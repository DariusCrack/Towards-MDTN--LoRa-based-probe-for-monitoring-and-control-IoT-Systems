import gc
import time
import ujson
import random

from AlLoRa.Connectors.SX127x_connector import SX127x_connector
from AlLoRa.Nodes.Requester import Requester
from AlLoRa.Nodes.Source import Source       # to send commands
from AlLoRa.Digital_Endpoint import Digital_Endpoint
from AlLoRa.File import CTP_File

# ——— Configuration ——————————————————————————————————————
CONFIG_PATH       = "LoRa_bi.json"
SOURCE_MAC        = b"\xda\x5a\x08\xdc"   # Source’s MAC (4 bytes)
CMD_INTERVAL      = 30                    # seconds between commands

# ——— Initialization —————————————————————————————————————
gc.enable()
connector = SX127x_connector(config_file=CONFIG_PATH)
req       = Requester(connector, config_file=CONFIG_PATH)
src       = Source(connector, config_file=CONFIG_PATH)

# Register the Source as an endpoint
req.add_endpoint(Digital_Endpoint("sensor", SOURCE_MAC, active=True))

print("Requester node up. Listening & sending commands to:", SOURCE_MAC.hex())

last_cmd_time = time.time()
cmd_count     = 0

# ——— Main event loop ——————————————————————————————————————
while True:
    # 1) Non-blocking check for any incoming file
    incoming = req.receive_file(blocking=False)
    if incoming:
        try:
            content = incoming.get_content()
        except AttributeError:
            # fallback if .get_content() not available
            content = incoming.payload
        print("📥 Received:", incoming.filename)
        print("    ►", content)

    # 2) Periodically send a simulated control command
    now = time.time()
    if now - last_cmd_time >= CMD_INTERVAL:
        cmd = {
            "command": f"CMD_{cmd_count}",
            "value":   random.randint(0, 100),
            "ts":      now
        }
        payload = ujson.dumps(cmd).encode()
        f = CTP_File("/tmp/cmd.json", payload)

        try:
            print("⏬ Sending control command:", cmd)
            src.send_file(SOURCE_MAC, f)
            print("    → OK")
        except Exception as e:
            print("    ! send_file failed:", e)

        last_cmd_time = now
        cmd_count += 1

    # 3) Short sleep to yield the radio
    time.sleep(0.1)
