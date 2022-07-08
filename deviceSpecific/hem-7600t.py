import sys
import datetime
sys.path.append('..')
from utility import bytearrayBitsToInt

def recordSize():
    return 0x0e
def startAddress():
    return 0x02AC
def user1Entries():
    return 100
def user2Entries():
    return 0
    
def recordToDict(recordBytes):
    recordDict = dict()
    recordDict["dia"]      = bytearrayBitsToInt(recordBytes, 0,   7)
    recordDict["sys"]      = bytearrayBitsToInt(recordBytes, 8,  15) + 25
    year                   = bytearrayBitsToInt(recordBytes, 16, 23) + 2000
    recordDict["bpm"]      = bytearrayBitsToInt(recordBytes, 24, 31)
    recordDict["mov"]      = bytearrayBitsToInt(recordBytes, 32, 32)
    recordDict["ihb"]      = bytearrayBitsToInt(recordBytes, 33, 33)
    month                  = bytearrayBitsToInt(recordBytes, 34, 37)
    day                    = bytearrayBitsToInt(recordBytes, 38, 42)
    hour                   = bytearrayBitsToInt(recordBytes, 43, 47)
    minute                 = bytearrayBitsToInt(recordBytes, 52, 57)
    second                 = bytearrayBitsToInt(recordBytes, 58, 63)
    recordDict["datetime"] = datetime.datetime(year, month, day, hour, minute, second)
    return recordDict
