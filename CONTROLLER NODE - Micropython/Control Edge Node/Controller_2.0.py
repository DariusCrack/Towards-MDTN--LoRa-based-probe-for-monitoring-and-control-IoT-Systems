from machine import Pin
from machine import UART
import time, gc
import sys
import select

from AlLoRa.Nodes.Source import Source
from AlLoRa.File import CTP_File
from AlLoRa.Connectors.SX127x_connector import SX127x_connector

def clean_timing_file():
	test_log = open('log.txt', "wb")
	test_log.write("")
	test_log.close()


#Define UART 1 for Raspberry Pi 4
uart_rpi   = UART(1, baudrate=115200, tx=41, rx=42, timeout=100)
#Define UART 2 for LILYGO
uart_lily  = UART(2, baudrate=115200, tx=46, rx=45, timeout=100)
time.sleep(0.2)

# Raspberry Pi Parameters
buffer = b""
partial = b""
partial_r  = b""
partial_c  = b""
last_metrics_time = time.ticks_ms()
last_command_time = time.ticks_ms()

COMMAND_INTERVAL_MS = 50000
METRICS_INTERVAL_MS = 60000

# LILYGO Parameters

valid_gpios = [15, 16, 38, 39, 40]
valid = {"on","off","exit"}
RELAY_PIN = 38
MENU_INTERVAL = 27
last_menu_time = time.time()
relay = Pin(RELAY_PIN, Pin.IN, value=0)


input_buffer = ""  # Stores ongoing keyboard input
awaiting_gpio = False
gpio_action = None  # "on" or "off"


gc.enable()
# For testing

file_counter = 0

# if __name__ == "__main__":
# AlLoRa setup
connector=SX127x_connector()
lora_node = Source(connector, config_file="LoRa_S.json")
chunk_size = lora_node.get_chunk_size() #235




# MAIN MENU

def print_menu():
    print("\n===============================================")
    print("\n=== LILYGO MENU OPTIONS ===")
    print("1. Request Metrics Manually")
    print("2. Reset Node")
    print("3. Turn GPIO ON")
    print("4. Turn GPIO OFF")
    print("\n=== RASPBERRY PI MENU OPTIONS ===")
    print("5. Write a command")
    print("\n=== ELECTRICITY OPTIONS ===")
    print("6. Control Switch")
    print("7. Exit Program")


# Raspberry Pi Functions
def handle_uart_data():
    global partial
    if uart_rpi.any():
        data_pi = uart_rpi.read()
        if data_pi:
            partial += data_pi
            if b"</RPI_METRICS>" in partial or b"</CMD_RESPONSE>" in partial:
                try:
                    decoded = partial.decode()
                    if "<RPI_METRICS>" in decoded:
                        print("\n📡 RECEIVED METRICS - RASPBERRY PI 4:")
                        print("----------------------------------------")
                        content = decoded.split("<RPI_METRICS>")[1].split("</RPI_METRICS>")[0]
                        for line in content.strip().splitlines():
                            print(line)
                        print("----------------------------------------")
                    elif "<CMD_RESPONSE>" in decoded:
                        print("\n📥 RESPONSE OF RASPBERRY PI 4:")
                        print("----------------------------------------")
                        content = decoded.split("<CMD_RESPONSE>")[1].split("</CMD_RESPONSE>")[0]
                        print(content.strip())
                        print("----------------------------------------")
                except Exception as e:
                    print("Error to decode:", e)
                partial = b""

            
            
# LILYGO FUNCTIONS

def send_get_metrics():
    uart_lily.write("GET_METRICS\n")
    print(">> Sent: GET_METRICS")

def send_reset():
    uart_lily.write("RESET\n")
    print(">> Sent: RESET")

def send_gpio(pin, state):
    if pin not in valid_gpios:
        print(f"[Invalid GPIO] GPIO {pin} not supported.")
        return
    uart_lily.write(f"SET_GPIO {pin} {state}\n")
    print(f">> Sent: SET_GPIO {pin} {state}")

# MAIN FUNCTIONS

