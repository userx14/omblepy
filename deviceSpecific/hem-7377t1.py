import datetime
import logging
import sys

logger = logging.getLogger("omblepy")

sys.path.append('..')
from sharedDriver import sharedDeviceDriverCode


class deviceSpecificDriver(sharedDeviceDriverCode):
    """Driver for Omron BP5360 (HEM-7377T1-ZAZ).

    Same Omron HEM-7361T-family record format and same vendor service UUIDs
    as HEM-7380T1, but with a different memory layout (record area starts
    8 bytes into the user data region — a header precedes the records).

    Authentication: OS-managed BLE bond only. The device does NOT respond to
    omblepy's 0x02/0x00/0x01 key programming flow at all (verified across 20+
    attempts with various orderings). Pair through the OS BLE stack first
    (bluetoothctl on Linux, Settings on Windows), then read with this driver.

    Time sync: requires a non-obvious byte-14 counter increment quirk at
    EEPROM 0x0088 (returning 0xe5 / "Err" otherwise). Not implemented in this
    driver yet — run without -t / --timeSync. See PR description for details.
    """
    parentService_UUID         = "0000fe4a-0000-1000-8000-00805f9b34fb"
    deviceRxChannelUUIDs       = ["49123040-aee8-11e1-a74d-0002a5d5c51b"]
    deviceTxChannelUUIDs       = ["db5b55e0-aee7-11e1-965e-0002a5d5c51b"]
    requiresUnlock             = False
    supportsPairing            = False
    supportsOsBondingOnly      = True

    deviceEndianess            = "little"
    # Two user record slots, matching the HEM-7380T1 layout. NOTE: the slot
    # index here ("user 1" = first list element, "user 2" = second) may NOT
    # match the user labels on the cuff display. Empirically on one BP5360
    # sample, all of one user's measurements landed in slot index 1 (0x080C),
    # while slot index 0 (0x01CC) and probed addresses 0x0098 and 0x0E4C were
    # empty. Recommend: take a known measurement in each cuff user mode
    # (Guest / User 1 / User 2) and verify which CSV it lands in.
    userStartAdressesList      = [0x01CC, 0x080C]
    perUserRecordsCountList    = [100, 100]
    recordByteSize             = 0x10
    transmissionBlockSize      = 0x38

    settingsReadAddress        = None
    settingsWriteAddress       = None
    settingsUnreadRecordsBytes = None
    settingsTimeSyncBytes      = None

    def deviceSpecific_ParseRecordFormat(self, singleRecordAsByteArray):
        # HEM-7361T-family bit layout (BP5360 uses the same record format).
        recordDict = dict()
        minute = self._bytearrayBitsToInt(singleRecordAsByteArray, 68, 73)
        second = self._bytearrayBitsToInt(singleRecordAsByteArray, 74, 79)
        second = min([second, 59])  # field can range up to 63 in some records
        recordDict["mov"] = self._bytearrayBitsToInt(singleRecordAsByteArray, 80, 80)
        recordDict["ihb"] = self._bytearrayBitsToInt(singleRecordAsByteArray, 81, 81)
        month = self._bytearrayBitsToInt(singleRecordAsByteArray, 82, 85)
        day = self._bytearrayBitsToInt(singleRecordAsByteArray, 86, 90)
        hour = self._bytearrayBitsToInt(singleRecordAsByteArray, 91, 95)
        year = self._bytearrayBitsToInt(singleRecordAsByteArray, 98, 103) + 2000
        recordDict["bpm"] = self._bytearrayBitsToInt(singleRecordAsByteArray, 104, 111)
        recordDict["dia"] = self._bytearrayBitsToInt(singleRecordAsByteArray, 112, 119)
        recordDict["sys"] = self._bytearrayBitsToInt(singleRecordAsByteArray, 120, 127) + 25
        recordDict["datetime"] = datetime.datetime(year, month, day, hour, minute, second)
        return recordDict

    def deviceSpecific_syncWithSystemTime(self):
        raise ValueError(
            "BP5360 time sync requires a byte-14 counter increment quirk that "
            "isn't yet integrated into omblepy's settings-cache flow. "
            "Re-run without -t / --timeSync."
        )
