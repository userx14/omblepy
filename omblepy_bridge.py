import asyncio                                                      #avoid wait on bluetooth stack stalling the application
import terminaltables                                               #for pretty selection table for ble devices
import serial                                                       #communication with esp32
import base64 
import re                                                           #regex to match bt mac address
import argparse                                                     #to process command line arguments
import datetime
import sys
import pathlib
import logging
import csv
import json
import time


#global variables
deviceSpecific      = None                            #imported module for each device
logger              = logging.getLogger("omblepy")
ser                 = None

def convertByteArrayToHexString(array):
    return (bytes(array).hex())


class bluetoothTxRxHandler:
    
    def __init__(self, ser, pairing = False):
        self.rxEepromAddress            = None
        self.ser                        = ser
        
    async def _waitForRxOrRetry(self, command, timeoutS = 1.0):
        command = "t ".encode()+base64.b64encode(command)
        ser.write(command)
        print(f"command {command}")
        #check crc
        combinedRawRx   = ser.readline()
        combinedRawRx   = base64.b64decode(combinedRawRx[2:])
        print(f"response {combinedRawRx}")
        self.packetSize = combinedRawRx[0]
        combinedRawRx   = combinedRawRx[:self.packetSize]          #cut extra bytes from the end
        xorCrc = 0
        for byte in combinedRawRx:
            xorCrc ^= byte
        if(xorCrc):
            raise ValueError(f"data corruption in rx\ncrc: {xorCrc}\ncombniedBuffer: {convertByteArrayToHexString(combinedRawRx)}")
            return
        #extract information
        self.rxPacketType       = combinedRawRx[1:3]
        self.rxEepromAddress    = combinedRawRx[3:5]
        expectedNumDataBytes    = combinedRawRx[5]
        if(expectedNumDataBytes > (len(combinedRawRx) - 8)):
            self.rxDataBytes    = bytes(b'\xff') * expectedNumDataBytes
        else:
            if(self.rxPacketType) == bytearray.fromhex("8f00"): #need special case for end of transmission packet, otherwise transmission error code is not accessible
                self.rxDataBytes = combinedRawRx[6:7]
            else:
                self.rxDataBytes    = combinedRawRx[6: 6 + expectedNumDataBytes]
    
    async def startTransmission(self):
        startDataReadout    = bytearray.fromhex("0800000000100018")
        await self._waitForRxOrRetry(startDataReadout)
        if(self.rxPacketType != bytearray.fromhex("8000")):
            raise ValueError("invalid response to data readout start")
                
    async def endTransmission(self):
        stopDataReadout         = bytearray.fromhex("080f000000000007")
        await self._waitForRxOrRetry(stopDataReadout)
        if(self.rxPacketType != bytearray.fromhex("8f00")):
            raise ValueError("invlid response to data readout end")
            return
        if(self.rxDataBytes[0]):
            raise ValueError(f"Device reported error status code {self.rxDataBytes[0]} while sending endTransmission command.")
            return
    
    async def _writeBlockEeprom(self, address, dataByteArray):
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
    
    async def writeContinuousEepromData(self, startAddress, bytesArrayToWrite, btBlockSize = 0x08):
        while(len(bytesArrayToWrite) != 0):
            nextSubblockSize = min(len(bytesArrayToWrite), btBlockSize)
            logger.debug(f"write to {hex(startAddress)} size {hex(nextSubblockSize)}")
            await self._writeBlockEeprom(startAddress, bytesArrayToWrite[:nextSubblockSize])
            bytesArrayToWrite = bytesArrayToWrite[nextSubblockSize:]
            startAddress += nextSubblockSize
        return
    
    async def readContinuousEepromData(self, startAddress, bytesToRead, btBlockSize = 0x10):
        eepromBytesData = bytearray()
        while(bytesToRead != 0):
            nextSubblockSize = min(bytesToRead, btBlockSize)
            logger.debug(f"read from {hex(startAddress)} size {hex(nextSubblockSize)}")
            eepromBytesData += await self._readBlockEeprom(startAddress, nextSubblockSize)
            startAddress    += nextSubblockSize
            bytesToRead     -= nextSubblockSize
        return eepromBytesData
    async def unlockWithUnlockKey(key=None):
        pass #already done by the connect command on the esp32

    

def readCsv(filename):
    records = []
    with open(filename, mode='r', newline='', encoding='utf-8') as infile:
        reader = csv.DictReader(infile)
        for oldRecordDict in reader:
            oldRecordDict["datetime"] = datetime.datetime.strptime(oldRecordDict["datetime"], "%Y-%m-%d %H:%M:%S")
            records.append(oldRecordDict)
    return records

def appendCsv(allRecords):
    for userIdx in range(len(allRecords)):
        oldCsvFile = pathlib.Path(f"user{userIdx+1}.csv")
        dateText = datetime.datetime.now().strftime('%Y_%m_%d__%H_%M_%S')
        backup = pathlib.Path(f"backup_user{userIdx+1}_{dateText}.csv")
        datesOfNewRecords = [record["datetime"] for record in allRecords[userIdx]]
        if(oldCsvFile.is_file()):
            backup.write_bytes(oldCsvFile.read_bytes())
            records = readCsv(f"user{userIdx+1}.csv")
            allRecords[userIdx].extend(filter(lambda x: x["datetime"] not in datesOfNewRecords,records))
        allRecords[userIdx] = sorted(allRecords[userIdx], key = lambda x: x["datetime"])
        logger.info(f"writing data to user{userIdx+1}.csv")
        with open(f"user{userIdx+1}.csv", mode='w', newline='', encoding='utf-8') as outfile:
            writer = csv.DictWriter(outfile, fieldnames = ["datetime", "dia", "sys", "bpm", "mov", "ihb"])
            writer.writeheader()
            for recordDict in allRecords[userIdx]:
                recordDict["datetime"] = recordDict["datetime"].strftime("%Y-%m-%d %H:%M:%S")
                writer.writerow(recordDict)

