import datetime
import logging
import sys

logger = logging.getLogger("omblepy")

sys.path.append('..')
from sharedDriver import sharedDeviceDriverCode


class deviceSpecificDriver(sharedDeviceDriverCode):
    """Driver for Omron X2 Smart (HEM-7143T2-ESL), read only.

    Same memory layout as the HEM-7146T (X2 Smart+) profile in UBPM and
    hass-omron: one user, 30 records of 14 bytes at 0x02E8, little-endian.
    Verified on a HEM-7143T2 with firmware SI.S01.16.02 against the device
    display.

    Authentication: OS-managed BLE bond only, no unlock key. macOS shows a
    pairing confirmation on first access.

    Record layout (bytes):
      0      sys - 25
      1      dia
      2      bpm
      3      year - 2000 (bits 0-5)
      4-5    LE word: hour 0-4, day 5-9, month 10-13, ihb 14, mov 15
      6-7    LE word: second 0-5, minute 6-11
      8-9    unknown
      10-11  sequence number, LE
      12     sum(bytes 0-11) & 0xFF
      13     byte 12 XOR 0xFF

    A second field of 63 marks a reading taken while the device clock was not
    set. Such records carry no usable time and
    are skipped.

    Time sync (-t) and the unread counter (-n) are not supported.
    """
    parentService_UUID         = "0000fe4a-0000-1000-8000-00805f9b34fb"
    deviceRxChannelUUIDs       = ["49123040-aee8-11e1-a74d-0002a5d5c51b"]
    deviceTxChannelUUIDs       = ["db5b55e0-aee7-11e1-965e-0002a5d5c51b"]
    requiresUnlock             = False
    supportsPairing            = False
    supportsOsBondingOnly      = True

    deviceEndianess            = "little"
    userStartAdressesList      = [0x02E8]
    perUserRecordsCountList    = [30]
    recordByteSize             = 0x0E
    transmissionBlockSize      = 0x2C

    settingsReadAddress        = 0x0260
    settingsWriteAddress       = 0x02A4
    settingsUnreadRecordsBytes = None
    settingsTimeSyncBytes      = None

    def deviceSpecific_ParseRecordFormat(self, singleRecordAsByteArray):
        record = bytes(singleRecordAsByteArray)
        checksum = sum(record[:12]) & 0xFF
        if record[12] != checksum or record[13] != checksum ^ 0xFF:
            raise ValueError("record checksum mismatch")

        word1 = record[4] | (record[5] << 8)
        word2 = record[6] | (record[7] << 8)
        second = word2 & 0x3F
        if second == 63:
            raise ValueError("clock not valid when the reading was taken")

        recordDict = dict()
        recordDict["sys"] = record[0] + 25
        recordDict["dia"] = record[1]
        recordDict["bpm"] = record[2]
        recordDict["ihb"] = (word1 >> 14) & 0x01
        recordDict["mov"] = (word1 >> 15) & 0x01
        recordDict["datetime"] = datetime.datetime(
            2000 + (record[3] & 0x3F),
            (word1 >> 10) & 0x0F,
            (word1 >> 5) & 0x1F,
            word1 & 0x1F,
            (word2 >> 6) & 0x3F,
            second,
        )
        return recordDict
