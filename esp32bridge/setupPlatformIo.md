# Installation steps
1) install [Visual Studio](https://code.visualstudio.com/)
2) in extensions sidebar install platformIO, restart IDE
3) in the sidebar (alien icon) pick "esp32bridge" as the project folder, wait until project is initialized
4) build and upload

# Commands
```
s                     -> (scan bluetooth devices and returns json formated list with rssi and name)
p aa:bb:00:dd:ee:ff   -> (pair with omron device with the following mac address)
c aa:bb:00:dd:ee:ff   -> (connect with omron device with the following mac address)
t base64string        -> (send command to device for reading or writing)
```