def saveUBPMJson(allRecords):
    f = pathlib.Path(f"ubpm.json")
    UBPM = {}
    UBPM["UBPM"] = {}
    for userIdx in range(len(allRecords)):
        UBPM["UBPM"][f"U{userIdx+1}"] = []
        for rec in allRecords[userIdx]:
            recdate=datetime.datetime.strptime(rec["datetime"], "%Y-%m-%d %H:%M:%S")
            UBPM["UBPM"][f"U{userIdx+1}"].append({
                                "date": recdate.strftime("%d.%m.%Y"),
                                'time': recdate.strftime("%H:%M:%S"), 'msg': "",
                                'sys': int(rec['sys']), 'dia': int(rec['dia']), 'bpm': int(rec['bpm']), 'ihb': int(rec['ihb']), 'mov': int(rec['mov']) })
    f.write_text(json.dumps(UBPM, indent=4, sort_keys=True, default=str))

async def selectBLEdevices():
    while True:
        ser.write("s".encode())
        scanResult = ser.readline()
        if scanResult:
            scanResult = json.loads(scanResult[2:])
            scanResult = sorted(scanResult, key = lambda x: x["rssi"], reverse=True)
        tableEntries = []
        tableEntries.append(["ID", "MAC", "NAME", "RSSI"])
        for resIdx,scanRes in enumerate(scanResult):
            tableEntries.append([resIdx, scanRes["mac"], scanRes["name"], scanRes["rssi"]])
        print(terminaltables.AsciiTable(tableEntries).table)
        res = input("Enter ID or just press Enter to rescan.\n")
        if(res.isdigit() and int(res) in range(len(scanResult))):
            break            
    return scanResult[int(res)]["mac"]



async def main():
    global bleClient
    global deviceSpecific    
    parser = argparse.ArgumentParser(description="python tool to read the records of omron blood pressure instruments")
    parser.add_argument('-d', "--device",     required="true", type=ascii,  help="Device name (e.g. HEM-7322T-D).")
    parser.add_argument("--loggerDebug",      action="store_true",          help="Enable verbose logger output")
    parser.add_argument("-p", "--pair",       action="store_true",          help="Programm the pairing key into the device. Needs to be done only once.")
    parser.add_argument("-m", "--mac",                          type=ascii, help="Bluetooth Mac address of the device (e.g. 00:1b:63:84:45:e6). If not specified, will scan for devices and display a selection dialog.")
    parser.add_argument('-n', "--newRecOnly", action="store_true",          help="Considers the unread records counter and only reads new records. Resets these counters afterwards. If not enabled, all records are read and the unread counters are not cleared.")
    parser.add_argument('-t', "--timeSync",   action="store_true",          help="Update the time on the omron device by using the current system time.")
    parser.add_argument('-b', "--bridgeDev",  required="true", type=ascii,  help="device location of esp32 serial on system (com-port or /dev path)")
    args = parser.parse_args()
    
    #setup logging
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    if(args.loggerDebug):
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.INFO)
    
    #import device specific module
    if(not args.pair and not args.device):
        raise ValueError("When not in pairing mode, please specify your device type name with -d or --device")
        return
    if(args.device):
        deviceName = args.device.strip("'").strip('\"') #strip quotes around arg
        sys.path.insert(0, "./deviceSpecific")
        try:
            logger.info(f"Attempt to import module for device {deviceName.lower()}")
            deviceSpecific = __import__(deviceName.lower())
        except ImportError:
            raise ValueError("the device is no supported yet, you can help by contributing :)")
            return
    
    #start serial communication
    global ser    
    ser = serial.Serial("COM4", 115200, timeout=10)
    
    #select device mac address
    validMacRegex = re.compile(r"^([0-9a-fA-F]{2}[:-]){5}([0-9a-fA-F]{2})$")  
    if(args.mac is not None):
        btmac = args.mac.strip("'").strip('\"') #strip quotes around arg
        if(validMacRegex.match(btmac) is None):
            raise ValueError(f"argument after -m or --mac {btmac} is not a valid mac address")
            return
        bleAddr = btmac
    else:
        print("To improve your chance of a successful connection please do the following:")
        print(" -remove previous device pairings in your OS's bluetooth dialog")
        print(" -enable bluetooth on you omron device and use the specified mode (pairing or normal)")
        print(" -do not accept any pairing dialog until you selected your device in the following list\n")
        bleAddr = await selectBLEdevices()
    
    
    try:
        logger.info(f"Attempt connecting to {bleAddr}.")
        bluetoothTxRxObj = bluetoothTxRxHandler(ser)
        if(args.pair):
            
            ser.write(f"p {bleAddr}".encode())
            response = ser.readline()
            if(response!=b"p OK\n"):
                raise ValueError(f"pairing failed {response}")
            
            #this seems to be neccesary when the device has not been paired to any device
            await bluetoothTxRxObj.startTransmission()
            await bluetoothTxRxObj.endTransmission()
        else:
            logger.info("communication started")
            ser.write(f"c {bleAddr}".encode())
            response = ser.readline()
            if(response!=b"c OK\n"):
                raise ValueError(f"connection failed {response}")
            
            devSpecificDriver = deviceSpecific.deviceSpecificDriver()
            allRecs = await devSpecificDriver.getRecords(btobj = bluetoothTxRxObj, useUnreadCounter = args.newRecOnly, syncTime = args.timeSync)
            logger.info("communication finished")
            appendCsv(allRecs)
            saveUBPMJson(allRecs)
    finally:
        logger.info("unpair and disconnect")

asyncio.run(main())
