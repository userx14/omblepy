# Omblepy
Cli tool to read records from Omron Bluetooth-LE measurement instruments


## Windows setup
First install latest python 3.x release.
Use the <a href="https://www.python.org/downloads/">official installer</a> and enable the "add to path option" in the installer. <br>
Then install the required libraries by opening a console window and executing the two commands:
| command  | library name | tested with library version |module use |
| -- | -- | -- | -- |
| `pip install bleak` | <a href="https://pypi.org/project/bleak/">bleak</a> | v0.18.1 | bluetooth-le communication |
| `pip install terminaltables` | <a href="https://pypi.org/project/terminaltables/">terminaltables</a> | v3.1.1 | formated command line output table for scanned devices |

## Linux setup
Install python ( ≥ version 3.8) and the two required libraries:
```
apt install python3.10
pip3 install bleak
pip3 install terminaltables
```

## Windows Usage
For the first time pairing process you need to use the -p flag and enable pairing mode by holding the bluetooth button until you see the blinking -P- in the display: 
```
python ./omblepy.py -p -d HEM-7322T
```

After the first connection the -p flag can be omitted, even when executing omblepy on a different device:
```
python ./omblepy.py -d HEM-7322T
```
## Linux Usage
(same as Windows usage, but python command is different)
```
python3 ./omblepy.py -p -d HEM-7322T
```
```
python3 ./omblepy.py -d HEM-7322T
```
### Pairing for UBPM
If you preform this pairing for <a href="https://codeberg.org/LazyT/ubpm/">ubpm</a>, just use one of the supported devices (e.g. `-d HEM-7322T`), even if your device model is different. As far as I know the pairing process is simmilar for all omron devices. If you use an unsupported device it is expected that the pairing will work and that the -P- on the display of the omron device will change to a small square. But the tool will crash futher in the readout, because the data format / readout commands for the stored records are different. Nevertheless your omron device is now bound to the mac address of your pc and ubpm should work without mac address spoofing. <br>
If you see the message "Could not enter key programming mode." or "Failure to programm new key." the pairing procedure did NOT work. Please see the troubleshooting section and if the problem persists please open an issue. <br>
Success is indicated by the message "Paired device successfully with new key".

### Flags table
| flag  | alternative long flag  | always required | required on first connection | potentialy dangerous eeprom write | description | usage example | 
| ----- | ----- | ----- | ----- | ----- | ----- | ----- |
| `-h`  | `--help` | - | - | - | display help for all possible flags, similar to this table | `python3 ./omblepy.py -h` |
| `-d`  | `--device` |✔️ | ✔️ | - | select which device libary will be loaded | `python3 ./omblepy.py -d HEM-7322T` |
| `-p`  | `--pair` | ❌ | ✔️ | - | use to write pairing key on first connection with this pc | `python3 ./omblepy.py -d HEM-7322T -p` |
| `-m`  | `--mac` |❌ | ❌ | - | select omron devices mac and skip bluetooth scan and device selection dialog | `python3 ./omblepy.py -d HEM-7322T -m 11:22:33:44:55:66` |
| `-n`  | `--newRecOnly` | ❌ | ❌ | ❗ | instead of downloading all records, check and update the "new records couter" and only transfer new records | `python3 ./omblepy.py -d HEM-7322T -n` |
| `-t`  | `--timeSync` | ❌ | ❌ | ❗ | synchronize omron internal clock with system time | `python3 ./omblepy.py -d HEM-7322T -t` |
|  |`--loggerDebug`  | ❌ | ❌ | - | displays every ingoing and outgoing data for debugging purposes | `python3 ./omblepy.py -d HEM-7322T --loggerDebug` |

Potentialy dangerous, referes to the possibility to mess up the calibration data for the pressure sensor, which is likely stored in the eeprom in the settings region.<br>
This is most important when you are trying to add support for a new device.

## Omron device support matrix
| device model | sold under name |  pairing | basic data readout | new record counter | time sync | contributors / testers / help by | 
| ----- | ----- | ----- | ----- | ----- | ----- | ----- |
| [HEM-7322T](deviceSpecific/hem-7322t.py) | M700 Intelli IT 				  	| ✔️ | ✔️ | ✔️ | ✔️ | userx14 				  	          |
| [HEM-7361T](deviceSpecific/hem-7361t.py) | M500 Intelli IT / M7 Intelli IT 	| ✔️ | ✔️ | ✔️ | ✔ | LazyT, userx14, zivanfi 	|
| [HEM-7600T](deviceSpecific/hem-7600t.py) | Omron Evolv 				      	| ✔️ | ✔️ | ✔️ | ✔️ | vulcainman 				            |
| [HEM-7155T](deviceSpecific/hem-7155t.py) | M400  				      	      | ✔️ | ✔️ | ✔️ | ✔️ | dromie 				                |

✔️=tested working, ❓=not tested , ❌=not supported yet <br>

Please open an issue if you can test a feature or an currently unsupported device. <br>
It is potentially dangerous to write to the eeprom on devices where the eeprom layout is unknown (see Flags table), <br>
since the calibration data for the pressure sensor is likeley also stored there.

## Troubleshooting
- Remove the pairing with the omron device using your os bluetooth dialog.
- Use a bluetooth chipset/dongle which supports at least bluetooth 4.2, better 5.0
- On the devices I had avilable for testing, win10 did always work, while ubuntu didn't work on some versions.
- If the pairing works and there is an error in the readout use the `--loggerDebug` flag and please open an issue.
- Windows specific
  - Do not use the CSR harmony stack (CSR 8510 based usb dongles), it is incompatible.
- Linux specific
  - Preferably test on a device with only one bluetooth adapter connected.
  - Restart the bluetooth stack `sudo systemctl restart bluetooth`.
  - Delete the bluetooth adapter cache with `sudo rm -r /var/lib/bluetooth/$yourBtCardMacAddress`.
  - If you have two bluetooth adapters in your system, open a second terminal alongside omblepy and use `bluetoothctl` to confirm pairing dialogs by typing `yes` when promped, some graphical interfaces will not show the pairing dialog for the second adapter.
  - When you are on ubuntu, install blueman, since it seems to be designed with multiple adapters in mind.
  - Try other versions of bluez, for me versions around bluez 5.55 worked best.


## Documentation 
The general communication is handled in the first 250 lines of [omblepy.py](./omblepy.py).

### command types (bytes 1-3 of header):
PC -> omron device
 command type bytes | function | packet size 
 --- | --- | ---
`0000` | start of transmission / read device id from eeprom | 0x08 bytes with checksum
`0100` | read data from eeprom | 0x08 bytes with checksum
`01c0` | write data to eeprom | 0x08 bytes + sizeof(data to write)
`0f00` | end of transmission | 0x08 bytes

omron device -> PC
response type bytes | function | packet size
 --- | --- | ---
`8000` | response start transmission | 0x18 bytes with checksum
`8100` | response read data | 0x08 bytes + sizeof(attached data read from eeprom)
`81c0` | response write data | same size as corresponding write command
`8f00` | response end transmission | 0x08 bytes

### Packet header for reads:
Example message sent to request a read of 0x26 bytes starting from address 0x0260:
messagelength | command type      | start address | readsize | padding     | crc, such that all bytes xored = 0
---           | ---               | ---           | ---      | ---         | ---
0x08          | 0x0100            | 0x0260        | 0x26     | 0x00        | 0x4d


## Related Projects
A huge thank you goes to LazyT and his <a href=https://codeberg.org/LazyT/ubpm>UBPM project</a>
which provided extremely usefull insight how the reception with multiple bluetooth channels works.
