# omblepy
Cli tool to read records from Omron Bluetooth-LE measurement instruments


## Initial setup
First install python in version 3.8 or preferably a more recent one. <br>
Use the official installer on windows or on linux use:<br>
```
apt install python3.10
```

Install the two required modules 'bleak' for bluetooth communication and 'terminaltables' for command line output formatting. <br>
```
pip3 install terminaltables
pip3 install bleak
```

## Usage examples
The tool provides a build-in help, which can be accesses like so:
```
python3 ./omblepy.py -h
```
### Pairing
Start the omron instrument in pairing mode, then execute the following to write the custom pairing key:
```
python3 ./omblepy.py -p
```
This only needs to be done once, even connecting using different PCs with different Bluetooth Mac Addresses should work fine from now on.
### Normal connection
Start the omron instrument in it's normal bluetooth connection mode, execute the commands below to export all stored data records into csv files in the current directory.
#### With selection dialog for device
```
python3 ./omblepy.py -d HEM-7322T-D
```
#### With predefined bluetooth mac
```
python3 ./omblepy.py -d HEM-7322T-D -m D3:07:19:08:27:00
```

## Adding Support for new devices
The device specific configuration is stored in a per device file. 
Feel free to contribute to bring support to more devices.

## Troubleshooting
- remove the pairing with the device using your os bluetooth dialog
### Linux specific
- restart the bluetooth stack `sudo systemctl restart bluetooth`
- delete the bluetooth adapter cache with `sudo rm -r /var/lib/bluetooth/$yourBtCardMacAddress`
- open a second terminal and use `bluetoothctl` to confirm pairing dialogs by typing `yes` when promped, 
  this is most important when you have two bluetooth adapters, since some graphical interfaces will not show the pairing dialog in this case
- try distributions with other versions of bluez, for me versions around bluez 5.55 worked best


## Documentation 

### Packet format for memory read

Example message sent to request data read from specific address:

messagelength | command type      | start address | readsize | padding     | crc with xor
---           | ---               | ---           | ---      | ---         | ---
10            | 80 00             | 02 60         | 26       | 00          | 4d
in bytes      | read from address | in bytes      | in bytes | 1byte zero  | all bytes xored = zero

## Thanks / Related Projects
A huge thank you goes to lazyT and his UBPM project, see:
https://codeberg.org/LazyT/ubpm
which provided extremely usefull insight how the reception with multiple bluetooth channels works.
