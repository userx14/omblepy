import sys
import datetime
sys.path.append('..')
from utility import bytearrayBitsToIntLittleEndian

def recordSize():
    return 0x10
def startAddress():
    return 0x98
def user1Entries():
    return 100
def user2Entries():
    return 100

def recordToDict(recordBytes):
    recordDict = dict()
    minute                 = bytearrayBitsToIntBigEndian(recordBytes, 68, 73)
    second                 = bytearrayBitsToIntBigEndian(recordBytes, 74, 79)
    recordDict["mov"]      = bytearrayBitsToIntBigEndian(recordBytes, 80, 80)
    recordDict["ihb"]      = bytearrayBitsToIntBigEndian(recordBytes, 81, 81)
    month                  = bytearrayBitsToIntBigEndian(recordBytes, 82, 85)
    day                    = bytearrayBitsToIntBigEndian(recordBytes, 86, 90)
    hour                   = bytearrayBitsToIntBigEndian(recordBytes, 91, 95)
    year                   = bytearrayBitsToIntBigEndian(recordBytes, 98, 103) + 2000
    recordDict["bpm"]      = bytearrayBitsToIntBigEndian(recordBytes, 104, 111)
    recordDict["dia"]      = bytearrayBitsToIntBigEndian(recordBytes, 112, 119)
    recordDict["sys"]      = bytearrayBitsToIntBigEndian(recordBytes, 120,  127) + 25
    
    recordDict["datetime"] = datetime.datetime(year, month, day, hour, minute, second)
    return recordDict
