import asyncio                                                      #avoid wait on bluetooth stack stalling the application
import terminaltables                                               #for pretty selection table for ble devices
import bleak                                                        #bluetooth low energy package for python
import re                                                           #regex to match bt mac address
import argparse                                                     #to process command line arguments
import time, datetime
import sys, os


#global constants
parentService_UUID        = "ecbe3980-c9a2-11e1-b1bd-0002a5d5c51b"

deviceUnlock_UUID         = "b305b680-aee7-11e1-a730-0002a5d5c51b"

deviceCommandChannel_UUID = "db5b55e0-aee7-11e1-965e-0002a5d5c51b"
deviceDataRxChannel0_UUID = "49123040-aee8-11e1-a74d-0002a5d5c51b" #first  16 bytes of transmission will arrive here
deviceDataRxChannel0_IntHandle = 0x360
deviceDataRxChannel1_UUID = "4d0bf320-aee8-11e1-a0d9-0002a5d5c51b" #second 16 bytes of transmission will arrive here
deviceDataRxChannel1_IntHandle = 0x370
deviceDataRxChannel2_UUID = "5128ce60-aee8-11e1-b84b-0002a5d5c51b" #third  16 bytes of transmission will arrive here
deviceDataRxChannel2_IntHandle = 0x380
deviceDataRxChannel3_UUID = "560f1420-aee8-11e1-8184-0002a5d5c51b" #fourth 16 bytes of transmission will arrive here
deviceDataRxChannel3_IntHandle = 0x390

channel0_IDcollection       = [deviceDataRxChannel0_UUID, deviceDataRxChannel0_IntHandle]
channel123_IDcollection     = [deviceDataRxChannel1_UUID, deviceDataRxChannel1_IntHandle,
                               deviceDataRxChannel2_UUID, deviceDataRxChannel2_IntHandle,
                               deviceDataRxChannel3_UUID, deviceDataRxChannel3_IntHandle]

#global variables
bleClient           = None
examplePairingKey   = bytearray.fromhex("deadbeaf12341234deadbeaf12341234") #arbitrary choise
deviceSpecific      = None                            #imported module for each device

#global variables for rx callback function
rxFinishedFlag          = False
totalBytesForBlock      = 0
dataBytesInBlock        = 0
rxChannelCombineBuffer  = bytearray()
rxTotalBuffer           = bytearray()
rxPacketTypeId          = None

def convertByteArrayToHexString(array):
    return (bytes(array).hex())

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

async def writeNewPairingKey(newKeyByteArray):
    global bleClient
    if(len(newKeyByteArray) != 16):
        raise ValueError(f"key has to be 16 bytes long, is {len(newKeyByteArray)}")
    #enable key programming mode
    switchToKeyProgMode       = b'\x02' + b'\x00'*16
    switchToKeyProgModeSucess = b'\x82' + b'\x00'*16
    await bleClient.write_gatt_char(deviceUnlock_UUID, switchToKeyProgMode, response=True)
    time.sleep(1)
    deviceResponse = await bleClient.read_gatt_char(deviceUnlock_UUID, use_cached = False)
    if(switchToKeyProgModeSucess != deviceResponse):
        print(deviceResponse)
        raise ValueError(f"Could not enter key programming mode. Has the device been started in pairing mode?")
    
    #programm new key
    setNewPairingKey         = b'\x00' + newKeyByteArray
    setNewPairingKeySucess   = b'\x80' + b'\x00'*16
    await bleClient.write_gatt_char(deviceUnlock_UUID, setNewPairingKey, response=True)
    time.sleep(1)
    deviceResponse = await bleClient.read_gatt_char(deviceUnlock_UUID, use_cached = False)
    if(setNewPairingKeySucess != deviceResponse):
        print(deviceResponse)
        raise ValueError(f"Failure to programm new key.")
    print(f"Paired device successfully with new key {newKeyByteArray}.")
    print("From now on you can connect ommit the -p flag, even on other PCs with different Bluetooth-MAC-addresses.")
    return
    
async def unlockWithPairingKey(keyByteArray):
    global bleClient
    enterPairingKey       = b'\x01' + keyByteArray
    enterPairingKeySucess = b'\x81' + b'\x00' * 16
    await bleClient.write_gatt_char(deviceUnlock_UUID, enterPairingKey, response=True)
    time.sleep(1)
    deviceResponse = await bleClient.read_gatt_char(deviceUnlock_UUID, use_cached = False)
    if(enterPairingKeySucess != deviceResponse):
        print(response)
        raise ValueError(f"Entered pairing key does not match.")

