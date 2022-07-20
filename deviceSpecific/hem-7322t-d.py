import sys
import datetime
sys.path.append('..')
from utility import bytearrayBitsToIntBigEndian

recordSize = 0x0e
recordsStartAddress = 0x02ac
user1Entries = 100
user2Entries = 100

transmissionBlockSize = 0x38

unreadRecordsReadAddress  = 0x0260
unreadRecordsReadSize     = 0x08
unreadRecordsWriteAddress = 0x0286

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

async def getNewRecordReadCommands(btobj):
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
    readRecordsInfoByteArray = await btobj.readContinuousEepromData(unreadRecordsReadAddress, unreadRecordsReadSize)
    _unclear             = int(readRecordsInfoByteArray[0])
    lastWrittenSlotUser1 = int(readRecordsInfoByteArray[1])
    _unclear             = int(readRecordsInfoByteArray[2])
    lastWrittenSlotUser2 = int(readRecordsInfoByteArray[3])
    _unclear             = int(readRecordsInfoByteArray[4])
    unreadRecordsUser1   = int(readRecordsInfoByteArray[5])
    _unclear             = int(readRecordsInfoByteArray[6])
    unreadRecordsUser2   = int(readRecordsInfoByteArray[7])
    
    print(f"Current ring buffer slot user1: {lastWrittenSlotUser1}")
    print(f"Current ring buffer slot user2: {lastWrittenSlotUser2}")
    print(f"Unread records user1: {unreadRecordsUser1}")
    print(f"Unread records user1: {unreadRecordsUser2}")
    
    #get read commands
    u1Reads = calcRecordReadLocations(recordsStartAddress,                             unreadRecordsUser1, lastWrittenSlotUser1)
    u2Reads = calcRecordReadLocations(recordsStartAddress + user1Entries * recordSize, unreadRecordsUser2, lastWrittenSlotUser2)
    return u1Reads, u2Reads
    
    
async def getNewRecords(btobj, UseAndResetUnreadCounter):
    await btobj.unlockWithUnlockKey()
    await btobj.startTransmission()
    
    if(UseAndResetUnreadCounter):
        user1ReadCom, user2ReadCom = await getNewRecordReadCommands(btobj)
    else:
        user1ReadCom, user2ReadCom = await getAllRecordReadCommands(btobj)
    
    
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
    
    if(UseAndResetUnreadCounter):
        #reset entries unread records
        #special code for no new records is 0x8000
        readRecordsInfoByteArray = await btobj.readContinuousEepromData(unreadRecordsReadAddress, unreadRecordsReadSize)
        readRecordsInfoByteArray[4] = 0x80
        readRecordsInfoByteArray[5] = 0x00
        readRecordsInfoByteArray[6] = 0x80
        readRecordsInfoByteArray[7] = 0x00
        await btobj.writeContinuousEepromData(unreadRecordsWriteAddress, readRecordsInfoByteArray[:8], 0x08)
    
    #data transmission complete
    await btobj.endTransmission()
    
            
    user1ParsedRecordsList = list()
    user2ParsedRecordsList = list()
    for recordBytes in user1ByteRecords:
        if recordBytes != b'\xff' * recordSize:
            try:
                user1ParsedRecordsList.append(recordToDict(recordBytes))
            except:
                print(f"Error parsing record {recordBytes}, ignoring this record.")
    for recordBytes in user2ByteRecords:
        if recordBytes != b'\xff' * recordSize:
            try:
                user2ParsedRecordsList.append(recordToDict(recordBytes))
            except:
                print(f"Error parsing record {recordBytes}, ignoring this record.")
    return [user1ParsedRecordsList, user2ParsedRecordsList]


def recordToDict(recordBytes):
    recordDict = dict()
    recordDict["dia"]      = bytearrayBitsToIntBigEndian(recordBytes, 0,   7)
    recordDict["sys"]      = bytearrayBitsToIntBigEndian(recordBytes, 8,  15) + 25
    year                   = bytearrayBitsToIntBigEndian(recordBytes, 16, 23) + 2000
    recordDict["bpm"]      = bytearrayBitsToIntBigEndian(recordBytes, 24, 31)
    recordDict["mov"]      = bytearrayBitsToIntBigEndian(recordBytes, 32, 32)
    recordDict["ihb"]      = bytearrayBitsToIntBigEndian(recordBytes, 33, 33)
    month                  = bytearrayBitsToIntBigEndian(recordBytes, 34, 37)
    day                    = bytearrayBitsToIntBigEndian(recordBytes, 38, 42)
    hour                   = bytearrayBitsToIntBigEndian(recordBytes, 43, 47)
    minute                 = bytearrayBitsToIntBigEndian(recordBytes, 52, 57)
    second                 = bytearrayBitsToIntBigEndian(recordBytes, 58, 63)
    recordDict["datetime"] = datetime.datetime(year, month, day, hour, minute, second)
    return recordDict