# Towards MDTN: LoRa-based Probe for Monitoring and Control of IoT Systems

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python: 3.x](https://img.shields.io/badge/Python-3.x-blue.svg)](https://www.python.org/)
[![Platform: ESP32-S3 | RPi 4](https://img.shields.io/badge/Platform-ESP32--S3%20%7C%20RPi%204-red.svg)](https://www.espressif.com/)

This repository contains the full source code and orchestration files for the **Edge Management Framework (EMF)**. This system enables non-intrusive, out-of-band management of remote IoT deployments using a dedicated hardware-isolated probe and an optimized bidirectional AlLoRa protocol.

## 🚀 Key Research Contributions
* **Hardware-Level Isolation:** Full decoupling of management and data planes to ensure zero-intrusiveness.
* **Non-Intrusive Monitoring:** Induced jitter and latency on primary sensing tasks are kept below **5 ms**.
* **High Availability:** System recovery and reconnection to TTN verified in **< 20 seconds** post-reset.
* **Bidirectional AlLoRa:** Modified stack supporting half-duplex remote actuation (RTT ≈ 1.8s).
* **Heterogeneous Support:** Unified management for both MicroPython (ESP32) and Linux-based (RPi) edge nodes.

---

## 🏗️ System Architecture

The EMF acts as an overlay management network. It interfaces with the host devices through independent UART channels, polling metrics without consuming primary network bandwidth.

[Image: Insert 'EMF Architecture.png' here]

### Repository Components
* **[Controller Node (LPWAN Probe)](./Controller%20Node%20(LPWAN%20Probe)):** The "brain" of the management plane. MicroPython firmware for LilyGO T3S3 that orchestrates polling and AlLoRa communication.
* **[Edge Node (LILYGO)](./Edge%20Node%20(LILYGO)):** Implementation of the dual-core isolation strategy on ESP32-S3 (LilyGO T3S3).
* **[Edge Node (RPI 4)](./Edge%20Node%20(RPI%204)):** Resource monitoring scripts and remote shell execution logic for Raspberry Pi 4.
* **[GATEWAY ALLORA](./GATEWAY%20ALLORA):** Backend suite (Docker-based TIG-Stack: Telegraf, InfluxDB, Grafana) for real-time observability.

---

## 📊 Performance & Validation

The framework was validated at the **Universitat Politècnica de València (UPV)**. The following table summarizes the quantitative results:

| Parameter | Value | Observation |
| :--- | :--- | :--- |
| **Induced Latency** | < 5 ms | Preserves high-fidelity sensing. |
| **Energy Overhead** | < 4% | Ideal for solar/battery deployments. |
| **Packet Delivery Ratio** | 100% | Guaranteed by AlLoRa ARQ mechanism. |
| **Handshake RTT** | 1.84 s | Enables near real-time remote control. |

[Image: Insert 'Grafana Control System LILYGO.png' here]

---

## 🛠️ Quick Start

### Hardware Setup
Interconnect the LPWAN Probe with the host nodes using the following UART scheme:
1. **Probe UART1 <--> Raspberry Pi 4** (Node A)
2. **Probe UART2 <--> LilyGO T3S3** (Node B)

[Image: Insert 'Scheme of Edge MDTN.png' here]

### Deployment
1. **Gateway:** Deploy the management backend using Docker:
   ```bash
   cd "GATEWAY ALLORA"
   docker-compose up -d
