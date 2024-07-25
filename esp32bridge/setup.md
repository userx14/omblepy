1) add esp32 as additional board manager url
2) download esp32 by Espressiv Systems in board manager
3) select correct com-port, set core-debugging-level to None and upload the compiled

Commands:
s                     -> (scan bluetooth devices and returns json formated list with rssi and name)
p aa:bb:00:dd:ee:ff   -> (pair with omron device with the following mac address)
c aa:bb:00:dd:ee:ff   -> (connect with omron device with the following mac address)
w data                -> (not working yet)
r data                -> (not working yet)
d                     -> (not working yet, disconnect device)