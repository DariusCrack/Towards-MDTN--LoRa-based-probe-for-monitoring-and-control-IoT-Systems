from machine import Pin
from machine import UART
import time
import sys
import select

#Define UART 1 for Raspberry Pi 4
uart = UART(1, baudrate=115200, tx=41, rx=42, timeout=100)
#Define UART 2 for LILYGO 
uart2 = UART(2, baudrate=115200, tx=46, rx=45, timeout=100)
time.sleep(0.2)

# Raspberry Pi Parameters
buffer = b""
partial = b""
last_metrics_time = time.ticks_ms()
last_command_time = time.ticks_ms()

COMMAND_INTERVAL_MS = 50000
METRICS_INTERVAL_MS = 60000

# LILYGO Parameters

valid_gpios = [15, 16, 38, 39, 40]
valid = {"on","off","exit"}
RELAY_PIN = 16
MENU_INTERVAL = 65
last_menu_time = time.time()
relay = Pin(RELAY_PIN, Pin.IN, value=1)


input_buffer = ""  # Stores ongoing keyboard input
awaiting_gpio = False
gpio_action = None  # "on" or "off"

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
    if uart.any():
        data = uart.read()
        if data:
            partial += data
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
    uart2.write("GET_METRICS\n")
    print(">> Sent: GET_METRICS")

def send_reset():
    uart2.write("RESET\n")
    print(">> Sent: RESET")

def send_gpio(pin, state):
    if pin not in valid_gpios:
        print(f"[Invalid GPIO] GPIO {pin} not supported.")
        return
    uart2.write(f"SET_GPIO {pin} {state}\n")
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
            uart.write(f"[CMD]{cmd}\n".encode())
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


# MAIN LOOP
while True:
    now = time.time()
    #now = time.ticks_ms()
    #Raspberry Pi Loop
    handle_uart_data()

    # Periodic menu
    if now - last_menu_time >= MENU_INTERVAL:
        print_menu()
        last_menu_time = now
    

    # LILYGO Loop
    if uart2.any():
        try:
            data = uart2.read().decode('utf-8').strip()
            if data:
                print("\n📡 RECEIVED METRICS - LILY GO:")
                print("----------------------------------------")
                print(f"[NODE] {data}")
        except Exception as e:
            print(f"[UART ERROR] {e}")

    # Non-blocking input handling
    if select.select([sys.stdin], [], [], 0.01)[0]:
        char = sys.stdin.read(1)
        if char == '\n':
            handle_command(input_buffer)
            input_buffer = ""
        else:
            input_buffer += char

    time.sleep(0.1)
