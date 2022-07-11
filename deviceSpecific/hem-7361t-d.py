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
