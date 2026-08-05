"""Omron BP4350 (Gold Wrist) — sold in the US as HEM-6232T-Z.

The trailing market letter does not change the BLE protocol, EEPROM
layout or record format (confirmed by maintainer and verified against
raw EEPROM dumps from hardware), so this is a thin alias for the
existing HEM-6232T driver. The device does require an active BLE bond
before Omron key programming succeeds; needsSmpAgent opts in to the
Linux BlueZ bonding agent (used when pairing with --bond).
"""

hem6232t = __import__("hem-6232t")


class deviceSpecificDriver(hem6232t.deviceSpecificDriver):
    needsSmpAgent = True
