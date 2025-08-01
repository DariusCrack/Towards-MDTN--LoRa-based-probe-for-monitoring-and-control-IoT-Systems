// BEFORE STARTING!
// 1) configure ".../Arduino/libraries/MCCI_LoRaWAN_LMIC_library/project_config/lmic_project_config.h"
// 2) define the board version and model in "boards.h"
//

#include <lmic.h>
#include <hal/hal.h>
#include <Arduino.h>
#include <WiFi.h>
#include "utilities.h"
#include <DHT.h>
#include <Wire.h>
#include <SPI.h>
#include <LoRa.h>  // Assuming you're using LoRa for TTN
#include <ESPping.h>
//#include <HardwareSerial.h>
#define BUILTIN_LED BOARD_LED

//  LoRaWAN parameters
static const u1_t PROGMEM APPEUI[8]={ 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00 };
void os_getArtEui (u1_t* buf) { memcpy_P(buf, APPEUI, 8);}

// This EUI must be in little-endian format. 
// For TTN issued EUIs the last bytes should be 0xD5, 0xB3, 0x70.
// This MUST be in little endian format. (lsb in TTN)
static const u1_t PROGMEM DEVEUI[8]={ 0x3D, 0xF5, 0x06, 0xD0, 0x7E, 0xD5, 0xB3, 0x70 };
void os_getDevEui (u1_t* buf) { memcpy_P(buf, DEVEUI, 8);}

// PM: This key MUST be in big endian format. (msb in TTN)
static const u1_t PROGMEM APPKEY[16] = { 0x83, 0x09, 0x80, 0x2E, 0x1F, 0x7C, 0x20, 0x7A, 0x8F, 0xFD, 0x07, 0x96, 0xEC, 0xB3, 0x4E, 0x0B };
void os_getDevKey (u1_t* buf) {  memcpy_P(buf, APPKEY, 16);}
//
//  end LoRaWAN parameters

//static uint8_t mydata[] = "Hello, world!";
static osjob_t sendjob;

// Schedule TX every this many seconds (might become longer due to duty
// cycle limitations).
const unsigned TX_INTERVAL = 30;

// PM: Local pin mapping for the Lilygo T3S3
 #define RADIO_CS            RADIO_CS_PIN     // 7
 #define RADIO_RESET         RADIO_RST_PIN    // 8
 #define RADIO_DIO_0         RADIO_DIO0_PIN   // 9
 #define RADIO_DIO_1         RADIO_DIO1_PIN   // 33
 #define RADIO_DIO_2         LMIC_UNUSED_PIN  // void
 #define DHTPIN 35
 #define DHTTYPE DHT22
 #define TX_INTERVAL 100

// === Protocol constants (must match Device B) ===
 #define SOF        0x7E   // Start-of-frame
 #define VERSION    0x01   // Protocol version
 #define MSG_TYPE   0x10   // Message type: sensor data
 #define MAX_PAYLOAD 16    // 4 floats × 4 bytes

// 1) Declaras tu buffer y longitud como variables globales
static uint8_t  lastPayload[16];
static uint8_t  lastPayloadLen = 0;

const lmic_pinmap lmic_pins = {
     .nss = RADIO_CS,
     .rxtx = LMIC_UNUSED_PIN,
     .rst = RADIO_RESET,
     .dio = {RADIO_DIO_0, RADIO_DIO_1, RADIO_DIO_2}  
};
// — new globals for LoRa metrics —
bool lorawanJoined    = false;
bool lastTxAck        = false;
int  lastLoRaRSSI     = 0;
int  lastLoRaSNR      = 0;
int  lastDataRate     = 0;
const int LORA_FPORT  = 1; 

// WiFi global 
bool             wifiEnabled       = false;
int              wifiRSSI          = -127;
long             pingRTT           = -1;

TaskHandle_t Task1;

// Define GPIO pins to control
const int controllable_gpios[] = {15, 16, 38, 39, 40};  // Example GPIOs to control
const int num_gpios = sizeof(controllable_gpios) / sizeof(controllable_gpios[0]);

int uptime = 0;
unsigned long lastMetricsTime = 0;
const unsigned long metricsInterval = 30000; // 30seconds

// Validation of the PIN to avoid interference with the GPIO using by LoRa
bool isReservedLoRaPin(int pin) {
  return (pin == RADIO_DIO_0 || pin == RADIO_DIO_1 || pin == RADIO_CS || pin == RADIO_RESET);
}

