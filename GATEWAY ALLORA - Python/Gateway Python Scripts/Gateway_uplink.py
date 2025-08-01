#!/usr/bin/env python3
import os
import time
import json
import threading
import logging
import re

import paho.mqtt.client as mqtt
import RPi.GPIO as GPIO

from AlLoRa.Connectors.Serial_connector import Serial_connector
from AlLoRa.Nodes.Gateway import Gateway

# __ CONFIGURATION ___

BROKER_HOST  = "localhost"
BROKER_PORT  = 1883
TOPIC_BASE   = "t3s3"
LILYGO_ID    = "T3S3-GATEWAY-001"
RPI_ID       = "RASPBERRYPI-001"
BASE_DIR     = "/home/pi/Desktop/RPi_GW/Results/da5a08dc"
LILYGO_FILE  = os.path.join(BASE_DIR, "metrics_LilyGo.json")
RPI_FILE     = os.path.join(BASE_DIR, "metrics_Rpi.json")
LORA_CONFIG  = "LoRa.json"

# ___ Logging Setup ____

logging.basicConfig(
    level    = logging.INFO,
    format   = "%(asctime)s [%(levelname)s] %(message)s",
    datefmt  = "%Y-%m-%d %H:%M:%S"
)
log = logging.getLogger()

# ____ MQTT Client Setup ___

client = mqtt.Client(client_id="gateway", clean_session=False)

# last-will for both devices
client.will_set(f"{TOPIC_BASE}/{LILYGO_ID}/status",
                "offline", qos=1, retain=True)
client.will_set(f"{TOPIC_BASE}/{RPI_ID}/status",
                "offline", qos=1, retain=True)

client.on_message = lambda c, u, m: log.info(f"CONTROL {m.topic}: {m.payload}")
client.connect(BROKER_HOST, BROKER_PORT)
client.loop_start()

# announce online
client.publish(f"{TOPIC_BASE}/{LILYGO_ID}/status",
               "online", qos=1, retain=True)
client.publish(f"{TOPIC_BASE}/{RPI_ID}/status",
               "online", qos=1, retain=True)

# subscribe for future control messages
client.subscribe(f"{TOPIC_BASE}/+/control", qos=1)

# ___ ESP32 Reset ___

def reset_esp32():
    pin = 23
    GPIO.setmode(GPIO.BCM)
    try:
        GPIO.setup(pin, GPIO.OUT)
    except RuntimeError:
        GPIO.cleanup(pin)
        GPIO.setup(pin, GPIO.OUT)
    GPIO.output(pin, GPIO.LOW)
    time.sleep(0.1)
    GPIO.output(pin, GPIO.HIGH)
    GPIO.cleanup(pin)
    log.info("ESP32 has been reset")

# ___ Publish Helper ___

def publish_metrics(device_id: str, data: dict):
    payload = {
        "device_id": device_id,
        "ts": int(time.time() * 1000),
        **data
    }
    topic = f"{TOPIC_BASE}/{device_id}/metrics"
    client.publish(topic, json.dumps(payload), qos=1)
    log.info(f"Published {topic} {payload}")

# ___ LilyGo (metrics_LilyGo.json) Parsing ___

FIELD_MAP = {
    "CPU":      "cpu",
    "Mem":      "mem",
    "Temp":     "temp",
    "Uptime":   "uptime",
    "Batt":     "batt",
    "WiFiRSSI": "wifi_rssi",
    "PingRTT":  "ping_rtt",
    "Joined":   "joined",
    "Online":   "online",
    "LoRaRSSI": "lora_rssi",
    "LoRaSNR":  "lora_snr",
    "DataRate": "datarate",
    "FPort":    "fport"
}

# find the inner JSON blob starting at {"CPU"... matching braces
def extract_inner_json(text: str) -> str:
    start = text.find('{"CPU"')
    if start < 0:
        return ""
    depth = 0
    for idx in range(start, len(text)):
        if text[idx] == "{":
            depth += 1
        elif text[idx] == "}":
            depth -= 1
            if depth == 0:
                return text[start:idx+1]
    return ""

# quote any unit-bearing values so JSON parser can load
unit_pattern = re.compile(
    r'("(?P<key>[A-Za-z0-9_]+)":)(?P<val>-?\d+(?:\.\d+)?[^\d,}\]\"]+)'
)
def quote_units(match):
    return f'{match.group(1)}"{match.group("val")}"'

def process_lilygo_file():
    try:
        raw = open(LILYGO_FILE, encoding="utf-8").read()
    except Exception as e:
        log.error(f"Could not read LilyGo file: {e}")
        return

    inner = extract_inner_json(raw)
    if not inner:
        log.error("Inner JSON not found in LilyGo file")
        return

    cleaned = unit_pattern.sub(quote_units, inner)

    try:
        obj = json.loads(cleaned)
    except json.JSONDecodeError as e:
        log.error(f"LilyGo JSON decode error: {e} {cleaned}")
        return

    flat = {}
    for k, v in obj.items():
        fld = FIELD_MAP.get(k)
        if not fld:
            continue
        m = re.match(r"-?\d+(\.\d+)?", str(v))
        flat[fld] = float(m.group(0)) if m else v

    publish_metrics(LILYGO_ID, flat)

