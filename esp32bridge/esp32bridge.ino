#include <BLEDevice.h>
#include <BLEUtils.h>
#include <BLEScan.h>
#include <BLESecurity.h>

const char* LOG_TAG = "ESP32OmBlePy";

const BLEUUID        serviceUUID("ecbe3980-c9a2-11e1-b1bd-0002a5d5c51b");
const BLEUUID   deviceUnlockUUID("b305b680-aee7-11e1-a730-0002a5d5c51b");

const BLEUUID rxChannels[] = {
  BLEUUID("49123040-aee8-11e1-a74d-0002a5d5c51b"),
  BLEUUID("4d0bf320-aee8-11e1-a0d9-0002a5d5c51b"),
  BLEUUID("5128ce60-aee8-11e1-b84b-0002a5d5c51b"),
  BLEUUID("560f1420-aee8-11e1-8184-0002a5d5c51b"),
};

const BLEUUID txChannels[] = {
  BLEUUID("db5b55e0-aee7-11e1-965e-0002a5d5c51b"),
  BLEUUID("e0b8a060-aee7-11e1-92f4-0002a5d5c51b"),
  BLEUUID("0ae12b00-aee8-11e1-a192-0002a5d5c51b"),
  BLEUUID("10e1ba60-aee8-11e1-89e5-0002a5d5c51b"),
};

BLEClient*                    clientP = NULL;
BLERemoteService*      remoteServiceP = NULL;
static volatile int    rxFinishedFlag = 0;
static volatile uint8_t*      rxDataP = NULL;
std::vector<uint8_t> defaultUnlockKey = {0xde, 0xad, 0xbe, 0xaf, 0x12, 0x34, 0x12, 0x34, 0xde, 0xad, 0xbe, 0xaf, 0x12, 0x34, 0x12, 0x34};
uint8_t rxChannelDataCache[4][16]     = {0x00};
uint8_t rxChannelDoneState[4]         = {0x00};

void _enableRxChannelNotifyAndCallback(){
  for(int channelIdx = 0; channelIdx < sizeof(rxChannels)/sizeof(rxChannels[0]); channelIdx++){
    BLERemoteCharacteristic* characteristicP = remoteServiceP->getCharacteristic(rxChannels[channelIdx]);
    characteristicP->registerForNotify(_callbackForRXchannels);
  }
}

void _disableRxChannelNotifyAndCallback(){
  for(int channelIdx = 0; channelIdx < sizeof(rxChannels)/sizeof(rxChannels[0]); channelIdx++){
    BLERemoteCharacteristic* characteristicP = remoteServiceP->getCharacteristic(rxChannels[channelIdx]);
    characteristicP->registerForNotify(NULL);
  }
}
void _callbackForUnlockChannel(BLERemoteCharacteristic* BLERemoteCharacteristicP, uint8_t* dataP, size_t length, bool isNotify) {
    ESP_LOGI(LOG_TAG, "callback in unlock char");
    rxDataP = dataP;
    rxFinishedFlag = 1;
}
void _callbackForRXchannels(BLERemoteCharacteristic* BLERemoteCharacteristicP, uint8_t* dataP, size_t length, bool isNotify) {
  int characteristicIdx = 0;
  for(;characteristicIdx<4;characteristicIdx++){
    if(BLERemoteCharacteristicP->getUUID().equals(rxChannels[characteristicIdx])){
      break;
    }
  }
  rxChannelDoneState[characteristicIdx] = 1;
  memcpy(rxChannelDataCache[characteristicIdx], dataP, length);
  if(rxChannelDoneState[0]){
    int packetSize = rxChannelDataCache[0][0];
    int requiredChannels = (packetSize + 15) / 16;
    for(int channelIdx = 0; channelIdx < requiredChannels; channelIdx++){
      if(rxChannelDoneState[channelIdx]){
        return; //not all required channels are there yet, wait for more data
      }
    }
    rxFinishedFlag = 1;
    //todo combine data, maybe incode as base64 to send over serial
  }

}

