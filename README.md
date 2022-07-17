# omblepy
Cli tool to read records from Omron Bluetooth-LE measurement instruments
This version is built to test compatibility with HEM-7361T-D and only works on linux, because of the dependency on bluez.

## Initial setup
First install python in version 3.8 or preferably a more recent one. <br>
Use the official installer on windows or on linux use:<br>
```
apt install python3.10
```

Install the two required modules 'bleak' for bluetooth communication and 'terminaltables' for command line output formatting. <br>
```
pip3 install terminaltables
pip3 install bluezero
```

## Usage examples
The tool provides a build-in help, which can be accesses like so:
```
python3 ./omblepy.py -h
```
### Pairing
If the omron is first used with this tool it is neccesary to write a new unlock key like so:
```
python3 ./omblepy.py -p -d HEM-7361T-D
```
This only needs to be done once, even connecting using different PCs with different Bluetooth Mac Addresses should work fine from now on.

### Normal connection
Start the omron instrument in it's normal bluetooth connection mode, execute the commands below to export all stored data records into csv files in the current directory.
#### With selection dialog for device
```
python3 ./omblepy.py -d HEM-7361T-D
```
#### With predefined bluetooth mac
```
python3 ./omblepy.py -d HEM-7361T-D -m D3:07:19:08:27:00
```
#### Read only new records and reset unread records counter
```
python3 ./omblepy.py -d HEM-7361T-D -n
```

## Adding Support for new devices
The device specific configuration is stored in a per device file. 
Feel free to contribute to bring support to more devices.

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
