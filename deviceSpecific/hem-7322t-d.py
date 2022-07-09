import sys
import datetime
sys.path.append('..')
from utility import bytearrayBitsToIntBigEndian

def recordSize():
    return 0x0e
def startAddress():
    return 0x02ac
def user1Entries():
    return 100
def user2Entries():
    return 100
    
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


async def resetUnreadRecordsCount(btobj):
    readRecordsInfoByteArray = await btobj.readContinuousEepromData(startAddress = 0x0260, bytesToRead = 0x08)
    print(f"got {bytes(readRecordsInfoByteArray).hex()}")
    _unclear           = bytearrayBitsToIntBigEndian(readRecordsInfoByteArray, 0, 7)   #probably indicated is user1 was last active
    currentSlotUser1   = bytearrayBitsToIntBigEndian(readRecordsInfoByteArray, 8, 15)
    _unclear           = bytearrayBitsToIntBigEndian(readRecordsInfoByteArray, 16, 23) #probably indicated is user2 was last active
    currentSlotUser2   = bytearrayBitsToIntBigEndian(readRecordsInfoByteArray, 24, 31)
    _unclear           = bytearrayBitsToIntBigEndian(readRecordsInfoByteArray, 32, 39)
    unreadRecordsUser1 = bytearrayBitsToIntBigEndian(readRecordsInfoByteArray, 40, 47)
    _unclear           = bytearrayBitsToIntBigEndian(readRecordsInfoByteArray, 48, 55)
    unreadRecordsUser2 = bytearrayBitsToIntBigEndian(readRecordsInfoByteArray, 56, 63)
    #special code for no new records
    
    print(f"Current ring buffer slot user1: {currentSlotUser1}")
    print(f"Current ring buffer slot user2: {currentSlotUser2}")
    print(f"Unread records user1: {unreadRecordsUser1}")
    print(f"Unread records user1: {unreadRecordsUser2}")
    
    #reset entries unread records
    readRecordsInfoByteArray[4] = 0x80
    readRecordsInfoByteArray[5] = 0x00
    readRecordsInfoByteArray[6] = 0x80
    readRecordsInfoByteArray[7] = 0x00
    await btobj.writeContinuousEepromData(startAddress = 0x0286, bytesArrayToWrite = readRecordsInfoByteArray)
    return 
