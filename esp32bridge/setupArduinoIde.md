# Installation steps
1) add esp32 as additional board manager url
2) download esp32 by Espressiv Systems in board manager
3) install base64 library by Densaugeo version 1.3.0
4) select correct com-port, set core-debugging-level to None, and configure board specific options
5) open the esp32bridge.ino file
6) compile and upload the sketch and close the serial monitor in the arduino ide, so the python script has access

# Commands
```
s                     -> (scan bluetooth devices and returns json formated list with rssi and name)
p aa:bb:00:dd:ee:ff   -> (pair with omron device with the following mac address)
c aa:bb:00:dd:ee:ff   -> (connect with omron device with the following mac address)
t base64string        -> (send command to device for reading or writing)
```