class OmronBleSecCallbacks : public BLESecurityCallbacks {
  uint32_t onPassKeyRequest(){
    ESP_LOGE(LOG_TAG, "onPassKeyRequest");
    return 0;
  }
  void onPassKeyNotify(uint32_t pass_key){
    ESP_LOGE(LOG_TAG, "The passkey Notify number:%d", pass_key);
  }
  bool onConfirmPIN(uint32_t pass_key){
    ESP_LOGI(LOG_TAG, "The passkey YES/NO number:%d", pass_key);
    vTaskDelay(5000);
    return true;
  }
  bool onSecurityRequest(){
    ESP_LOGI(LOG_TAG, "Security Request");
    return true;
  }
  void onAuthenticationComplete(esp_ble_auth_cmpl_t auth_cmpl){
    if(auth_cmpl.success){
      ESP_LOGI(LOG_TAG, "Auth success, remote BD_ADDR:");
      esp_log_buffer_hex(LOG_TAG, auth_cmpl.bd_addr, sizeof(auth_cmpl.bd_addr));
      ESP_LOGI(LOG_TAG, "address type = %d", auth_cmpl.addr_type);
      ESP_LOGI(LOG_TAG, "auth mode = %d", auth_cmpl.auth_mode);
    }else{
      ESP_LOGI(LOG_TAG, "auth fail reason: %d", auth_cmpl.fail_reason);
    }
    
  }
};

void setup() {
  Serial.begin(115200);
  ESP_LOGI(LOG_TAG, "ESP32 bridge online");
  BLEDevice::init("esp32bridge");
  BLEDevice::setEncryptionLevel(ESP_BLE_SEC_ENCRYPT);
  BLEDevice::setSecurityCallbacks(new OmronBleSecCallbacks());
  //setup encryption for successful pairing
  BLESecurity *securityP = new BLESecurity();
  ESP_LOGI(LOG_TAG, "try bonding");
  securityP->setCapability(ESP_IO_CAP_NONE);
  securityP->setKeySize(16);
  securityP->setAuthenticationMode(ESP_LE_AUTH_BOND); //also available ESP_LE_AUTH_NO_BOND, ESP_LE_AUTH_REQ_SC_MITM, ESP_LE_AUTH_BOND, ESP_LE_AUTH_NO_BOND
  securityP->setInitEncryptionKey(ESP_BLE_ENC_KEY_MASK | ESP_BLE_ID_KEY_MASK);
  securityP->setRespEncryptionKey(ESP_BLE_ENC_KEY_MASK | ESP_BLE_ID_KEY_MASK);
  
}

class AdvertisedDeviceCallbacks: public BLEAdvertisedDeviceCallbacks {
    void onResult(BLEAdvertisedDevice advertisedDevice) {
      Serial.printf("{\"mac\": \"%s\", \"name\": \"%s\", \"rssi\": \%d\"},", advertisedDevice.getAddress().toString().c_str(), advertisedDevice.getName().c_str(), advertisedDevice.getRSSI());
    }
};



void writeNewUnlockKey(BLEClient* clientP, std::vector<uint8_t> unlockKey){
  if(unlockKey.size() != 16){
    ESP_LOGE(LOG_TAG, "unlock key has incorrect format");
  }
  unlockKey.insert(unlockKey.begin(), 0x00);
  
  ESP_LOGI(LOG_TAG, "get service");
  remoteServiceP = clientP->getService(serviceUUID);
  if (!remoteServiceP) {
    ESP_LOGE(LOG_TAG, "remote service not found");
  }

  ESP_LOGI(LOG_TAG, "get characteristic");
  BLERemoteCharacteristic* unlockChannelCharacteristicP = remoteServiceP->getCharacteristic(deviceUnlockUUID);
  if(!unlockChannelCharacteristicP){
    ESP_LOGE(LOG_TAG, "unlock characteristic not found");
  }
  if(!unlockChannelCharacteristicP->canNotify()){
    ESP_LOGE(LOG_TAG, "unlock characteristic does not support notify");
  }

  unlockChannelCharacteristicP->registerForNotify(_callbackForUnlockChannel);
  ESP_LOGI(LOG_TAG, "write unlock code");
  rxFinishedFlag = 0;
  unlockChannelCharacteristicP->writeValue({0x02, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00});
  while(!rxFinishedFlag){};
  if((rxDataP[0] != 0x82) || (rxDataP[1] != 0x00)){
    ESP_LOGE(LOG_TAG, "Could not enter key programming mode.");
  }

  ESP_LOGI(LOG_TAG, "write default key");
  rxFinishedFlag = 0;
  unlockChannelCharacteristicP->writeValue(unlockKey.data(), unlockKey.size());
  while(!rxFinishedFlag){};
  if((rxDataP[0] != 0x80) || (rxDataP[1] != 0x00)){
    ESP_LOGE(LOG_TAG, "Failed to programm new key.");
  }
  Serial.printf("p OK");
}

