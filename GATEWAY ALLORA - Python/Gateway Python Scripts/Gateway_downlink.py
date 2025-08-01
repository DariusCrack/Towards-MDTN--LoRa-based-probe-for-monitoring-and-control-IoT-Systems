#!/usr/bin/env python3
import time
import threading
import queue
import logging
import RPi.GPIO as GPIO
from flask import Flask, request, jsonify
from flask_cors import CORS
from serial import SerialException

from AlLoRa.Connectors.Serial_connector import Serial_connector
from AlLoRa.Nodes.Source import Source
from AlLoRa.File import CTP_File  # updated import path

# ———————————————————————————
# Logging configuration
# ———————————————————————————
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)

# ———————————————————————————
# Hardware reset for ESP32
# ———————————————————————————

def reset_esp32():
    RST_PIN = 23
    GPIO.setmode(GPIO.BCM)
    try:
        GPIO.setup(RST_PIN, GPIO.OUT)
    except RuntimeError:
        GPIO.cleanup(RST_PIN)
        GPIO.setup(RST_PIN, GPIO.OUT)
    GPIO.output(RST_PIN, GPIO.LOW)
    time.sleep(0.1)
    GPIO.output(RST_PIN, GPIO.HIGH)
    logger.info("ESP32 has been reset")
    GPIO.cleanup()

# ———————————————————————————
# LoRa Source initialization for downlink
# ———————————————————————————
SERIAL_PORT = "/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_A50285BI-if00-port0"  # adjust to your device
BAUDRATE = 115200
CONFIG_FILE = "LoRa_S.json"

# Create a single connector instance with exclusive access
connector = Serial_connector(reset_function=reset_esp32)

# Initialize Source for downlink transmissions
source = Source(connector, config_file=CONFIG_FILE)
chunk_size = source.get_chunk_size()

# Attempt initial handshake
try:
    source.establish_connection()
    logger.info("LoRa handshake successful")
except Exception as e:
    logger.error(f"Initial LoRa handshake failed: {e}")

# ———————————————————————————
# Command queue and worker thread
# ———————————————————————————
cmd_queue = queue.Queue()


def downlink_worker():
    while True:
        device_id, cmd = cmd_queue.get()
        try:
            # Prepare CTP_File packet
            payload = cmd.encode("utf-8")
            filename = f"cmd_{device_id}_{int(time.time())}.bin"
            packet = CTP_File(
                name=filename,
                content=payload,
                chunk_size=chunk_size
            )
            # Send packet
            source.set_file(packet)
            source.send_file()
            logger.info(f"Sent '{cmd}' to '{device_id}' via AlLoRa")
        except SerialException as se:
            logger.error(f"Serial port error during downlink: {se}")
            # Attempt to reset and re-establish connection
            time.sleep(1)
            connector.reset_function()
            try:
                source.establish_connection()
                logger.info("Re-established LoRa handshake after reset")
            except Exception as e:
                logger.error(f"Re-handshake failed: {e}")
        except Exception as ex:
            logger.error(f"Unexpected error sending downlink: {ex}")
        finally:
            cmd_queue.task_done()

# Start worker thread
downlink_thread = threading.Thread(target=downlink_worker, daemon=True)
downlink_thread.start()

# ———————————————————————————
# Flask HTTP server for Grafana integration
# ———————————————————————————
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

last_cmd = None

@app.route("/", methods=["GET"])
def healthcheck():
    return jsonify({"ok": True}), 200

@app.route("/downlink/status", methods=["GET"])
def get_status():
    return jsonify({"ok": True, "last_cmd": last_cmd}), 200

@app.route("/downlink", methods=["POST"])
def do_downlink():
    global last_cmd
    try:
        data = request.get_json(force=True)
        device_id = data.get("deviceId")
        cmd = data.get("cmd")

        # Validate input
        valid_cmds = {"reset"}
        if not device_id or not isinstance(device_id, str):
            return jsonify({"status": "error", "error": "Invalid deviceId"}), 400
        if cmd not in valid_cmds:
            return jsonify({"status": "error", "error": f"Unsupported command: {cmd}"}), 400

        # Enqueue for downlink
        last_cmd = cmd
        logger.info(f"Queued downlink command '{cmd}' for '{device_id}'")
        cmd_queue.put((device_id, cmd))

        return jsonify({"status": "ok", "message": f"Command '{cmd}' queued for '{device_id}'"}), 200

    except Exception as e:
        logger.error(f"Error processing downlink request: {e}")
        return jsonify({"status": "error", "error": str(e)}), 500


def start_http():
    logger.info("Starting HTTP server on port 5000 for downlink")
    app.run(host="0.0.0.0", port=5000)

if __name__ == "__main__":
    start_http()