def getDataReadoutCommand(addressOffset, blockSize):
    dataAdressRead  = bytearray.fromhex("080100")  
    dataAdressRead += addressOffset.to_bytes(2, 'big')
    dataAdressRead += blockSize.to_bytes(1, 'big')  
    dataAdressRead += b'\x00'
    #last byte is xor crc
    xorCrc = 0
    for byte in dataAdressRead:
        xorCrc ^= byte
    dataAdressRead.append(xorCrc)
    return dataAdressRead

def callbackForNotifications(UUIDorIntHandle, rxBytes):
    global rxFinishedFlag
    global dataBytesInBlock
    global totalBytesForBlock
    global rxChannelCombineBuffer
    global rxTotalBuffer
    global rxPacketTypeId  #can be either 0x8000 or 0x8100, only 0x8100 are data packets
    
    print(f"Data Rx... {UUIDorIntHandle}, {convertByteArrayToHexString(rxBytes)}")
    

    if(UUIDorIntHandle in channel0_IDcollection):
        #analyze header, first 6 bytes
        totalBytesForBlock          = rxBytes[0]
        rxPacketTypeId              = rxBytes[1:3]               
        unusedRxAddress             = rxBytes[3:5] 
        dataBytesInBlock            = rxBytes[5]  
    elif(UUIDorIntHandle not in channel123_IDcollection):                            
        raise ValueError("Unkown ATT id {UUIDorIntHandle}")
    rxChannelCombineBuffer          += rxBytes                     

    if(len(rxChannelCombineBuffer) >= (totalBytesForBlock)):    #last 2 bytes are part of crc
        #calc if xorCrc matches
        xorCrc = 0
        for byte in rxChannelCombineBuffer:
            xorCrc ^= byte
        if(xorCrc != 0):
            raise ValueError(f"Data corruption in rx, {convertByteArrayToHexString(rxChannelCombineBuffer[:dataBytesInBlock + 2])}, crc={xorCrc}")
        
        #differentiate between packet types     
        if(bytearray.fromhex("8000") == rxPacketTypeId):
            print("got initial packet, ignoring")
            rxChannelCombineBuffer = bytearray()
            print("write rxf = 1")
            rxFinishedFlag = True
            return
        if(bytearray.fromhex("8100") != rxPacketTypeId):
            raise ValueError("Unexpected packet type")
            
        #export valid data to rxTotalBuffer
        rxTotalBuffer += rxChannelCombineBuffer[6: 6 + dataBytesInBlock] #extract only data bytes
        rxChannelCombineBuffer = bytearray()                       #clear combine buffer
        print("write rxf = 1")
        rxFinishedFlag = True
        return

def waitForRxAndCheckTimeout():
    global rxFinishedFlag
    timeout = 0.3
    while (rxFinishedFlag == False):
        time.sleep(0.1)
        timeout -= 0.1
        if(timeout < 0):
            break
    if(timeout < 0):
        return True
    rxFinishedFlag = False
    time.sleep(0.3)
    return False
        