//Function to control GPIOs
void setGPIO(int pin, int state){
  if (isReservedLoRaPin(pin)) {
  Serial2.println("{\"error\":\"PIN_RESERVED\"}");
  return;
  }
  for (int i = 0; i < num_gpios; i++){
    if(pin == controllable_gpios[i]){
      pinMode(pin,OUTPUT);
      digitalWrite(pin,state);
      return;
    }
  }
    Serial2.println("Error: Invalid GPIO"); 
}

// Function to reset Node 1
void resetNode() {
  Serial.println("[Node 1] Resetting device...");
  // Add reset logic here (e.g., restarting the device)
  ESP.restart();  // Restart the device
  Serial2.println("{\"status\":\"RESETTING\"}");  // Inform Controler of the reset
}
void sampleWiFi() {
  if (!wifiEnabled || WiFi.status() != WL_CONNECTED) {
    wifiRSSI = -127;
    pingRTT  = -1;
  } else {
    wifiRSSI = WiFi.RSSI();
    // do a single ping, timeout 1s:
    if (Ping.ping("8.8.8.8", 1)) {
      pingRTT = Ping.averageTime();  // in ms
    } else {
      pingRTT = -1;
    }
  }
}

void printHex2(unsigned v) {
    v &= 0xff;
    if (v < 16)
        Serial.print('0');
    Serial.print(v, HEX);
}

void oledPrintf(int col, int row, const char* fmt, ...) {
  char msg[50];
  va_list args;
  va_start(args, fmt);
  vsprintf(msg, fmt, args);
  va_end(args);
  Serial.println(msg);

  u8g2->clearBuffer();
  u8g2->drawStr(col, row, msg);
  u8g2->sendBuffer();
}

void oledPrintfbrow(int row, const char* fmt, ...) {
  char msg[50];
  va_list args;
  va_start(args, fmt);
  vsprintf(msg, fmt, args);
  va_end(args);
  Serial.println(msg);

  u8g2->clearBuffer();
  u8g2->drawStr(0, (row+1)*10, msg);
  u8g2->sendBuffer();
}

bool isValidGPIO(uint8_t pin) {
  for (uint8_t i = 0; i < sizeof(controllable_gpios); i++) {
    if (controllable_gpios[i] == pin) return true;
  }
  return false;
}

