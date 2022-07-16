import asyncio                                                      #avoid wait on bluetooth stack stalling the application
import terminaltables                                               #for pretty selection table for ble devices
import bleak                                                        #bluetooth low energy package for python
import re                                                           #regex to match bt mac address
import argparse                                                     #to process command line arguments
import datetime
import sys, os


#global constants
parentService_UUID        = "ecbe3980-c9a2-11e1-b1bd-0002a5d5c51b"

#global variables
bleClient           = None
examplePairingKey   = bytearray.fromhex("deadbeaf12341234deadbeaf12341234") #arbitrary choise
deviceSpecific      = None                            #imported module for each device

def convertByteArrayToHexString(array):
    return (bytes(array).hex())


class bluetoothTxRxHandler:
    #BTLE Characteristic IDs
    deviceCommandChannel_UUID = "db5b55e0-aee7-11e1-965e-0002a5d5c51b"
    deviceDataRxChannelUUIDs = [
                                    "49123040-aee8-11e1-a74d-0002a5d5c51b",
                                    "4d0bf320-aee8-11e1-a0d9-0002a5d5c51b",
                                    "5128ce60-aee8-11e1-b84b-0002a5d5c51b",
                                    "560f1420-aee8-11e1-8184-0002a5d5c51b"
                                ]
    deviceDataRxChannelIntHandles = [0x360, 0x370, 0x380, 0x390]
    deviceUnlock_UUID         = "b305b680-aee7-11e1-a730-0002a5d5c51b"
    
    def __init__(self, pairing = False):
        self.currentRxNotifyStateFlag   = False
        self.rxPacketType               = None
        self.rxEepromAddress            = None
        self.rxDataBytes                = None
        self.rxFinishedFlag             = False
        self.rxRawChannelBuffer         = [None] * 4 #a buffer for each channel
        
    async def _enableRxChannelNotifyAndCallback(self):
        if(self.currentRxNotifyStateFlag != True):
            for rxChannelUUID in self.deviceDataRxChannelUUIDs:
                await bleClient.start_notify(rxChannelUUID, self._callbackForRxChannels)
            self.currentRxNotifyStateFlag = True
                
    async def _disableRxChannelNotifyAndCallback(self):
        if(self.currentRxNotifyStateFlag != False):
            for rxChannelUUID in self.deviceDataRxChannelUUIDs:
                await bleClient.stop_notify(rxChannelUUID)
            self.currentRxNotifyStateFlag = False
                
    def _callbackForRxChannels(self, UUID_or_intHandle, rxBytes):
        rxChannelId = self.deviceDataRxChannelIntHandles.index(UUID_or_intHandle)
        self.rxRawChannelBuffer[rxChannelId] = rxBytes
        
        print(f"rx on channel {rxChannelId}\n{convertByteArrayToHexString(rxBytes)}")
        
        if self.rxRawChannelBuffer[0]:                               #if there is data present in the first rx buffer
            packetSize       = self.rxRawChannelBuffer[0][0]
            requiredChannels = range(((packetSize - 1) // 16) + 1)
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
            self.rxDataBytes        = combinedRawRx[6: 6 + combinedRawRx[5]]
            self.rxRawChannelBuffer = [None] * 4 #clear channel buffers
            self.rxFinishedFlag     = True
            return
        return
    
    async def _waitForRxOrRetry(self, command, timeoutS = 1.0):
        self.rxFinishedFlag = False
        retries = 0
        while True:
            currentTimeout = timeoutS
            await bleClient.write_gatt_char(self.deviceCommandChannel_UUID, command)
            while(self.rxFinishedFlag == False):
                await asyncio.sleep(0.1)
                currentTimeout -= 0.1
                if(currentTimeout < 0):
                    break
            if(currentTimeout >= 0):
                break
            retries += 1
            if(retries > 5):
                ValueError("Same transmission failed 5 times, abort")
    
    async def startTransmission(self):
        await self._enableRxChannelNotifyAndCallback()
        startDataReadout    = bytearray.fromhex("0800000000100018")
        await self._waitForRxOrRetry(startDataReadout)
        if(self.rxPacketType != bytearray.fromhex("8000")):
            raise ValueError("invalid response to data readout start")
                
    async def endTransmissionAndPoweroff(self):
        stopDataReadout         = bytearray.fromhex("080f000000000007")
        await self._waitForRxOrRetry(stopDataReadout)
        if(self.rxPacketType != bytearray.fromhex("8f00")):
            raise ValueError("invlid response to data readout end")
        await self._disableRxChannelNotifyAndCallback()
    
    async def _writeBlockEeprom(self, address, dataByteArray):
        if(len(dataByteArray) > 0x08):
            raise ValueError("single write commands larger than 8 bytes not possible")
        dataWriteCommand = bytearray.fromhex("1001c0")  
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
        
        await self._waitForRxOrRetry(dataWriteCommand)
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
        await self._waitForRxOrRetry(dataReadCommand)
        if(self.rxEepromAddress != address.to_bytes(2, 'big')):
            raise ValueError(f"revieved packet address {self.rxEepromAddress} does not match requested address {address.to_bytes(2, 'big')}")
        if(self.rxPacketType != bytearray.fromhex("8100")):
            raise ValueError("Invalid packet type in eeprom read")
        return self.rxDataBytes
    
    async def writeContinuousEepromData(self, startAddress, bytesArrayToWrite):
        print("data write start...")
        while(len(bytesArrayToWrite) != 0):
            nextSubblockSize = min(len(bytesArrayToWrite), 0x08)
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
        
    async def writeNewPairingKey(self, newKeyByteArray = examplePairingKey):
        if(len(newKeyByteArray) != 16):
            raise ValueError(f"key has to be 16 bytes long, is {len(newKeyByteArray)}")
        #enable key programming mode
        await bleClient.write_gatt_char(self.deviceUnlock_UUID, b'\x02' + b'\x00'*16, response=True)
        await asyncio.sleep(0.5)
        deviceResponse = await bleClient.read_gatt_char(self.deviceUnlock_UUID, use_cached = False)
        if(deviceResponse[:2] != bytearray.fromhex("8200")):
            raise ValueError(f"Could not enter key programming mode. Has the device been started in pairing mode?")
        
        #programm new key
        await bleClient.write_gatt_char(self.deviceUnlock_UUID, b'\x00' + newKeyByteArray, response=True)
        await asyncio.sleep(0.5)
        deviceResponse = await bleClient.read_gatt_char(self.deviceUnlock_UUID, use_cached = False)
        if(deviceResponse[:2] != bytearray.fromhex("8000")):
            raise ValueError(f"Failure to programm new key.")
            
        print(f"Paired device successfully with new key {newKeyByteArray}.")
        print("From now on you can connect ommit the -p flag, even on other PCs with different Bluetooth-MAC-addresses.")
        return
        
    async def unlockWithPairingKey(self, keyByteArray = examplePairingKey):
        await bleClient.write_gatt_char(self.deviceUnlock_UUID, b'\x01' + keyByteArray, response=True)
        await asyncio.sleep(0.5)
        deviceResponse = await bleClient.read_gatt_char(self.deviceUnlock_UUID, use_cached = False)
        if(deviceResponse[:2] !=  bytearray.fromhex("8100")):
            raise ValueError(f"entered pairing key does not match stored one.")
        return


async def parseUserRecords(btobj):
    recordSize   = deviceSpecific.recordSize()
    startAddress = deviceSpecific.startAddress()
    user1Entries = deviceSpecific.user1Entries()
    user2Entries = deviceSpecific.user2Entries()
    
    await btobj.unlockWithPairingKey()
    await btobj.startTransmission()
    
    
    readData = await btobj.readContinuousEepromData(startAddress, recordSize * (user1Entries + user2Entries))
    
    #reset unread records counter
    if(hasattr(deviceSpecific, "resetUnreadRecordsCount")):
        await deviceSpecific.resetUnreadRecordsCount(btobj)
    
    await btobj.endTransmissionAndPoweroff()
    
    
    #slice split for both users, then split each record
    user1ByteRecords = readData[:recordSize * user1Entries]
    user1ByteRecords = [user1ByteRecords[recordStartPos:recordStartPos+recordSize] for recordStartPos in range(0, len(user1ByteRecords), recordSize)]
    #print(user1ByteRecords)
    user2ByteRecords = readData[recordSize * user1Entries:]
    user2ByteRecords = [user2ByteRecords[recordStartPos:recordStartPos+recordSize] for recordStartPos in range(0, len(user2ByteRecords), recordSize)]
        
    user1ParsedRecordsList = list()
    user2ParsedRecordsList = list()
    for recordBytes in user1ByteRecords:
        if(recordBytes != b'\xff' * recordSize):
            user1ParsedRecordsList.append(deviceSpecific.recordToDict(recordBytes))
    for recordBytes in user2ByteRecords:
        if(recordBytes != b'\xff' * recordSize):
            user2ParsedRecordsList.append(deviceSpecific.recordToDict(recordBytes))
    
    user1ParsedRecordsList = sorted(user1ParsedRecordsList, key = lambda x: x["datetime"])
    user2ParsedRecordsList = sorted(user2ParsedRecordsList, key = lambda x: x["datetime"])
    
    return [user1ParsedRecordsList, user2ParsedRecordsList]

def writeCsv(allRecords):
    import csv
    for userIdx in range(2):
        print(f"writing data to user{userIdx+1}.csv")
        with open(f"user{userIdx+1}.csv", mode='w', newline='', encoding='utf-8') as outfile:
            writer = csv.DictWriter(outfile, fieldnames = ["datetime", "dia", "sys", "bpm", "mov", "ihb"])
            writer.writeheader()
            for recordDict in allRecords[userIdx]:
                writer.writerow(recordDict)

async def selectBLEdevices():
    print("Scanning for BLE devices...")
    while(True):
        devices = await bleak.BleakScanner.discover()
        devices = sorted(devices, key = lambda x: x.rssi, reverse=True)
        tableEntries = []
        tableEntries.append(["ID", "MAC", "NAME", "RSSI"])
        for deviceIdx, device in enumerate(devices):
            tableEntries.append([deviceIdx, device.address, device.name, device.rssi])
        print(terminaltables.AsciiTable(tableEntries).table)
        res = input("Enter ID or just press Enter to rescan.\n")
        if(res.isdigit() and int(res) in range(len(devices))):
            break
    return devices[int(res)].address

async def main():
    global bleClient
    global deviceSpecific
    parser = argparse.ArgumentParser(description="python tool to read the records of omron blood pressure instruments")
    parser.add_argument("-p", "--pair", action="store_true", help="Programm the pairing key into the device. Needs to be done only once.")
    parser.add_argument("-m", "--mac",      type=ascii, help="Bluetooth Mac address of the device (e.g. 00:1b:63:84:45:e6). If not specified, will scan for devices and display a selection dialog.")
    parser.add_argument('-d', "--device",   type=ascii, help="Device name (e.g. HEM-7322T-D).")
    args = parser.parse_args()
    
    if(not args.pair and not args.device):
        raise ValueError("When not in pairing mode, please specify your device type name with -d or --device")
    if(args.device):
        deviceName = args.device.strip("'").strip('\"') #strip quotes around arg
        sys.path.insert(0, "./deviceSpecific")
        try:
            print(f"Attempt to import module for device {deviceName.lower()}")
            deviceSpecific = __import__(deviceName.lower())
        except ImportError:
            raise ValueError("the device is no supported yet, you can help by contributing :)")
    
    
    validMacRegex = re.compile(r"^([0-9a-fA-F]{2}[:-]){5}([0-9a-fA-F]{2})$")  
    if(args.mac is not None):
        btmac = args.mac.strip("'").strip('\"') #strip quotes around arg
        if(validMacRegex.match(btmac) is None):
            raise ValueError(f"argument after -m or --mac {btmac} is not a valid mac address")
        bleAddr = btmac
    else:
        print("To improve your chance of a successful connection please do the following:")
        print(" -remove previous device pairings in your OS's bluetooth dialog")
        print(" -enable bluetooth on you omron device and use the specified mode (pairing or normal)")
        print(" -do not accept any pairing dialog until you selected your device in the following list\n")
        bleAddr = await selectBLEdevices()
    
    bleClient = bleak.BleakClient(bleAddr)
    try:
        print(f"Attempt connecting to {bleAddr}.")
        await bleClient.connect()
        await asyncio.sleep(0.5)
        #verify that the device is an omron device by checking presence of certain bluetooth services
        services = await bleClient.get_services()
        if parentService_UUID not in [service.uuid for service in services]:
            raise OSError("""Some required bluetooth attributes not found on this ble device. 
                             This means that either, you connected to a wrong device, 
                             or that your OS has a bug when reading BT LE device attributes (certain linux versions).""")
        await asyncio.sleep(0.5)
        
        bluetoothTxRxObj = bluetoothTxRxHandler(args.pair)
        if(args.pair):
            await bluetoothTxRxObj.writeNewPairingKey()
        else:
            allRecs = await parseUserRecords(bluetoothTxRxObj)
            writeCsv(allRecs)
    finally:
        await bleClient.disconnect()

asyncio.run(main())
