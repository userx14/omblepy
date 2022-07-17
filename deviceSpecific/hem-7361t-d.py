import sys
import datetime
sys.path.append('..')
from utility import bytearrayBitsToIntLittleEndian

recordSize = 0x10
recordsStartAddress = 0x98
user1Entries = 100
user2Entries = 100

transmissionBlockSize = 0x10

unreadRecordsReadAddress  = 0x0010
unreadRecordsReadSize     = 0x10
unreadRecordsWriteAddress = 0x0054

def calcRecordReadLocations(userStartAddr, unreadRecords, lastWrittenSlot):
    userReadQueue = []
    if(lastWrittenSlot < unreadRecords): #two reads neccesary, because ring buffer start reached
        #read start of ring buffer
        firstRead = dict()
        firstRead["address"] = userStartAddr
        firstRead["size"]    = recordSize * lastWrittenSlot
        userReadQueue.append(firstRead)
        
        #read end of ring buffer
        secondRead = dict()
        secondRead["address"] = userStartAddr
        secondRead["address"] += (user1Entries + lastWrittenSlot - unreadRecords) * recordSize
        secondRead["size"]    = recordSize * (unreadRecords - lastWrittenSlot)
        userReadQueue.append(secondRead)
    else:
        #read start of ring buffer
        firstRead = dict()
        firstRead["address"] = userStartAddr
        firstRead["address"] += recordSize * (lastWrittenSlot - unreadRecords)
        firstRead["size"]    = recordSize * unreadRecords
        userReadQueue.append(firstRead)
    return userReadQueue
    

async def getAllRecordReadCommands(btobj):
    u1Reads = []
    firstRead = dict()
    firstRead["address"] = recordsStartAddress
    firstRead["size"] = recordSize * user1Entries
    u1Reads.append(firstRead)
    
    u2Reads = []
    firstRead = dict()
    firstRead["address"] = recordsStartAddress + recordSize * user1Entries
    firstRead["size"] = recordSize * user2Entries
    u2Reads.append(firstRead)
    return u1Reads, u2Reads

async def getNewRecordReadCommandsAndResetCounter(btobj):
    readRecordsInfoByteArray = await btobj.readContinuousEepromData(unreadRecordsReadAddress, unreadRecordsReadSize)
    lastWrittenSlotUser1 = int(readRecordsInfoByteArray[0]) #0-99, when device is initialized, slot 1 is the first one used
    _unclear             = int(readRecordsInfoByteArray[1])
    lastWrittenSlotUser2 = int(readRecordsInfoByteArray[2])
    _unclear             = int(readRecordsInfoByteArray[3])
    unreadRecordsUser1   = int(readRecordsInfoByteArray[4])
    _unclear             = int(readRecordsInfoByteArray[5])
    unreadRecordsUser2   = int(readRecordsInfoByteArray[6])
    _unclear             = int(readRecordsInfoByteArray[7])
    
    print(f"Current ring buffer slot user1: {lastWrittenSlotUser1}")
    print(f"Current ring buffer slot user2: {lastWrittenSlotUser2}")
    print(f"Unread records user1: {unreadRecordsUser1}")
    print(f"Unread records user1: {unreadRecordsUser2}")
    
    #get read commands
    u1Reads = calcRecordReadLocations(recordsStartAddress,                             unreadRecordsUser1, lastWrittenSlotUser1)
    u2Reads = calcRecordReadLocations(recordsStartAddress + user1Entries * recordSize, unreadRecordsUser2, lastWrittenSlotUser2)
    return u1Reads, u2Reads
    
    