void onEvent (ev_t ev) {
    long now = os_getTime();
    oledPrintfbrow(0, "Time %lu", now);

    switch(ev) {
        case EV_SCAN_TIMEOUT:
            oledPrintf(0, 7, "EV_SCAN_TIMEOUT");
            break;
        case EV_BEACON_FOUND:
            oledPrintf(0, 7, "EV_BEACON_FOUND");
            break;
        case EV_BEACON_MISSED:
            oledPrintf(0, 7, "EV_BEACON_MISSED");
            break;
        case EV_BEACON_TRACKED:
            oledPrintf(0, 7, "EV_BEACON_TRACKED");
            break;
        case EV_JOINING:
            oledPrintf(0, 7, "EV_JOINING");
            break;
        case EV_JOINED:
            oledPrintf(0, 7, "EV_JOINED");
            {
              u4_t netid = 0;
              devaddr_t devaddr = 0;
              u1_t nwkKey[16];
              u1_t artKey[16];
              LMIC_getSessionKeys(&netid, &devaddr, nwkKey, artKey);
              Serial.print("netid: ");
              Serial.println(netid, DEC);
              Serial.print("devaddr: ");
              Serial.println(devaddr, HEX);
              Serial.print("AppSKey: ");
              for (size_t i=0; i<sizeof(artKey); ++i) {
                if (i != 0) Serial.print("-");
                printHex2(artKey[i]);
              }
              Serial.println("");
              Serial.print("NwkSKey: ");
              for (size_t i=0; i<sizeof(nwkKey); ++i) {
                      if (i != 0) Serial.print("-");
                      printHex2(nwkKey[i]);
              }
              Serial.println();
            }
            
            // Disable link check validation (automatically enabled
            // during join, but because slow data rates change max TX
              // size, we don't use it in this example.
            LMIC_setLinkCheckMode(0);
            lorawanJoined = true;
            Serial.println("[LMIC] Joined network");
            break;
        case EV_RFU1:
            oledPrintf(0, 7, "EV_RFU1");
            break;
        case EV_JOIN_FAILED:
            oledPrintf(0, 7, "EV_JOIN_FAILED");
            break;
        case EV_REJOIN_FAILED:
            oledPrintf(0, 7, "EV_REJOIN_FAILED");
            lorawanJoined = false;
            Serial.println("[LMIC] Join failed");
            break;
        case EV_TXCOMPLETE:
            oledPrintf(0, 7, "EV_TXCOMPLETE");
            digitalWrite(BUILTIN_LED, LOW);
            if (LMIC.txrxFlags & TXRX_ACK) {
              oledPrintf(0, 3, "rssi:%d, snr:%1d", LMIC.rssi, LMIC.snr);
              oledPrintf(0, 6, "Received ack");
            }
            if (LMIC.dataLen) {
              oledPrintf(0, 3, "rssi:%d, snr:%1d", LMIC.rssi, LMIC.snr);
              oledPrintf(0, 6, "Received %d", LMIC.dataLen);
              Serial.print("Data:");
              for(size_t i=0; i<LMIC.dataLen; i++) {
                Serial.print(" ");
                printHex2(LMIC.frame[i + LMIC.dataBeg]);
              }
            if (LMIC.dataLen >= 2) {
              uint8_t gpio_pin = LMIC.frame[LMIC.dataBeg];
              uint8_t state = LMIC.frame[LMIC.dataBeg + 1];

              if (isValidGPIO(gpio_pin)) {
                pinMode(gpio_pin, OUTPUT);
                digitalWrite(gpio_pin, state ? HIGH : LOW);

                Serial.print("GPIO ");
                Serial.print(gpio_pin);
                Serial.print(" seteado a ");
                Serial.println(state ? "ON" : "OFF");
              } else {
                Serial.print("GPIO no válido: ");
                Serial.println(gpio_pin);
              }
            }
 
            }
            // capture ACK flag, RSSI, SNR, DR
            lastTxAck    = (LMIC.txrxFlags & TXRX_ACK) != 0;
            lastLoRaRSSI = LMIC.rssi;    // rssi of last downlink / ACK
            lastLoRaSNR  = LMIC.snr;     // snr of last downlink / ACK
            lastDataRate = LMIC.datarate; // numeric LoRaDR (e.g. DR0..DR5)
            // Schedule next transmission
            os_setTimedCallback(&sendjob,os_getTime(),onSendJob);
            break;
        case EV_LOST_TSYNC:
            oledPrintf(0, 7, "EV_LOST_TSYNC");
            break;
        case EV_RESET:
            oledPrintf(0, 7, "EV_RESET");
            break;
        case EV_RXCOMPLETE:
            oledPrintf(0, 7, "EV_RXCOMPLETE");
            break;
        case EV_LINK_DEAD:
            oledPrintf(0, 7, "EV_LINK_DEAD");
            break;
        case EV_LINK_ALIVE:
            oledPrintf(0, 7, "EV_LINK_ALIVE");
            break;
        case EV_SCAN_FOUND:
            oledPrintf(0, 7, "EV_SCAN_FOUND");
            break;
        case EV_TXSTART:
            oledPrintf(0, 3, "EV_TXSTART");
            break;
        case EV_TXCANCELED:
            oledPrintf(0, 7, "EV_TXCANCELED");
            break;
        case EV_RXSTART:
            oledPrintf(0, 7, "EV_RXSTART");
            break;
        case EV_JOIN_TXCOMPLETE:
            oledPrintf(0, 7, "EV_JOIN_TXCOMPLETE");
            break;
        default:
            oledPrintf(0, 7, "Unknown event %ud", ev);
            break;
    }
}


// Parser state
enum ParseState { WAIT_SOF, READ_HDR, READ_PAY, READ_CHK };
static ParseState state    = WAIT_SOF;
static uint8_t   hdrBuf[5];
static uint8_t   hdrIdx    = 0;
static uint16_t  payloadLen= 0;
static uint8_t   payloadBuf[MAX_PAYLOAD];
static uint16_t  payIdx    = 0;
static uint8_t   chkCalc   = 0;

// 2)
void sendPayload(uint8_t* data, uint8_t len) {
  if (LMIC.opmode & OP_TXRXPEND) return;
  LMIC_setTxData2(1, data, len, 0);
  Serial.println(F("📡 Packet queued"));
}

// 3) Callback with sign osjobcb_t
void onSendJob(osjob_t* j) {
  // 
  sendPayload(lastPayload, lastPayloadLen);
}

