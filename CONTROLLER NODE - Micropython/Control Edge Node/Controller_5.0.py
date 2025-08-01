# Controller_Unified_RaspLilyGo4.3.py
#
# MicroPython on LILYGO T3S3:
#  - UART1 ↔ Raspberry Pi 4  (pins 41=TX, 42=RX)
#  - UART2 ↔ T3S3 LILYGO IoT Node (pins 46=TX, 45=RX)
#  - Sends metrics via AlLoRa Source
#  - Receives downlink commands via AlLoRa Requester → executes control actions

from machine import Pin, UART, reset as mcu_reset
import time, sys, gc
from AlLoRa.Connectors.SX127x_connector import SX127x_connector
from AlLoRa.Nodes.Source import Source
from AlLoRa.Nodes.Requester import Requester
from AlLoRa.File import CTP_File
from AlLoRa.Digital_Endpoint import Digital_Endpoint

# ——————————— LoRa Setup ———————————
connector     = SX127x_connector()
# Source for metrics uploads
lora_source   = Source(connector, config_file="LoRa_S.json")
chunk_size    = lora_source.chunk_size
# Requester for downlink commands
lora_req      = Requester(connector, config_file="LoRa_S.json")
# Define the endpoint (the Grafana gateway or server) to listen to
gateway_ep    = Digital_Endpoint(
    name="G",
    mac_address="da586520",   # replace with your Grafana node’s MAC
    active=True
)

# ——————————— UART Setup ———————————
uart_rpi  = UART(1, 115200, tx=41, rx=42, timeout=100)
uart_lily = UART(2, 115200, tx=46, rx=45, timeout=100)
time.sleep(0.2)

# ——————————— Buffers ———————————
partial_rpi  = b""
partial_lily = b""

# ——————————— Relay Example ———————————
RELAY_PIN = 16
relay     = Pin(RELAY_PIN, Pin.OUT)
relay.value(0)

# ——————————— Downlink Commands ———————————
CMD_RESET      = 0x01
CMD_SET_GPIO   = 0x02
CMD_FORCE_RPI  = 0x03
CMD_FORCE_LILY = 0x04

# ——————————— Handlers ———————————
def handle_uart_from_rpi():
    global partial_rpi
    if not uart_rpi.any():
        return
    partial_rpi += uart_rpi.read() or b""

    # Process complete <RPI_METRICS> blocks
    while b"</RPI_METRICS>" in partial_rpi:
        s = partial_rpi.find(b"<RPI_METRICS>")
        e = partial_rpi.find(b"</RPI_METRICS>") + len(b"</RPI_METRICS>")
        block = partial_rpi[s:e].decode("utf-8","ignore")
        json_text = block.replace("<RPI_METRICS>","").replace("</RPI_METRICS>","")
        print("\n📡 RPI METRICS:\n", json_text)
        f = CTP_File("metrics_Rpi.json", json_text.encode(), chunk_size)
        lora_source.set_file(f); lora_source.send_file()
        partial_rpi = partial_rpi[e:]

    # Process complete <CMD_RESPONSE> blocks
    while b"</CMD_RESPONSE>" in partial_rpi:
        s = partial_rpi.find(b"<CMD_RESPONSE>")
        e = partial_rpi.find(b"</CMD_RESPONSE>") + len(b"</CMD_RESPONSE>")
        block = partial_rpi[s:e].decode("utf-8","ignore")
        json_text = block.replace("<CMD_RESPONSE>","").replace("</CMD_RESPONSE>","")
        print("\n📥 RPI CMD RESPONSE:\n", json_text)
        f = CTP_File("response_Rpi.json", json_text.encode(), chunk_size)
        lora_source.set_file(f); lora_source.send_file()
        partial_rpi = partial_rpi[e:]

def handle_uart_from_lily():
    global partial_lily
    if not uart_lily.any():
        return
    partial_lily += uart_lily.read() or b""
    parts = partial_lily.split(b"\n")
    for line in parts[:-1]:
        text = line.decode("utf-8","ignore").strip()
        if not text:
            continue
        print(f"\n🤖 LILYGO METRICS:\n{text}")
        # wrap in minimal JSON
        json_text = '{"metrics":"' + text + '"}'
        f = CTP_File("metrics_LilyGo.json", json_text.encode(), chunk_size)
        lora_source.set_file(f); lora_source.send_file()
    partial_lily = parts[-1]

def handle_downlink():
    """
    Listen for a downlink file (commands) from the gateway endpoint.
    Uses Requester.listen_to_endpoint with a small timeout.
    """
    try:
        file = lora_req.listen_to_endpoint(gateway_ep, timeout_ms=5000, print_file=False)
    except Exception as ex:
        print("⚠️ Downlink listen error:", ex)
        return

    if not file:
        return

    data = file.get_content()
    file.cleanup()
    gc.collect()

    if not data:
        return

    cmd = data[0]
    args = data[1:]
    if cmd == CMD_RESET:
        print("⚙️ DOWNLINK CMD: RESET")
        mcu_reset()
    elif cmd == CMD_SET_GPIO and len(args) >= 2:
        pin, state = args[0], args[1]
        p = Pin(pin, Pin.OUT)
        p.value(1 if state else 0)
        print(f"⚙️ DOWNLINK CMD: SET_GPIO {pin} = {state}")
    elif cmd == CMD_FORCE_RPI:
        print("⚙️ DOWNLINK CMD: FORCE_GET_RPI_METRICS")
        uart_rpi.write(b"GET_RPI_METRICS\n")
    elif cmd == CMD_FORCE_LILY:
        print("⚙️ DOWNLINK CMD: FORCE_GET_LILYGO_METRICS")
        uart_lily.write(b"GET_METRICS\n")
    else:
        print(f"⚠️ UNKNOWN DOWNLINK CMD: {cmd:#02x}, ARGS: {args}")

# ——————————— Main Loop ———————————
print("=== Controller_Unified_RaspLilyGo4.3 Starting ===")
while True:
    handle_uart_from_rpi()
    handle_uart_from_lily()
    handle_downlink()
    time.sleep(0.05)
