import sys
import datetime
import logging
logger = logging.getLogger("omblepy")

sys.path.append('..')
from sharedDriver import sharedDeviceDriverCode

class deviceSpecificDriver(sharedDeviceDriverCode):
    deviceEndianess                 = "little"
    userStartAdressesList           = [0x2e8]
    perUserRecordsCountList         = [90]
    recordByteSize                  = 0x0e
    transmissionBlockSize           = 0x10
    
    settingsReadAddress             = 0x0260
    settingsWriteAddress            = 0x02a4

    #settingsUnreadRecordsBytes      = [0x00, 0x10]
    #settingsTimeSyncBytes           = [0x2C, 0x3C]
    
    def deviceSpecific_ParseRecordFormat(self, singleRecordAsByteArray):
        print(singleRecordAsByteArray)
        """
        recordDict             = dict()
        minute                 = self._bytearrayBitsToInt(singleRecordAsByteArray, 68, 73)
        second                 = self._bytearrayBitsToInt(singleRecordAsByteArray, 74, 79)
        second                 = min([second, 59]) #for some reason the second value can range up to 63
        recordDict["mov"]      = self._bytearrayBitsToInt(singleRecordAsByteArray, 80, 80)
        recordDict["ihb"]      = self._bytearrayBitsToInt(singleRecordAsByteArray, 81, 81)
        month                  = self._bytearrayBitsToInt(singleRecordAsByteArray, 82, 85)
        day                    = self._bytearrayBitsToInt(singleRecordAsByteArray, 86, 90)
        hour                   = self._bytearrayBitsToInt(singleRecordAsByteArray, 91, 95)
        year                   = self._bytearrayBitsToInt(singleRecordAsByteArray, 98, 103) + 2000
        recordDict["bpm"]      = self._bytearrayBitsToInt(singleRecordAsByteArray, 104, 111)
        recordDict["dia"]      = self._bytearrayBitsToInt(singleRecordAsByteArray, 112, 119)
        recordDict["sys"]      = self._bytearrayBitsToInt(singleRecordAsByteArray, 120,  127) + 25
        recordDict["datetime"] = datetime.datetime(year, month, day, hour, minute, second)
        """
        return dict()
    
    def deviceSpecific_syncWithSystemTime(self):
        raise ValueError("not supported")