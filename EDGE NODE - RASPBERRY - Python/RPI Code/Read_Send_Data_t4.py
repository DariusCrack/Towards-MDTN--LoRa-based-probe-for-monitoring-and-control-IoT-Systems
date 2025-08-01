#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
device_b.py

Reads a DHT22 sensor, simulates extra sensors (pressure and light),
packs all readings into a lightweight binary protocol frame, and
sends it over the PL011 UART (/dev/ttyAMA0) every 60 seconds.
"""

import time
import random
import struct
import serial
import Adafruit_DHT

# === Configuration ===

# DHT22 sensor
DHT_SENSOR = Adafruit_DHT.DHT22
DHT_PIN    = 4             # GPIO pin connected to the DHT22 data line

# PL011 UART0 settings
UART_PORT    = "/dev/serial0"
UART_BAUD    = 115200
UART_TIMEOUT = 1           # seconds

# Sending interval (seconds)
POLL_INTERVAL = 60

# Protocol constants
SOF       = 0x7E           # Start-of-frame marker
VERSION   = 0x01           # Protocol version
MSG_TYPE  = 0x10           # Message type: sensor data

# === Functions ===

def read_dht22():
    """
    Read temperature (°C) and humidity (%) from the DHT22.
    Returns (temperature, humidity) rounded to 2 decimals,
    or (None, None) if the read fails.
    """
    humidity, temperature = Adafruit_DHT.read_retry(DHT_SENSOR, DHT_PIN)
    if humidity is None or temperature is None:
        return None, None
    return round(temperature, 2), round(humidity, 2)

def simulate_extra_sensors():
    """
    Simulate readings for pressure (hPa) and light (lux).
    """
    return {
        'pressure_hPa': round(random.uniform(980.0, 1050.0), 1),
        'light_lux':    round(random.uniform(0.0, 1000.0), 1)
    }

def pack_sensor_frame(seq, temp, hum, pres, light):
    """
    Build a binary frame according to the protocol:
    [SOF][Version][MsgType][Seq][LenHi][LenLo][payload(4x float32 LE)][Checksum]
      - Seq: 0–255 sequence number
      - payload: temperature, humidity, pressure, light as float32 little-endian
      - Checksum: sum of all header+payload bytes modulo 256
    """
    # Pack payload: 4 floats little-endian
    payload = struct.pack('<4f', temp, hum, pres, light)
    length  = len(payload)  # should always be 16 bytes

    # Build header: three uint8 + one uint16 (big-endian)
    header = struct.pack('>BBBH',
                         VERSION,
                         MSG_TYPE,
                         seq,
                         length)

    # Compute checksum over header + payload
    checksum = (sum(header) + sum(payload)) & 0xFF

    # Compose full frame: SOF + header + payload + checksum
    frame = bytes([SOF]) + header + payload + bytes([checksum])
    return frame

# === Main Execution ===

def main():
    # Open UART port
    ser = serial.Serial(
        port=UART_PORT,
        baudrate=UART_BAUD,
        timeout=UART_TIMEOUT
    )
    print(f"[INFO] Opened UART on {UART_PORT} at {UART_BAUD} bps")
    seq = 0

    try:
        while True:
            # 1) Read DHT22
            temp, hum = read_dht22()
            if temp is None:
                print("[WARN] Failed to read DHT22; retrying in 2s...")
                time.sleep(2)
                continue

            # 2) Simulate extra sensors
            extras = simulate_extra_sensors()
            pres   = extras['pressure_hPa']
            light  = extras['light_lux']

            # 3) Log to console (for debugging)
            print(f"[DATA] Seq={seq}  Temp={temp}°C  Hum={hum}%  "
                  f"Pres={pres}hPa  Light={light}lux")

            # 4) Pack and send the frame
            frame = pack_sensor_frame(seq, temp, hum, pres, light)
            ser.write(frame)

            # 5) Increment sequence number (wrap at 255)
            seq = (seq + 1) & 0xFF

            # 6) Wait until next cycle
            time.sleep(POLL_INTERVAL)

    except KeyboardInterrupt:
        print("\n[INFO] Interrupted by user; closing UART...")

    finally:
        ser.close()
        print("[INFO] UART closed. Exiting.")

if __name__ == "__main__":
    main()