//------------------------------------------------------------------------------
// Read bytes from UART1 and assemble frames of the form:
// [SOF][Ver][Type][Seq][LenHi][LenLo][4×float32 LE][Chk]
void parseUART1() {
  while (Serial1.available()) {
    uint8_t b = Serial1.read();
    switch (state) {
      case WAIT_SOF:
        if (b == SOF) {
          state  = READ_HDR;
          hdrIdx = chkCalc = 0;
        }
        break;

      case READ_HDR:
        hdrBuf[hdrIdx++] = b;
        chkCalc += b;
        if (hdrIdx == 5) {
          uint8_t ver     = hdrBuf[0];
          uint8_t type    = hdrBuf[1];
          payloadLen      = (hdrBuf[3] << 8) | hdrBuf[4];
          if (ver!=VERSION || type!=MSG_TYPE || payloadLen>MAX_PAYLOAD) {
            state = WAIT_SOF;  // bad header ⇒ resync
          } else {
            payIdx = 0;
            state  = READ_PAY;
          }
        }
        break;

      case READ_PAY:
        payloadBuf[payIdx++] = b;
        chkCalc += b;
        if (payIdx >= payloadLen) {
          state = READ_CHK;
        }
        break;

      case READ_CHK:
        if ((chkCalc & 0xFF) == b) {
          // valid frame!  extract floats
          float temp, hum, pres, light;
          memcpy(&temp,  payloadBuf+0, 4);
          memcpy(&hum,   payloadBuf+4, 4);
          memcpy(&pres,  payloadBuf+8, 4);
          memcpy(&light, payloadBuf+12,4);

          // 1) print on COM8
          Serial.printf("📥 T=%.2f°C H=%.2f%% P=%.2fhPa L=%.2flux\n",
                        temp, hum, pres, light);

          // 2) forward on LoRa
          sendPayload(payloadBuf, payloadLen);
        } else {
          Serial.println(F("⚠ Checksum fail"));
        }
        state = WAIT_SOF;
        // …
        memcpy(lastPayload, payloadBuf, payloadLen);
        lastPayloadLen = payloadLen;

        // TX_INTERVAL seconds to send
        os_setTimedCallback(&sendjob,
        os_getTime() + sec2osticks(TX_INTERVAL),
        onSendJob);
        break;
    }
  }
}


void loop2( void * parameter )
{
  Serial2.begin(115200, SERIAL_8N1, 45, 46); //
  Serial.println("UART2 initialized on GPIO45 RX / GPIO46 TX");
  Serial2.println("Hi?");
  for(;;){
    
      // Send metrics every 30 seconds
    if (millis() - lastMetricsTime >= metricsInterval) {
      uptime += 100;
      String metrics = getSystemMetrics(); // Respond with system metrics
      Serial2.println(metrics);
      lastMetricsTime = millis();
    }
    if (Serial2.available()){
      Serial.println("UART 2 Available");
      //Serial2.println("UART Available");
      delay(1);
      String input = Serial2.readStringUntil('\n'); // Read new data until newline
      input.trim(); // Remove leading/trailing whitespace
      Serial.println("[UART] Received command: " + input);
      // Process the command
      if (input.startsWith("GET_METRICS")){
        String metrics = getSystemMetrics(); // Respond with system metrics
        delay(30000); // each 30 seconds the metrics will send.
        Serial2.println(metrics);
      }
      else if (input.startsWith("SET_GPIO")){
          int pin, state;
          int matched = sscanf(input.c_str(), "SET_GPIO %d %d", &pin, &state);

          // Check if the command is valid
          if (matched == 2) {
            // Check if the pin is valid
            bool validPin = false;
            for (int i = 0; i < num_gpios; i++) {
              if (pin == controllable_gpios[i]) {
                validPin = true;
                break;
              }
            }

            if (validPin) {
              pinMode(pin, OUTPUT);
              // Set the GPIO to the requested state (HIGH or LOW)
              if (state == 1){digitalWrite(pin, HIGH);}
              else {digitalWrite(pin, LOW);}
              Serial2.println("{\"status\":\"OK\"}");  // Acknowledge the command
            } else {
              Serial2.println("{\"error\":\"INVALID_PIN\"}"); } // Invalid pin number
            
          } else {
            Serial2.println("{\"error\":\"INVALID_COMMAND\"}"); } // Invalid command format     
       }
       else if (input.startsWith("RESET")){
        resetNode();} 
      else {
         Serial2.println("Error: Unknow Command");}
    }
    //delay(20000);
    vTaskDelay(10);  // Evita un uso excesivo de la CPU, pero no bloquea el sistema
  }
}

