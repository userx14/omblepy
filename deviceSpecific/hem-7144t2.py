import sys
import datetime
import logging
logger = logging.getLogger("omblepy")

sys.path.append('..')
from sharedDriver import sharedDeviceDriverCode

class deviceSpecificDriver(sharedDeviceDriverCode):
    deviceEndianess           = "big"
    userStartAdressesList     = [0x2e8]
    perUserRecordsCountList   = [30]
    recordByteSize            = 0x0e
    transmissionBlockSize     = 0x38
    settingsReadAddress       = 0x260
    #settingsWriteAddress            = 0x0286
    #AsettingsUnreadRecordsBytes      = [0x00, 0x08]
    #AsettingsTimeSyncBytes           = [0x14, 0x1e]

    def deviceSpecific_ParseRecordFormat(self, singleRecordAsByteArray):
        recordDict             = dict()
        recordDict["sys"]      = self._bytearrayBitsToInt(singleRecordAsByteArray, 0, 7) + 25
        recordDict["dia"]      = self._bytearrayBitsToInt(singleRecordAsByteArray, 8, 15)
        recordDict["bpm"]      = self._bytearrayBitsToInt(singleRecordAsByteArray, 16, 23)
        year                   = self._bytearrayBitsToInt(singleRecordAsByteArray, 24, 31) + 2000
        month                  = self._bytearrayBitsToInt(singleRecordAsByteArray, 32, 35)
        day                    = self._bytearrayBitsToInt(singleRecordAsByteArray, 36, 40)
        hour                   = self._bytearrayBitsToInt(singleRecordAsByteArray, 41, 45)
        minute                 = self._bytearrayBitsToInt(singleRecordAsByteArray, 50, 55)
        second                 = self._bytearrayBitsToInt(singleRecordAsByteArray, 56, 61)
        second                 = min([second, 59])
        recordDict["datetime"] = datetime.datetime(year, month, day, hour, minute, second)
        return recordDict

    def deviceSpecific_syncWithSystemTime(self):
        raise ValueError("Not supported yet.")