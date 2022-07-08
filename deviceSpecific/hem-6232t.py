import sys
import datetime
sys.path.append('..')
from utility import bytearrayBitsToIntBigEndian

def recordSize():
    return 0x0e
def startAddress():
    return 0x02E8
def user1Entries():
    return 100
def user2Entries():
    return 100
    
def recordToDict(recordBytes):
    recordDict = dict()
    recordDict["dia"]      = bytearrayBitsToIntBigEndian(recordBytes, 0,   7)
    recordDict["sys"]      = bytearrayBitsToIntBigEndian(recordBytes, 8,  15) + 25
    year                   = bytearrayBitsToIntBigEndian(recordBytes, 18, 23) + 2000
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