void setup () {
  Serial.begin (115200);
  while (!Serial) { delay(10); }
  Serial.println(F("Device A starting..."));

  // Initialize UART1 for RX from Raspberry Pi
  Serial1.begin(115200, SERIAL_8N1, 42, 41);
  Serial.println(F(" UART 1 initialized on GPIO42 RX / GPIO41 TX"));


  Serial2.begin(115200); 
  Serial.println (F ("Starting"));
  initBoard ();
  delay (1500);  // When the power is turned on, a delay is required.
  oledPrintfbrow (2, "Hello Darius! Viva LoRaWAN");
  SPI.begin();
  // LMIC init
  os_init ();
  // Reset the MAC state. Session and pending data transfers will be discarded.
  Serial.println("LMIC reset...");
  LMIC_reset ();
  LMIC_setClockError(MAX_CLOCK_ERROR * 1/100);  // trim clock error if needed
  LMIC_startJoining();
  
  Serial.println("Setting ADR...");
  LMIC_setAdrMode (false);
  //dht.begin();
  // Start job (sending automatically starts OTAA too)
  // do_send (&sendjob);
  pinMode (BUILTIN_LED, OUTPUT);
  digitalWrite (BUILTIN_LED, LOW);
  randomSeed(analogRead(A0)); // Usa una lectura analógica como semilla
  
  // Start LED CORE 0
  xTaskCreatePinnedToCore(
    loop2,   // Task function
    "UART Control",     // Task name
    8192,              // Stack size
    NULL,              // Task parameters
    1,                 // Task priority
    &Task1,    // Task handle
    0                  // Core 0
  );
  
  Serial.println("[System] Setup complete. Main loop on Core 0, UART control on Core 1.");
  
  // … if you uncomment these lines, the metrics will start working:
  WiFi.begin("Darius","Dariuscrack");
  wifiEnabled = true;
}

float getBatteryVoltage() {
    int raw = analogRead(BAT_ADC_PIN);
    return raw*(3.3 / 4095);  // Adjust for your voltage divider
}
float readInternalTemperature() {
  // Read the raw value from the internal temperature sensor (GPIO34 as ADC)
  int raw = analogRead(BAT_ADC_PIN);  // ADC Channel
  // Convert the raw value to voltage
  float voltage = raw*(3.3 / 4095);  // Convert raw ADC value to voltage
  
  // Convert voltage to temperature (°C)
  // The ESP32 internal temperature sensor gives an approximate range of 0-100°C
    float tempe = (voltage - 0.5) * 100;  // Convert voltage to temperature in Celsius
    float offsetval; 
    if (tempe >50 & tempe<125 ){
      offsetval=-2;
      } else if (tempe >20 & tempe<50){
      offsetval=-1;}
      else if (tempe >-10 & tempe<20) {
      offsetval=0;}
      else if (tempe >-30 & tempe<-10) {
      offsetval=1;}
      else if (tempe >-40 & tempe<-30) {
      offsetval=2;}
      else {
        offsetval=0;
        //Serial.println("Incorrect range of temperature");
        }
    tempe= (0.4386 * tempe)-(27.88*offsetval)-30.52;
    return tempe;  
}

// --- SYSTEM METRICS FUNCTION ---
String getSystemMetrics() {
  sampleWiFi();

  uint32_t freeHeap = ESP.getFreeHeap();
  float    tempInt  = readInternalTemperature();
  uint32_t upSec    = millis() / 1000;
  float    battV    = getBatteryVoltage();

  // build JSON in the desired groups/order
  String j = "{";
  // 1) General
  j += "\"CPU\":"    + String(ESP.getCpuFreqMHz()) + "MHz,";
  j += "\"Mem\":"    + String(freeHeap)        + "Bytes,";
  j += "\"Temp\":"   + String(tempInt)         + "°C,";
  j += "\"Uptime\":" + String(upSec)           + "s,";  

  // 2) Battery
  j += "\"Batt\":"   + String(battV)           + "V,";

  // 3) Wi-Fi
  j += "\"WiFiRSSI\":" + String(wifiRSSI)    + "dBm,";
  j += "\"PingRTT\":"  + String(pingRTT)     + "ms,";

  // 4) LoRaWAN
  j += "\"Joined\":"   + String(lorawanJoined ? "true":"false") + ",";
  j += "\"Online\":"   + String(lastTxAck     ? "true":"false") + ",";
  j += "\"LoRaRSSI\":" + String(lastLoRaRSSI ) + "dB,";
  j += "\"LoRaSNR\":"  + String(lastLoRaSNR  ) + "dB,";
  j += "\"DataRate\":" + String(lastDataRate ) + ",";
  j += "\"FPort\":"    + String(LORA_FPORT);

  j += "}";
  return j;
}

void loop () {
  os_runloop_once ();
  // Parse incoming UART frames and send via LoRa
  parseUART1();
  delay(1);  // Very short delay to yield CPU
}
