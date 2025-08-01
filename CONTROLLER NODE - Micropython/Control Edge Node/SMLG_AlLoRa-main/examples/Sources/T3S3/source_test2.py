# micropython_device.py
import time, ujson, urandom
from SX127x_connector import SX127x_connector
from File          import CTP_File

# — configuration —
CONFIG = "LoRa_S.json"
THRESHOLD = 30.0       # °C
SEND_INTERVAL = 10     # seconds
LISTEN_WINDOW = 5      # seconds

# — setup —
conn   = SX127x_connector()
node   = CTP_File  # we’ll instantiate per-message
lora   = __import__("Source").Source(conn, config_file=CONFIG)  # delayed import on device

def simulate_temperature():
    # pseudo-random between 20 and 35
    return 20 + (urandom.getrandbits(8)/255)*15

while True:
    # 1) Send a temperature reading
    temp = simulate_temperature()
    payload = ujson.dumps({"type":"temp","value":temp})
    msg = CTP_File(name="temp.json",
                   content=payload.encode(),
                   chunk_size=lora.get_chunk_size(),
                   mesh_mode=False)
    print("▶ Sending temperature:", temp)
    lora.send_file(msg)

    # 2) Listen briefly for any incoming command
    print("⏳ Listening for command …")
    start = time.time()
    while time.time() - start < LISTEN_WINDOW:
        raw = conn.recv(focus_time=LISTEN_WINDOW)
        if not raw:
            continue
        pkt = __import__("File").Packet.from_raw(raw)
        if pkt.command == pkt.COMMANDS["DATA"]:
            cmd = ujson.loads(pkt.payload.decode())
            if cmd.get("type") == "control" and cmd.get("action") == "turn_off":
                print("❗ Command received: TURN OFF")
                # … insert your shutdown logic here …
                break

    time.sleep(SEND_INTERVAL)
