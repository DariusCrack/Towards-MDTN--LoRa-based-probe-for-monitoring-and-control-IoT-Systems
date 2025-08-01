#!/usr/bin/env python3
    
import subprocess
import time
import serial
import threading

uart = serial.Serial("/dev/ttyAMA1", baudrate=115200, timeout=1)

def run_cmd(cmd):
    result = subprocess.run(cmd, shell=True, text=True, capture_output=True)
    return result.stdout.strip() if result.stdout else result.stderr.strip()

def collect_metrics():
    metrics = {
        "CPU Usage": run_cmd("top -bn1 | grep '%Cpu'"),
        "Load Average": run_cmd("uptime"),
        "CPU Current Freq": run_cmd("cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq"),
        "CPU Min Freq": run_cmd("cat /sys/devices/system/cpu/cpu0/cpufreq/cpuinfo_min_freq"),
        "CPU Max Freq": run_cmd("cat /sys/devices/system/cpu/cpu0/cpufreq/cpuinfo_max_freq"),
        "CPU Temp": run_cmd("vcgencmd measure_temp"),
        "RAM Usage": run_cmd("free -m"),
        "Disk Usage": run_cmd("df -h"),
        "Disk Values": run_cmd("df -h / | tail -n 1"),
        "Network RX Bytes": run_cmd("cat /sys/class/net/eth0/statistics/rx_bytes"),
        "Network TX Bytes": run_cmd("cat /sys/class/net/eth0/statistics/tx_bytes"),
        "GPU Memory": run_cmd("vcgencmd get_mem gpu"),
        "Voltage": run_cmd("vcgencmd measure_volts"),
        "Throttling": run_cmd("vcgencmd get_throttled"),
        "Uptime": run_cmd("uptime -p"),
        "Kernel": run_cmd("uname -a"),
	"IP Address": run_cmd("ip -4 addr show eth0 | grep -oP '(?<=inet\\s)\\d+(\\.\\d+){3}'"),
        "MAC Address": run_cmd("cat /sys/class/net/$(ip route | grep default | awk '{print $5}')/address"),
        "Interface": run_cmd("ip route | grep default | awk '{print $5}'"),
        "Link State": run_cmd("cat /sys/class/net/$(ip route | grep default | awk '{print $5}')/operstate"),
        "Ping 8.8.8.8": run_cmd("ping -c 1 -W 1 8.8.8.8 > /dev/null && echo 'Online' || echo 'Offline'"),
        "Info - Configuration": run_cmd("ifconfig")
    }
    return metrics

def format_metrics(metrics):
    lines = ["<RPI_METRICS>"]
    for key, value in metrics.items():
        lines.append(f"{key}: {value}")
    lines.append("</RPI_METRICS>")
    return "\n".join(lines)

def metrics_loop():
    while True:
        metrics = collect_metrics()
        message = format_metrics(metrics)
        uart.write(message.encode('utf-8') + b'\n')
        print("[INFO] Sending to ESP32:\n", message)
        time.sleep(60)

def command_listener():
    buffer = ""
    while True:
        if uart.in_waiting:
            data = uart.read(uart.in_waiting).decode()
            buffer += data

            if "[CMD]" in buffer and "\n" in buffer:
                start = buffer.find("[CMD]") + len("[CMD]")
                end = buffer.find("\n", start)
                command = buffer[start:end].strip()
                buffer = buffer[end+1:]  # Clean the buffer

                print(f"[CMD] Ejecutando: {command}")
                output = run_cmd(command)
                response = f"<CMD_RESPONSE>\n{output}\n</CMD_RESPONSE>\n"
                uart.write(response.encode('utf-8'))

        time.sleep(0.1)

if __name__ == "__main__":
    t1 = threading.Thread(target=metrics_loop, daemon=True)
    t2 = threading.Thread(target=command_listener, daemon=True)

    t1.start()
    t2.start()

    while True:
        time.sleep(1)