# ____ Raspberry Pi (metrics_Rpi.json) Parsing ___

RPI_PATTERNS = [
    (re.compile(r"Cpu\(s\):\s*([\d\.]+) us,\s*([\d\.]+) sy"),
     ["cpu_user", "cpu_sys"]),
    (re.compile(r"load average:\s*([\d\.]+),\s*([\d\.]+),\s*([\d\.]+)"),
     ["load1", "load5", "load15"]),
    (re.compile(r"CPU Current Freq:\s*(\d+)"), ["cpu_freq_cur"]),
    (re.compile(r"CPU Min Freq:\s*(\d+)"),     ["cpu_freq_min"]),
    (re.compile(r"CPU Max Freq:\s*(\d+)"),     ["cpu_freq_max"]),
    (re.compile(r"temp=([\d\.]+)'C"),         ["cpu_temp"]),
    (re.compile(r"Mem:\s+\S+\s+(\d+)\s+(\d+)\s+(\d+)"),
     ["ram_total", "ram_used", "ram_free"]),
    (re.compile(r"Swap:\s+(\d+)\s+(\d+)"),     ["swap_total", "swap_used"]),
    (re.compile(r"/dev/root.*\s+(\d+)%"),      ["disk_used_pct"]),
    (re.compile(r"Network RX Bytes:\s*(\d+)"), ["net_rx"]),
    (re.compile(r"Network TX Bytes:\s*(\d+)"), ["net_tx"]),
    (re.compile(r"gpu=(\d+)"),                ["gpu_mem"]),
    (re.compile(r"volt=([\d\.]+)V"),          ["voltage"]),
    (re.compile(r"throttled=(0x[0-9A-Fa-f]+)"), ["throttled"]),
    (re.compile(r"Uptime:\s*up\s*(\d+)\s*hours?,\s*(\d+)\s*minutes?"),
     ["uptime_s", "_uptime_m"])
]

def parse_text_fields(line: str, out: dict):
    if line.startswith("Kernel:"):
        out["kernel"] = line.split(":",1)[1].strip()
    if line.startswith("IP Address:"):
        out["ip_address"] = line.split(":",1)[1].strip()
    if line.startswith("MAC Address:"):
        out["mac_address"] = line.split(":",1)[1].strip()
    if line.startswith("Interface:"):
        out["interface"] = line.split(":",1)[1].strip()
    if line.startswith("Link State:"):
        out["link_state"] = line.split(":",1)[1].strip()
    if line.startswith("Ping"):
        out["ping"] = line.split(":",1)[1].strip()

def process_rpi_file():
    try:
        raw = open(RPI_FILE, encoding="utf-8").read()
    except Exception as e:
        log.error(f"Could not read RPi file: {e}")
        return

    data = {}
    for line in raw.splitlines():
        for pattern, keys in RPI_PATTERNS:
            m = pattern.search(line)
            if not m:
                continue
            vals = m.groups()
            for name, val in zip(keys, vals):
                v = val.strip()
                try:
                    if v.lower().startswith("0x"):
                        data[name] = int(v, 16)
                    elif v.replace(".", "", 1).isdigit():
                        data[name] = float(v) if "." in v else int(v)
                    else:
                        data[name] = v
                except Exception as ex:
                    log.warning(f"RPi parse error for {name}={v!r}: {ex}")
                    data[name] = v
            break
        parse_text_fields(line, data)

    publish_metrics(RPI_ID, data)

#  File Watcher Threads ___

def watch_file(path: str, handler, label: str):
    last_mtime = 0
    log.info(f"Starting watcher for {label}")
    while True:
        if os.path.isfile(path):
            mtime = os.path.getmtime(path)
            if mtime > last_mtime:
                last_mtime = mtime
                handler()
        time.sleep(1)

# ___ Main ___

def main():
    # start LoRa gateway listener
    conn = Serial_connector(reset_function=reset_esp32)
    gw   = Gateway(conn, config_file=LORA_CONFIG, debug_hops=False)
    threading.Thread(
        target=gw.check_digital_endpoints,
        kwargs={"print_file_content": True, "save_files": True},
        daemon=True
    ).start()

    # start file watchers for both devices
    threading.Thread(
        target=watch_file,
        args=(LILYGO_FILE, process_lilygo_file, "LilyGo"),
        daemon=True
    ).start()

    threading.Thread(
        target=watch_file,
        args=(RPI_FILE, process_rpi_file, "RaspberryPi"),
        daemon=True
    ).start()

    log.info("gateway.py running; press Ctrl+C to exit")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        log.info("Shutting down")
        client.loop_stop()
        client.disconnect()

if __name__ == "__main__":
    main()

