# main.py — Control de relé “active-LOW” en LilyGO T3S3 (ESP32-S3)
# Pin de control: GPIO38

from machine import Pin

# Configuración del pin de relé
RELAY_PIN = 16
# Asumimos relé active-LOW: 0 = cerrado (ON), 1 = abierto (OFF)
relay = Pin(RELAY_PIN, Pin.OUT, value=1)

def encender():
    relay.value(1)
    print("🔌 Relé CERRADO → regleta ENCENDIDA")

def apagar():
    relay.value(0)
    print("❌ Relé ABIERTO → regleta APAGADA")

def cleanup():
    # Asegura estado OFF y libera el pin
    apagar()
    try:
        relay.init(Pin.IN)
    except Exception:
        pass
    print("🧹 Pin limpiado y reconfigurado como entrada")

def repl():
    print(f"⚙️  Control de relé iniciado en GPIO{RELAY_PIN}")
    print("Comandos: 'on' → encender, 'off' → apagar, 'exit' → salir")
    while True:
        try:
            cmd = input("comando> ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\n⏸️  Interrupción recibida. Saliendo…")
            break

        if cmd == "on":
            encender()
        elif cmd == "off":
            apagar()
        elif cmd == "exit":
            relay.value(1)
            print("🚪 Saliendo del programa.")
            break
        else:
            print("❗ Comando no válido. Usa 'on', 'off' o 'exit'.")

    cleanup()

# Arranca el bucle de comandos
repl()
