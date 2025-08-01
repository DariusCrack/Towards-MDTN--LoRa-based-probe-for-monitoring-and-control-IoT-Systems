import gc
import time
import ujson
import random

from AlLoRa.Connectors.SX127x_connector import SX127x_connector
from AlLoRa.Nodes.Source import Source
from AlLoRa.File import CTP_File

# ——— Configuration ——————————————————————————————————————
CONFIG_PATH = "LoRa_bi.json"
PEER_MAC    = b"\xda\x5a\x0f\x50"   # Requester’s MAC (4 bytes)

# ——— Initialization —————————————————————————————————————
gc.enable()
connector = SX127x_connector(config_file=CONFIG_PATH)
src       = Source(connector, config_file=CONFIG_PATH)

print("Source node up. Sending to:", PEER_MAC.hex())

# ——— Main loop: send a “sensor” reading every 60 s ————————————
while True:
    # 1) Simulate sensor data
    reading = {
        "temperature": round(random.randint(200, 300) / 10, 1),   # 20.0–30.0 °C
        "humidity":    round(random.randint(300, 600) / 10, 1),   # 30.0–60.0 %
        "timestamp":   time.time()
    }
    payload = ujson.dumps(reading).encode()

    # 2) Wrap in a CTP_File and send
    f = CTP_File("/tmp/sensor.json", payload)
    try:
        print("⏫ Sending sensor data:", reading)
        src.send_file(PEER_MAC, f)
        print("   → OK")
    except Exception as e:
        print("   ! send_file failed:", e)

    # 3) Wait 60 seconds
    time.sleep(60)
