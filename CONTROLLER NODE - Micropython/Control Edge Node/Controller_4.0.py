# Controller_Unified_RaspLilyGo4.0.py
#
# MicroPython on LILYGO T3S3:
#  - UART1 ↔ Raspberry Pi 4  (pins 41=TX, 42=RX)
#  - UART2 ↔ T3S3 LILYGO IoT Node (pins 46=TX, 45=RX)
# Automatically forwards each complete metrics block via AlLoRa

from machine import UART, Pin
import time, sys, select
from AlLoRa.Nodes.Source import Source
from AlLoRa.File import CTP_File
from AlLoRa.Connectors.SX127x_connector import SX127x_connector

# ——————————————————————————————————————————————————————————————————————
# LoRa Initialization (do once)
# ——————————————————————————————————————————————————————————————————————
connector = SX127x_connector()
lora_node = Source(connector, config_file="LoRa_S.json")
chunk_size = lora_node.chunk_size

# ——————————————————————————————————————————————————————————————————————
# UART Initialization
# ——————————————————————————————————————————————————————————————————————
uart_rpi  = UART(1, baudrate=115200, tx=41, rx=42, timeout=100)
uart_lily = UART(2, baudrate=115200, tx=46, rx=45, timeout=100)
time.sleep(0.2)

# ——————————————————————————————————————————————————————————————————————
# Buffers for accumulating incoming bytes
# ——————————————————————————————————————————————————————————————————————
partial_rpi  = b""
partial_lily = b""

# ——————————————————————————————————————————————————————————————————————
# Handler for Raspberry Pi metrics & responses
# ——————————————————————————————————————————————————————————————————————
def handle_uart_from_rpi():
    global partial_rpi
    if not uart_rpi.any():
        return
    data = uart_rpi.read()
    if not data:
        return
    partial_rpi += data

    # Send full <RPI_METRICS> blocks
    while b"</RPI_METRICS>" in partial_rpi:
        start = partial_rpi.find(b"<RPI_METRICS>")
        end   = partial_rpi.find(b"</RPI_METRICS>") + len(b"</RPI_METRICS>")
        block = partial_rpi[start:end]
        text  = block.decode("utf-8", "ignore")
        # Print locally
        print("\n📡 RPI METRICS:")
        print(text.replace("<RPI_METRICS>", "").replace("</RPI_METRICS>", ""))
        # Send via LoRa
        file = CTP_File("metrics_Rpi.json", text.encode(), chunk_size)
        lora_node.set_file(file)
        lora_node.send_file()
        # Remove processed block
        partial_rpi = partial_rpi[end:]

    # Send full <CMD_RESPONSE> blocks (if your Pi sends them)
    while b"</CMD_RESPONSE>" in partial_rpi:
        start = partial_rpi.find(b"<CMD_RESPONSE>")
        end   = partial_rpi.find(b"</CMD_RESPONSE>") + len(b"</CMD_RESPONSE>")
        block = partial_rpi[start:end]
        text  = block.decode("utf-8", "ignore")
        print("\n📥 RPI CMD RESPONSE:")
        print(text.replace("<CMD_RESPONSE>", "").replace("</CMD_RESPONSE>", ""))
        file = CTP_File("response_rpi.json", text.encode(), chunk_size)
        lora_node.set_file(file)
        lora_node.send_file()
        partial_rpi = partial_rpi[end:]

# ——————————————————————————————————————————————————————————————————————
# Handler for LilyGo T3S3 metrics
# ——————————————————————————————————————————————————————————————————————
def handle_uart_from_lily(): 
    global partial_lily
    if not uart_lily.any():
        return
    data = uart_lily.read()
    if not data:
        return
    partial_lily += data

    # Split on newline to process each complete line
    parts = partial_lily.split(b"\n")
    for line in parts[:-1]:
        text = line.decode("utf-8", "ignore").strip()
        if not text:
            continue
        print(f"\n🤖 LILYGO METRICS: {text}")
        file = CTP_File("metrics_LilyGo.json", text.encode(), chunk_size)
        lora_node.set_file(file)
        lora_node.send_file()
    # keep leftover
    partial_lily = parts[-1]

# ——————————————————————————————————————————————————————————————————————
# Main loop: continuously poll UARTs and forward metrics
# ——————————————————————————————————————————————————————————————————————
print("=== Controller_Unified_RaspLilyGo4.0 Starting ===")

while True:
    handle_uart_from_rpi()
    handle_uart_from_lily()
    time.sleep(0.05)