async def getNewRecordsDoResetUnreadCounter(btobj):
    btobj.unlockWithUnlockKey()
    await btobj.startTransmission()
    
    user1ReadCom, user2ReadCom = await getNewRecordReadCommandsAndResetCounter(btobj)
    
    #process user1
    user1ByteRecords = bytearray()
    for readCom in user1ReadCom:
        user1ByteRecords += await btobj.readContinuousEepromData(readCom["address"], readCom["size"], transmissionBlockSize)
    user1ByteRecords = [user1ByteRecords[recordStartPos:recordStartPos+recordSize] for recordStartPos in range(0, len(user1ByteRecords), recordSize)]

    #process user2
    user2ByteRecords = bytearray()
    for readCom in user2ReadCom:
        user2ByteRecords += await btobj.readContinuousEepromData(readCom["address"], readCom["size"], transmissionBlockSize)
    user2ByteRecords = [user2ByteRecords[recordStartPos:recordStartPos+recordSize] for recordStartPos in range(0, len(user2ByteRecords), recordSize)]
    
    #reset entries unread records
    #special code for no new records is 0x8000
    readRecordsInfoByteArray = await btobj.readContinuousEepromData(unreadRecordsReadAddress, unreadRecordsReadSize)
    readRecordsInfoByteArray[4] = 0x00
    readRecordsInfoByteArray[5] = 0x80
    readRecordsInfoByteArray[6] = 0x00
    readRecordsInfoByteArray[7] = 0x80
    await btobj.writeContinuousEepromData(unreadRecordsWriteAddress, readRecordsInfoByteArray[:8], 0x08)
    
    #data transmission complete
    await btobj.endTransmission()
    
            
    user1ParsedRecordsList = list()
    user2ParsedRecordsList = list()
    for recordBytes in user1ByteRecords:
        user1ParsedRecordsList.append(recordToDict(recordBytes))
    for recordBytes in user2ByteRecords:
        user2ParsedRecordsList.append(recordToDict(recordBytes))
    
    user1ParsedRecordsList = sorted(user1ParsedRecordsList, key = lambda x: x["datetime"])
    user2ParsedRecordsList = sorted(user2ParsedRecordsList, key = lambda x: x["datetime"])
    
    return [user1ParsedRecordsList, user2ParsedRecordsList]

async def getAllRecordsDoNotResetUnreadCounter(btobj):
    btobj.unlockWithUnlockKey()
    await btobj.startTransmission()
    
    user1ReadCom, user2ReadCom = await getAllRecordReadCommands(btobj)
    
    #process user1
    user1ByteRecords = bytearray()
    for readCom in user1ReadCom:
        user1ByteRecords += await btobj.readContinuousEepromData(readCom["address"], readCom["size"], recordSize)   #must be recordSize instead of rxMaxBlockSize here, because if one reads into non existing records the device will reply invalid -> 0xff for the whole block
    user1ByteRecords = [user1ByteRecords[recordStartPos:recordStartPos+recordSize] for recordStartPos in range(0, len(user1ByteRecords), recordSize)]

    #process user2
    user2ByteRecords = bytearray()
    for readCom in user2ReadCom:
        user2ByteRecords += await btobj.readContinuousEepromData(readCom["address"], readCom["size"], recordSize)
    user2ByteRecords = [user2ByteRecords[recordStartPos:recordStartPos+recordSize] for recordStartPos in range(0, len(user2ByteRecords), recordSize)]
    
    #data transmission complete
    await btobj.endTransmission()
    
            
    user1ParsedRecordsList = list()
    user2ParsedRecordsList = list()
    for recordBytes in user1ByteRecords:
        if recordBytes != b'\xff' * recordSize:
            user1ParsedRecordsList.append(recordToDict(recordBytes))
    for recordBytes in user2ByteRecords:
        if recordBytes != b'\xff' * recordSize:
            user2ParsedRecordsList.append(recordToDict(recordBytes))
    return [user1ParsedRecordsList, user2ParsedRecordsList]


def recordToDict(recordBytes):
    print(f"recordToDict {recordBytes}")
    recordDict = dict()
    minute                 = bytearrayBitsToIntLittleEndian(recordBytes, 68, 73)
    second                 = bytearrayBitsToIntLittleEndian(recordBytes, 74, 79)
    recordDict["mov"]      = bytearrayBitsToIntLittleEndian(recordBytes, 80, 80)
    recordDict["ihb"]      = bytearrayBitsToIntLittleEndian(recordBytes, 81, 81)
    month                  = bytearrayBitsToIntLittleEndian(recordBytes, 82, 85)
    day                    = bytearrayBitsToIntLittleEndian(recordBytes, 86, 90)
    hour                   = bytearrayBitsToIntLittleEndian(recordBytes, 91, 95)
    year                   = bytearrayBitsToIntLittleEndian(recordBytes, 98, 103) + 2000
    recordDict["bpm"]      = bytearrayBitsToIntLittleEndian(recordBytes, 104, 111)
    recordDict["dia"]      = bytearrayBitsToIntLittleEndian(recordBytes, 112, 119)
    recordDict["sys"]      = bytearrayBitsToIntLittleEndian(recordBytes, 120,  127) + 25
    
    recordDict["datetime"] = datetime.datetime(year, month, day, hour, minute, second)
    return recordDict