void unlockWithUnlockKey(BLEClient* clientP, std::vector<uint8_t> unlockKey){
  if(unlockKey.size() != 16){
    ESP_LOGE(LOG_TAG, "unlock key has incorrect format");
  }
  unlockKey.insert(unlockKey.begin(), 0x01);

  ESP_LOGI(LOG_TAG, "get service");
  remoteServiceP = clientP->getService(serviceUUID);
  if (!remoteServiceP) {
    ESP_LOGE(LOG_TAG, "remote service not found");
  }

  ESP_LOGI(LOG_TAG, "get characteristic");
  BLERemoteCharacteristic* unlockChannelCharacteristicP = remoteServiceP->getCharacteristic(deviceUnlockUUID);
  if(!unlockChannelCharacteristicP){
    ESP_LOGE(LOG_TAG, "unlock characteristic not found");
  }
  if(!unlockChannelCharacteristicP->canNotify()){
    ESP_LOGE(LOG_TAG, "unlock characteristic does not support notify");
  }

  unlockChannelCharacteristicP->registerForNotify(_callbackForUnlockChannel);
  ESP_LOGI(LOG_TAG, "write unlock code");
  rxFinishedFlag = 0;
  unlockChannelCharacteristicP->writeValue(unlockKey.data(), unlockKey.size());
  while(!rxFinishedFlag){};
  if((rxDataP[0] != 0x81) || (rxDataP[1] != 0x00)){
    ESP_LOGE(LOG_TAG, "Could not unlock with key.");
  }
  Serial.printf("c OK");
}

void loop() {
  String command;
  if(Serial.available()){
    command = Serial.readStringUntil('\n');
  }
  switch (command[0]) {
    case 's':{
      BLEScan* bleScanP = BLEDevice::getScan();
      bleScanP->setAdvertisedDeviceCallbacks(new AdvertisedDeviceCallbacks());
      bleScanP->setActiveScan(true);
      bleScanP->setInterval(1000);
      bleScanP->setWindow(1000);
      Serial.print("[");
      BLEScanResults foundDevices = bleScanP->start(1, false);
      Serial.println("]");
      bleScanP->stop();
      bleScanP->clearResults();
    }
    break;
    case 'p':{
      clientP = BLEDevice::createClient();
      BLEAddress macAdderss = BLEAddress(command.substring(2).c_str());
      ESP_LOGI(LOG_TAG,"Trying to connect to %s", macAdderss.toString().c_str());
      clientP->connect(macAdderss, BLE_ADDR_TYPE_RANDOM);
      if (!clientP) {
        ESP_LOGE(LOG_TAG, "connection failed");
        exit(1);
      }
      writeNewUnlockKey(clientP, defaultUnlockKey);
    }
    break;
    case 'c':{
      clientP = BLEDevice::createClient();
      BLEAddress macAdderss = BLEAddress(command.substring(2).c_str());
      ESP_LOGI(LOG_TAG,"Trying to connect to %s", macAdderss.toString().c_str());
      clientP->connect(macAdderss, BLE_ADDR_TYPE_RANDOM);
      if (!clientP) {
        ESP_LOGE(LOG_TAG, "connection failed");
        exit(1);
      }
      unlockWithUnlockKey(clientP, defaultUnlockKey);
    }    
    break;
    case 'w':{
      // decode data from base64
    }
    break;
    case 'r':{
      // decode read data from base64
      // encode return data to base64
    }
    break;
  }
}