def handle_command(command):
    command = command.strip()

    if command == "1":
        send_get_metrics()

    elif command == "2":
        send_reset()

    elif command == "3":
        print("Enter a valid GPIO [15, 16, 38, 39, 40] number to turn ON (or 'c' to cancel):")
        gpio = input().strip()
        if gpio.lower() == "c":
            print("[CANCELLED] GPIO input cancelled.")
            return
        try:
            pin = int(gpio)
            send_gpio(pin, 1)
        except ValueError:
            print("[Error] Invalid GPIO number.")

    elif command == "4":
        print("Enter GPIO [15, 16, 38, 39, 40] number to turn OFF (or 'c' to cancel):")
        gpio = input().strip()
        if gpio.lower() == "c":
            print("[CANCELLED] GPIO input cancelled.")
            return
        try:
            pin = int(gpio)
            send_gpio(pin, 0)
        except ValueError:
            print("[Error] Invalid GPIO number.")

    elif command == "5":
        print("\n⌨️ Write the command to send Raspberry Pi ")
        
        #cmd = sys.stdin.readline().strip()
        cmd = input().strip()
        if cmd.lower() == "c":
            print("[CANCELLED] ")
            return
        else:
            uart_rpi.write(f"[CMD]{cmd}\n".encode())
            print("✅ Comando enviado al Raspberry Pi.")
            handle_uart_data()
            time.sleep(0.05)
            
    elif command == "6":
        Relay = input("Insert a Command (on/off/exit):").strip().lower()
        if Relay not in valid:
            print("[Error Command]")
            return
        if Relay == "on":
            relay = Pin(RELAY_PIN, Pin.IN)  
            print("The Switch is ON")
        elif Relay == "off":
            # inicializa una sola vez al inicio:
            relay = Pin(RELAY_PIN, Pin.OUT)  
            print("The Switch is OFF")
        else:
            print("Exit")
            relay = Pin(RELAY_PIN, Pin.IN) 
            return

            
    elif command == "7":
        print(">> Exiting...")
        sys.exit()
    elif command == "":
        pass  # Ignore empty input

    else:
        print("[Invalid Option] Use 1-7.")

print(">> CONTROLLER ACTIVE - UART 1 and 2 Listening Mode")

def parse_rpi():
    global partial_r
    if not uart_rpi.any(): return None
    partial_r += uart_rpi.read()
    if b"</RPI_METRICS>" in partial_r:
        data_pi = partial_r.decode()
        body = data_pi.split("<RPI_METRICS>")[1].split("</RPI_METRICS>")[0]
        partial_r = b""
        return "📡 RPI_METRICS\n" + body
    return None

def parse_lily():
    if not uart_lily.any(): return None
    line = uart_lily.readline().decode().strip()
    if line:
        return "📡 LILYGO_METRICS\n" + line
    return None


# MAIN LOOP
while True:
    now = time.time()
    #now = time.ticks_ms()
    #Raspberry Pi Loop
    if handle_uart_data():
        parse_rpi()

    # Periodic menu
    if now - last_menu_time >= MENU_INTERVAL:
        print_menu()
        last_menu_time = now
    

    # LILYGO Loop
    if uart_lily.any():
        try:
            data_lily = uart_lily.read().decode('utf-8').strip()
            if data_lily:
                print("\n📡 RECEIVED METRICS - LILY GO:")
                print("----------------------------------------")
                print(f"[NODE] {data_lily}")
        except Exception as e:
            print(f"[UART ERROR] {e}")
        parse_lily()

    # Non-blocking input handling
    if select.select([sys.stdin], [], [], 0.01)[0]:
        char = sys.stdin.read(1)
        if char == '\n':
            handle_command(input_buffer)
            input_buffer = ""
        else:
            input_buffer += char

    time.sleep(0.1)

    # SEND ALLORA CODE
    
    clean_timing_file()
    print("Waiting first OK")
    backup = lora_node.establish_connection()
    print("Connection OK")

    # This is how to handle a backup file if needed (not implemented in this example...)
    if backup:
        print("Asking backup")
        #file = Datasource.get_backup()
        #lora_node.restore_file(file)

    # with an established connection, we start sending data periodically
    #while True:
        # 1) Si no hay fichero activo, trato de setear uno
        if not lora_node.got_file():
            data_pi = parse_rpi()
            data_lily = parse_lily()
            if data_pi:
                payload_pi = data_pi.encode("utf-8")
                filename = 'metrics_pi{}.json'
                file = CTP_File(
                    name=filename,
                    content=payload_pi,
                    chunk_size=chunk_size
                )
                lora_node.set_file(file)
            elif data_lily:
                payload_lily = data_lily.encode("utf-8")
                filename = 'metrics_lily{}.json'
                file = CTP_File(
                    name=filename,
                    content=payload_lily,
                    chunk_size=chunk_size
                )
                lora_node.set_file(file)
            else:
                # nada que enviar, duermo un poco y salto send_file()
                time.sleep(0.05)
                continue

        # 2) Solo si _ahora_ hay fichero activo, enviamos
        lora_node.send_file()
        time.sleep(0.05)





