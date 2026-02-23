# Towards MDTN: LoRa-based Probe for Monitoring and Control of IoT Systems

This repository contains the full implementation of an **Edge Management Framework (EMF)** designed for non-intrusive, out-of-band monitoring and remote actuation of IoT edge nodes. The system leverages hardware-level isolation and an optimized **AlLoRa** protocol to ensure 100% management reliability in remote deployments.

## 🚀 Key Features
* **Hardware Isolation:** Decoupled management plane using a dedicated LPWAN Probe.
* **Non-Intrusive:** Induced latency on primary sensing tasks < 5 ms.
* **Bidirectional Control:** Remote reboot, GPIO actuation, and shell command execution via LoRa.
* **High Reliability:** 100% Packet Delivery Ratio (PDR) using modified AlLoRa ARQ stack.
* **Real-time Observability:** Containerized TIG-Stack (Telegraf, InfluxDB, Grafana) dashboard.

---

## 🏗️ System Architecture

The framework is organized into a three-tier architecture that overlays existing IoT data planes without interference.



### Repository Structure
The code is divided into four main functional blocks:

1.  **[Controller Node (LPWAN Probe)](./Controller%20Node%20(LPWAN%20Probe)):** MicroPython-based firmware for the LilyGO T3S3 acting as the out-of-band manager.
2.  **[Edge Node (LILYGO)](./Edge%20Node%20(LILYGO)):** Firmware for the host transceiver, implementing dual-core isolation (Core 0 for management, Core 1 for sensing).
3.  **[Edge Node (RPI 4)](./Edge%20Node%20(RPI%204)):** Scripts for the primary host (Raspberry Pi 4) including metric extraction and remote shell execution logic.
4.  **[GATEWAY ALLORA](./GATEWAY%20ALLORA):** Docker-based TIG-Stack orchestration files and the AlLoRa broker for bidirectional management.

---

## 📊 Experimental Results

Validated at the **Universitat Politècnica de València (UPV)**, the system demonstrates superior performance compared to standard in-band management solutions.

| Metric | Measured Value |
| :--- | :--- |
| **Induced Latency** | < 5 ms |
| **Energy Overhead** | < 4% |
| **Bidirectional RTT** | ≈ 1.84 s |
| **Recovery Time** | ≈ 20 s (Post-Reset) |



---

## 🛠️ Installation & Setup

### 1. Hardware Interconnection
Connect the LPWAN Probe to your host nodes via UART as shown in the interconnection scheme:
* **Probe UART1:** To Raspberry Pi 4 (Node A).
* **Probe UART2:** To LilyGO T3S3 (Node B).



### 2. Deployment
Each folder contains its own installation guide. Generally:
* **Nodes:** Flash the `.py` or `.ino` files to the respective ESP32-S3/RPi platforms.
* **Gateway:** Run the containerized stack:
    ```bash
    cd GATEWAY_ALLORA
    docker-compose up -d
    ```

## 📜 Citation
If you use this framework in your research, please cite our paper:
> *D. Arratia, E. Rosas, et al., "Towards MDTN: LoRa-based probe for monitoring and control IoT Systems," 2026.* (Full citation pending).

## 👨‍💻 Author
**Darius Guamán** - [GitHub Profile](https://github.com/DariusCrack)