async def readUserRecords(startAddressOffset, recordsSize, countUser1, countUser2, selectedTransferBlockSize = 0x38):
    global bleClient 
         
    global rxTotalBuffer
    
    deviceLimitTransferBlockSize = 16 * 4 - (6 + 2) # 4 rx channels 16 bytes each, first 6 bytes packet header, last 2 bytes part of checksum
    if(selectedTransferBlockSize > deviceLimitTransferBlockSize):
        raise ValueError("Chosen block size above device limit")
   
    #enable notifications on command and data channels
    await bleClient.start_notify(deviceDataRxChannel0_UUID, callbackForNotifications)
    await bleClient.start_notify(deviceDataRxChannel1_UUID, callbackForNotifications)
    await bleClient.start_notify(deviceDataRxChannel2_UUID, callbackForNotifications)
    await bleClient.start_notify(deviceDataRxChannel3_UUID, callbackForNotifications)
    time.sleep(0.5)
    
    #send command to start read data
    startDataReadout        = bytearray.fromhex("0800000000100018")
    rxFinishedFlag   = False
    await bleClient.write_gatt_char(deviceCommandChannel_UUID, startDataReadout)
    print(f"Start reading data...")
    #no wait for rxFinishedFlag here, because the rx channels seem to get filled only after the NEXT data request
    #meaning that the data arriving when the first address is read, is the data from the startDataReadout command
    time.sleep(0.3)
    
    #send address commands
    currentAddress = startAddressOffset
    numBytesToReadLeft = (countUser1 + countUser2) * recordsSize
    while numBytesToReadLeft != 0: 
        nextReadNumBytes    = min(numBytesToReadLeft, selectedTransferBlockSize)
        print(f"read {hex(currentAddress)}")
        await bleClient.write_gatt_char(deviceCommandChannel_UUID, getDataReadoutCommand(currentAddress, nextReadNumBytes))
        if(waitForRxAndCheckTimeout()):
            continue
        currentAddress      += nextReadNumBytes
        numBytesToReadLeft  -= nextReadNumBytes
    #disable notifications on command and data channels
    await bleClient.stop_notify(deviceDataRxChannel0_UUID)
    await bleClient.stop_notify(deviceDataRxChannel1_UUID)
    await bleClient.stop_notify(deviceDataRxChannel2_UUID)
    await bleClient.stop_notify(deviceDataRxChannel3_UUID)
    
    #end data read
    stopDataReadout         = bytearray.fromhex("080f000000000007")
    await bleClient.write_gatt_char(deviceCommandChannel_UUID, stopDataReadout)
    
    print(len(rxTotalBuffer))
    
    recordsUser1 = []
    recordsUser2 = []
    for user1recordIdx in range(countUser1):
        startRecordByte = (user1recordIdx)     * recordsSize
        endRecordByte   = (user1recordIdx + 1) * recordsSize
        recordsUser1.append(rxTotalBuffer[startRecordByte:endRecordByte])
    for user2recordIdx in range(countUser2):
        startRecordByte = (user2recordIdx + countUser1)     * recordsSize
        endRecordByte   = (user2recordIdx + countUser1 + 1) * recordsSize
        recordsUser2.append(rxTotalBuffer[startRecordByte:endRecordByte])
    return [recordsUser1, recordsUser2]


async def parseUserRecords():
    recordSize   = deviceSpecific.recordSize()
    startAddress = deviceSpecific.startAddress()
    user1Entries = deviceSpecific.user1Entries()
    user2Entries = deviceSpecific.user2Entries()
    
    await unlockWithPairingKey(examplePairingKey)
    user1ByteRecords, user2ByteRecords =  await readUserRecords(startAddress, recordSize, user1Entries, user2Entries)

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
            deviceSpecific = __import__(deviceName.lower())
        except ImportError:
            raise ValueError("the device is no supported yet, you can help by contributing :)")
    
    
    validMacRegex = re.compile("/^([0-9a-f]{2}[:-]){5}([0-9a-f]{2})$/i")  
    if(args.mac is not None):
        btmac = args.mac.strip("'").strip('\"') #strip quotes around arg
        if(validMacRegex.match(btmac) is None):
            raise ValueError("argument after -m or --mac is not a valid mac address")
        bleAddr = btmac
    else:
        print("To improve your chance of a successful connection please do the following:")
        print(" -remove previous device pairings in your OS's bluetooth dialog")
        print(" -enable bluetooth on you omron device and use the specified mode (pairing or normal)")
        print(" -do not accept any pairing dialog until you selected your device in the following list\n")
        bleAddr = await selectBLEdevices()
    
    bleClient = bleak.BleakClient(bleAddr)
    #try:
    print(f"Attempt connecting to {bleAddr}.")
    await bleClient.connect()
    time.sleep(1)
    #verify that the device is an omron device by checking presence of certain bluetooth services
    services = await bleClient.get_services()
    if parentService_UUID not in [service.uuid for service in services]:
        raise OSError("""Some required bluetooth attributes not found on this ble device. 
                         This means that either, you connected to a wrong device, 
                         or that your OS has a bug when reading BT LE device attributes (certain linux versions).""")
    time.sleep(1)
    if(args.pair):
        await writeNewPairingKey(examplePairingKey)
        print("Plase now restart omronpy without the -p flag.")
        bleClient.disconnect()
        exit(0)
    else:
        allRecs = await parseUserRecords()
        writeCsv(allRecs)
    #except Exception as e:
    #    print(f"Error occured:\n{type(e)}\n{e}")
    #finally:
    #    await bleClient.disconnect()

asyncio.run(main())
