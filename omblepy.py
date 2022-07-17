import asyncio                                                      #avoid wait on bluetooth stack stalling the application
import terminaltables                                               #for pretty selection table for ble devices
from bluezero import adapter                                        #bluetooth low energy package for python
from bluezero import device
from bluezero import central
from gi.repository import GLib
import re                                                           #regex to match bt mac address
import argparse                                                     #to process command line arguments
import datetime
import sys, os
import pathlib
import dbus         #for exception with name and bug in bluezero


#global variables
examplePairingKey   = bytearray.fromhex("deadbeaf12341234" * 2)     #arbitrary choise
deviceSpecific      = None                                          #imported module for each device

def convertByteArrayToHexString(array):
    return (bytes(array).hex())

class bluetoothTxRxHandler:
    #BTLE Characteristic IDs
    deviceMainServiceUUID = "ecbe3980-c9a2-11e1-b1bd-0002a5d5c51b"
    deviceTxChannelUUIDs  = [
                                "db5b55e0-aee7-11e1-965e-0002a5d5c51b",
                                "e0b8a060-aee7-11e1-92f4-0002a5d5c51b",
                                "0ae12b00-aee8-11e1-a192-0002a5d5c51b",
                                "10e1ba60-aee8-11e1-89e5-0002a5d5c51b"
                            ]
    deviceRxChannelUUIDs  = [
                                "49123040-aee8-11e1-a74d-0002a5d5c51b",
                                "4d0bf320-aee8-11e1-a0d9-0002a5d5c51b",
                                "5128ce60-aee8-11e1-b84b-0002a5d5c51b",
                                "560f1420-aee8-11e1-8184-0002a5d5c51b"
                            ]
    #deviceDataRxChannelIntHandles = [0x360, 0x370, 0x380, 0x390]
    deviceUnlock_UUID     = "b305b680-aee7-11e1-a730-0002a5d5c51b"
    
    def __init__(self, bleCentInst):
        self.currentRxNotifyStateFlag   = False
        self.rxPacketType               = None
        self.rxEepromAddress            = None
        self.rxDataBytes                = None
        self.rxFinishedFlag             = False
        self.rxRawChannelBuffer         = [None] * 4 #a buffer for each channel
        
        self.bleCentralInstance = bleCentInst
        self.unlockChannel  = self.bleCentralInstance.add_characteristic(self.deviceMainServiceUUID, self.deviceUnlock_UUID)
        self.rxChannels = []
        self.txChannels = []
        for rxUUID in self.deviceRxChannelUUIDs:
            self.rxChannels.append(self.bleCentralInstance.add_characteristic(self.deviceMainServiceUUID, rxUUID))
        for txUUID in self.deviceTxChannelUUIDs:
            self.txChannels.append(self.bleCentralInstance.add_characteristic(self.deviceMainServiceUUID, txUUID))
        
        
    async def _enableRxChannelNotifyAndCallback(self):
        if(self.currentRxNotifyStateFlag != True):
            for rxIdx, rxChannel in enumerate(self.rxChannels):
                rxChannel.start_notify()
                rxChannel.add_characteristic_cb(self._wrappedCallbackRxGenerator(self.deviceRxChannelUUIDs[rxIdx]))
                self.bleCentralInstance.run()
            self.currentRxNotifyStateFlag = True
                
    async def _disableRxChannelNotifyAndCallback(self):
        if(self.currentRxNotifyStateFlag != False):
            for rxChannel in self.rxChannels:
                rxChannel.stop_notify()
                rxChannel.add_characteristic_cb()
            self.currentRxNotifyStateFlag = False
    
    def _wrappedCallbackRxGenerator(self, uuid):
        def wrappedFunction(iface, changed_props, invalidated_props):
            notify = changed_props.get("Notifying", None)
            value  = changed_props.get("Value", None)
            if(notify):
                self.bleCentralInstance.quit()
                return
            if not value:
                return
            rxBytes = bytes(value)
            self._callbackForRxChannels(uuid, rxBytes)
        return wrappedFunction
    
    def _callbackForRxChannels(self, UUID_or_intHandle, rxBytes):

        rxChannelId = self.deviceRxChannelUUIDs.index(UUID_or_intHandle)
        self.rxRawChannelBuffer[rxChannelId] = rxBytes
        
        print(f"rx on channel {rxChannelId}\n{convertByteArrayToHexString(rxBytes)}")
        
        if self.rxRawChannelBuffer[0]:                               #if there is data present in the first rx buffer
            packetSize       = self.rxRawChannelBuffer[0][0]
            requiredChannels = range((packetSize + 15) // 16)
            #are all required channels already recieved
            for channelIdx in requiredChannels: 
                if self.rxRawChannelBuffer[channelIdx] is None:         #if one of the required channels is empty wait for more packets to arrive
                    return
           
            #check crc
            combinedRawRx = bytearray()
            for channelIdx in requiredChannels:
                combinedRawRx += self.rxRawChannelBuffer[channelIdx]
            combinedRawRx = combinedRawRx[:packetSize]          #cut extra bytes from the end
            xorCrc = 0
            for byte in combinedRawRx:
                xorCrc ^= byte
            if(xorCrc):
                raise ValueError(f"data corruption in rx\ncrc: {xorCrc}\ncombniedBuffer: {convertByteArrayToHexString(combinedRawRx)}")
            
            #extract information
            self.rxPacketType       = combinedRawRx[1:3]
            self.rxEepromAddress    = combinedRawRx[3:5]
            expectedNumDataBytes       = combinedRawRx[5]
            #neccessary fix for hem7361t, does not transmit zero bytes
            if(expectedNumDataBytes > (len(combinedRawRx) - 8)):
                self.rxDataBytes    = bytes(b'\xff') * expectedNumDataBytes
            else:
                self.rxDataBytes    = combinedRawRx[6: 6 + expectedNumDataBytes]
            self.rxRawChannelBuffer = [None] * 4 #clear channel buffers
            self.rxFinishedFlag     = True
            self.bleCentralInstance.quit()
            return
        return
    
    async def _waitForRx(self, command, timeoutMs = 1000):
        self.rxFinishedFlag = False
        requiredTxChannels = range((len(command) + 15) // 16)
        for channelIdx in requiredTxChannels:
            print(f"tx ch{channelIdx} bytes {command[:16]}")
            self.txChannels[channelIdx].write_value(list(command[:16]))
            command = command[16:]
        self.bleCentralInstance.run()
        if(self.rxFinishedFlag == False):
            raise ValueError("Packet did not arrive fully.")
        
    async def startTransmission(self):
        await self._enableRxChannelNotifyAndCallback()
        startDataReadout    = bytearray.fromhex("0800000000100018")
        await self._waitForRx(startDataReadout)
        if(self.rxPacketType != bytearray.fromhex("8000")):
            raise ValueError("invalid response to data readout start")
                
    async def endTransmission(self):
        stopDataReadout         = bytearray.fromhex("080f000000000007")
        await self._waitForRx(stopDataReadout)
        if(self.rxPacketType != bytearray.fromhex("8f00")):
            raise ValueError("invlid response to data readout end")
        await self._disableRxChannelNotifyAndCallback()
    
    async def _writeBlockEeprom(self, address, dataByteArray):
        if(len(dataByteArray) > 0x30):
            raise ValueError("single write commands larger than 0x30 bytes not possible")
        dataWriteCommand = bytearray()
        dataWriteCommand += (len(dataByteArray) + 8).to_bytes(1, 'big') #total packet size with 6byte header and 2byte crc
        dataWriteCommand += bytearray.fromhex("01c0")  
        dataWriteCommand += address.to_bytes(2, 'big')
        dataWriteCommand += len(dataByteArray).to_bytes(1, 'big')
        dataWriteCommand += dataByteArray
        #calculate and append crc
        xorCrc = 0
        for byte in dataWriteCommand:
            xorCrc ^= byte
        dataWriteCommand += b'\x00'
        dataWriteCommand.append(xorCrc)
        
        print(f"Write command. {convertByteArrayToHexString(dataWriteCommand)}")
        
        await self._waitForRx(dataWriteCommand)
        if(self.rxEepromAddress != address.to_bytes(2, 'big')):
            raise ValueError(f"recieved packet address {self.rxEepromAddress} does not match the written address {address.to_bytes(2, 'big')}")
        if(self.rxPacketType != bytearray.fromhex("81c0")):
            raise ValueError("Invalid packet type in eeprom write")
        return
    
    async def _readBlockEeprom(self, address, blocksize):
        dataReadCommand = bytearray.fromhex("080100")  
        dataReadCommand += address.to_bytes(2, 'big')
        dataReadCommand += blocksize.to_bytes(1, 'big')  
        #calculate and append crc
        xorCrc = 0
        for byte in dataReadCommand:
            xorCrc ^= byte
        dataReadCommand += b'\x00'
        dataReadCommand.append(xorCrc)
        await self._waitForRx(dataReadCommand)
        if(self.rxEepromAddress != address.to_bytes(2, 'big')):
            raise ValueError(f"revieved packet address {self.rxEepromAddress} does not match requested address {address.to_bytes(2, 'big')}")
        if(self.rxPacketType != bytearray.fromhex("8100")):
            raise ValueError("Invalid packet type in eeprom read")
        return self.rxDataBytes
    
    async def writeContinuousEepromData(self, startAddress, bytesArrayToWrite, btBlockSize = 0x08):
        print("data write start...")
        while(len(bytesArrayToWrite) != 0):
            nextSubblockSize = min(len(bytesArrayToWrite), btBlockSize)
            print(f"write at {hex(startAddress)} size {hex(nextSubblockSize)}")
            await self._writeBlockEeprom(startAddress, bytesArrayToWrite[:nextSubblockSize])
            bytesArrayToWrite = bytesArrayToWrite[nextSubblockSize:]
            startAddress += nextSubblockSize
            print(bytesArrayToWrite)
        return
    
    async def readContinuousEepromData(self, startAddress, bytesToRead, btBlockSize = 0x38):
        print("data read start...")
        
        #check if blutooth block size is compatible with device
        #4 rx channels 16 bytes each, first 6 bytes packet header, last 2 bytes part of checksum)
        if(btBlockSize > 16 * 4 - (6 + 2)): 
            raise ValueError("btBlockSize to large")
        #read out data
        eepromBytesData = bytearray()
        while(bytesToRead != 0):
            nextSubblockSize = min(bytesToRead, btBlockSize)
            print(f"read at {hex(startAddress)} size {hex(nextSubblockSize)}")
            eepromBytesData += await self._readBlockEeprom(startAddress, nextSubblockSize)
            startAddress    += nextSubblockSize
            bytesToRead     -= nextSubblockSize
        return eepromBytesData
        
    def writeNewUnlockKey(self, newKeyByteArray = examplePairingKey):
        if(len(newKeyByteArray) != 16):
            raise ValueError(f"key has to be 16 bytes long, is {len(newKeyByteArray)}")
        #enable key programming mode
        self.unlockChannel.write_value([0x02])
        deviceResponse = bytes(self.unlockChannel.read_raw_value())
        if(deviceResponse[:2] != bytearray.fromhex("8200")):
            raise ValueError(f"Could not enter key programming mode. Has the device been started in pairing mode?")
        
        #programm new key
        self.unlockChannel.write_value([0x00] + list(newKeyByteArray))
        deviceResponse = bytes(self.unlockChannel.read_raw_value())
        if(deviceResponse[:2] != bytearray.fromhex("8000")):
            raise ValueError(f"Failure to programm new key.")
        
        print(f"Paired device successfully with new key {newKeyByteArray}.")
        print("From now on you can connect ommit the -p flag, even on other PCs with different Bluetooth-MAC-addresses.")
        return
        
    def unlockWithUnlockKey(self, keyByteArray = examplePairingKey):
        self.unlockChannel.write_value([0x01] + list(keyByteArray))
        deviceResponse = bytes(self.unlockChannel.read_raw_value())
        if(deviceResponse[:2] !=  bytearray.fromhex("8100")):
            raise ValueError(f"entered pairing key does not match stored one. got {deviceResponse}")
        print("unlocked")
        return



def appendCsv(allRecords):
    import csv    
    for userIdx in range(2):
        oldCsvFile = pathlib.Path("user{userIdx+1}.csv")
        if(oldCsvFile.is_file()):
            with open(f"user{userIdx+1}.csv", mode='r', newline='', encoding='utf-8') as infile:
                reader = csv.DictReader(infile)
                for recordDict in reader:
                    if recordDict not in allRecords[userIdx]: #only add if record is new
                        allRecords[userIdx].append(recordDict)
        allRecords[userIdx] = sorted(allRecords[userIdx], key = lambda x: x["datetime"])
        print(f"writing data to user{userIdx+1}.csv")
        with open(f"user{userIdx+1}.csv", mode='w', newline='', encoding='utf-8') as outfile:
            writer = csv.DictWriter(outfile, fieldnames = ["datetime", "dia", "sys", "bpm", "mov", "ihb"])
            writer.writeheader()
            for recordDict in allRecords[userIdx]:
                writer.writerow(recordDict)

def getRssiOrDefaultValueForSorting(dev):
    if(dev.RSSI is None):
        return -100
    else:
        return dev.RSSI

def selectBLEdevices(btAdap):
    print("Scanning for BLE devices...")
    while(True):
        btAdap.nearby_discovery(timeout = 5)
        devices = list(device.Device.available())
        devices = sorted(devices, key = getRssiOrDefaultValueForSorting, reverse=True)
        tableEntries = []
        tableEntries.append(["ID", "MAC", "NAME", "RSSI"])
        for deviceIdx, dev in enumerate(devices):
            tableEntries.append([deviceIdx, dev.address, dev.name, dev.RSSI])
        print(terminaltables.AsciiTable(tableEntries).table)
        res = input("Enter ID or just press Enter to rescan.\n")
        if(res.isdigit() and int(res) in range(len(devices))):
            break
    return devices[int(res)].address

def selectBtAdapter():
    while(True):
        dongles = list(adapter.Adapter.available())
        tableEntries = []
        tableEntries.append(["ID", "MAC", "NAME", "POWERED"])
        for dongleIdx, dongle in enumerate(dongles):
            tableEntries.append([dongleIdx, dongle.address, dongle.name, dongle.powered])
        print(terminaltables.AsciiTable(tableEntries).table)    
        res = input("Enter ID or just press Enter to rescan.\n")
        if(res.isdigit() and (int(res) in range(len(dongles)))):
            break
    return dongles[int(res)].address

async def main():
    global deviceSpecific
    parser = argparse.ArgumentParser(description="python tool to read the records of omron blood pressure instruments")
    parser.add_argument('-d', "--device", required="true",   type=ascii, help="Device name (e.g. HEM-7322T-D).")
    parser.add_argument("-p", "--pair",   action="store_true",           help="Programm the pairing key into the device. Needs to be done only once.")
    parser.add_argument("-m", "--mac",                       type=ascii, help="Bluetooth Mac address of the device (e.g. 00:1b:63:84:45:e6). If not specified, will scan for devices and display a selection dialog.")
    parser.add_argument('-a', "--adapter",                   type=ascii, help="HCI Bluetooth adapter mac address")
    parser.add_argument('-n', "--newRecOnly", action="store_true",       help="Considers the unread records counter and only reads new records. Resets these counters afterwards. If not enabled, all records are read and the unread counters are not cleared.")
    args = parser.parse_args()
    
    #import the module for the device
    deviceName = args.device.strip("'").strip('\"') #strip quotes around arg
    sys.path.insert(0, "./deviceSpecific")
    try:
        print(f"Attempt to import module for device {deviceName.lower()}")
        deviceSpecific = __import__(deviceName.lower())
    except ImportError:
        raise ValueError("the device is no supported yet, you can help by contributing :)")
    
    #select bt adapter if neccesary
    if(args.adapter is not None):
        btAdapterMac = args.adapter.strip("'").strip('\"')
    else:
        btAdapterMac = selectBtAdapter()
    btAdapter = adapter.Adapter(adapter_addr = btAdapterMac)
    btAdapter.pairable = True
    #TODO maybe use to clear previousely connected devices btAdapter.remove_device(device_path = )
    
    
    #select device if neccesary
    validMacRegex = re.compile(r"^([0-9a-fA-F]{2}[:-]){5}([0-9a-fA-F]{2})$")  
    if(args.mac is not None):
        btmac = args.mac.strip("'").strip('\"') #strip quotes around arg
        if(validMacRegex.match(btmac) is None):
            raise ValueError(f"argument after -m or --mac {btmac} is not a valid mac address")
        bleAddr = btmac
        btAdapter.nearby_discovery(timeout = 3) #some scanning time to find device
    else:
        bleAddr = selectBLEdevices(btAdapter)
    
    #delete bluetooth device to delete cache
    #dev = device.Device(adapter_addr = bleAddr, device_addr = btAdapterMac)
    #btAdapter.remove_device(str(dev.device_path))
    
    bleCentralInstance = central.Central(device_addr = bleAddr, adapter_addr = btAdapterMac)
    bluetoothTxRxObj = bluetoothTxRxHandler(bleCentralInstance)
    bleCentralInstance.connect() #connect must be after defining the services in the bluetoothTxRxHandler.__init__ function
    
    if not bleCentralInstance.connected:
        raise ValueException("Not connected to device")
    else:
        print("Connection succesfull, wait for pairing.")
        
    #do pairing and data readout
    bleCentralInstance.rmt_device.pair()
    if not bleCentralInstance.rmt_device.paired:
        raise ValueException("Not paired to device")
    else:
        print("BT Pairing successfull, Encrypted connection established")
    if(args.pair):
        bluetoothTxRxObj.writeNewUnlockKey()
    if(args.newRecOnly):
        allRecs = await deviceSpecific.getNewRecordsDoResetUnreadCounter(bluetoothTxRxObj)
    else:
        allRecs = await deviceSpecific.getAllRecordsDoNotResetUnreadCounter(bluetoothTxRxObj)
    appendCsv(allRecs)
   
    #disconnect and unpair in the end
    devicePathStr = str(bleCentralInstance.rmt_device.remote_device_path)
    bleCentralInstance.disconnect()
    print(f"remove os bluetooth pairing information for device {devicePathStr}")
    btAdapter.remove_device(devicePathStr)

asyncio.run(main())
