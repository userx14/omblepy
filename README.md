# Omblepy-bridge
Cli tool to read records from Omron Bluetooth-LE measurement instruments.
This version bypasses the os bluetooth stack by offloading the communication to an esp32 connected over usb serial.

## Advantages of this version
- os bluetooth stack not used, bypasses any bugs in os bluetooth implementation
- not affected by os updates

## Disadvantages of this version
- slower communication (at least 2x slower)
- need esp32 board connected to pc for operation
- additional one time setup work to programm the esp32 with arduino IDE
- less tested in general, write commands not tested
- usb serial on linux requires user to be added to group (dialout) or other changes to permissions in order to access /dev/ttyUSB0

## esp32 setup in arduino ide 2.0
1) add esp32 as additional board manager url
2) download esp32 by Espressiv Systems in board manager
3) install base64 library by Densaugeo version 1.3.0
4) select correct com-port, set core-debugging-level to None, and configure board specific options
5) upload the compiled sketch and close the serial monitor in the arduino ide, so the python script has access

## OS independent bridge script
First install latest python 3.x release.
Use the <a href="https://www.python.org/downloads/">official installer</a> and enable the "add to path option" in the installer. <br>
Then install the required libraries by opening a console window and executing the two commands:
| command  | library name | tested with library version |module use |
| -- | -- | -- | -- |
| `pip install pyserial` | <a href="https://pypi.org/project/pyserial/">pyserial</a> | v3.5 | serial communication |
| `pip install terminaltables` | <a href="https://pypi.org/project/terminaltables/">terminaltables</a> | v3.1.1 | formated command line output table for scanned devices |

On linux make sure the user has access to serial tty in /dev.

## Usage
For the first time pairing process you need to use the -p flag and enable pairing mode by holding the bluetooth button until you see the blinking -P- in the display: 
```
python ./omblepy_bridge.py -b COM3 -p -d HEM-7322T
```
Check arduino ide or device manager for correct COMX port on windows. On linux likely `-b /dev/ttyUSB0`.

After the first connection the -p flag can be omitted:
```
python ./omblepy_bridge.py -b COM3 -d HEM-7322T
```

## Esp32 serial commands documentation
| command example | description | return |
| -- | -- | -- |
| s  | scan bluetooth devices | json of scanned deviced |
| p aa:bb:00:dd:ee:ff   | pair with omron device with the following mac address | p OK |
| c aa:bb:00:dd:ee:ff    | connect with omron device with the following mac address | c OK |
| t base64stringTx        | send command to device for reading or writing | t base64stringRx (response from device) |
