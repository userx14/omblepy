import sys
import datetime
import logging
logger = logging.getLogger("omblepy")

sys.path.append('..')
from sharedDriver import sharedDeviceDriverCode

class deviceSpecificDriver(sharedDeviceDriverCode):
    deviceEndianess                 = "big"
    userStartAdressesList           = [0x370, 0x8E8]
    perUserRecordsCountList         = [100  , 100  ]
    recordByteSize                  = 14
    settingsReadAddress             = 3956
    settingsWriteAddress            = 3994
    def deviceSpecific_ParseRecordFormat(self, singleRecordAsByteArray):
        logger.info(f"got {singleRecordAsByteArray}")
        """
        Code that parses the bitstream needs to be determined. 
        Might be simmilar to other big endian devices.
        Otherwise just compare bits to what the device / app displays.
        
        e.g.:
        recordDict             = dict()
        recordDict["dia"]      = self._bytearrayBitsToInt(singleRecordAsByteArray, 0, 7)
        ...
        ...
        return recordDict
        """
        
    def deviceSpecific_syncWithSystemTime(self):
        raise ValueError("Not supported yet.")