# Archivo: loopback_test_pi.py

import serial
import time

# Abrimos UART2 (/dev/ttyAMA1) que está en GPIO 20 (pin 38) → TX
# y GPIO 21 (pin 40) → RX
ser = serial.Serial('/dev/ttyAMA1', baudrate=115200, timeout=1)

# Pequeña espera para que el puerto abra correctamente
time.sleep(1)

print("=== Raspberry Pi Loopback Test ===")
print("Enviando y leyendo en UART2 (pin 38⇄40)")

# Mensaje de prueba
msg = b"PING_PI\n"
print("Pi: Enviado ->", msg)
ser.write(msg)

# Pequeño retraso para que el mensaje regrese
time.sleep(0.2)

# Intentamos leer la línea completa
resp = ser.readline()
print("Pi: Recibido <-", resp)

if resp == msg:
    print("→ Loopback OK en Pi (38⇄40)")
else:
    print("→ Error en loopback. Verifica jumper 38⇄40 o baudio.")

ser.close()
