# Reproducibility Guide: Davis Vantage Pro 2 Telemetry Decoding via RTL-SDR

This document provides step-by-step instructions to reproduce the experimental validation and analysis published in **IJSAMI Vol. 20, 2026**.

## 1. Hardware Setup
* **SBC:** Raspberry Pi 5 (8GB RAM)
* **SDR:** Nooelec NESDR SMArt v5 (RTL2832U / R820T2)
* **Transmitter:** Davis Vantage Pro2 (902–928 MHz ISM band)
* **Antenna:** 915 MHz tuned omnidirectional antenna

## 2. Environment Setup
```bash
# Clone the repository
git clone https://github.com/Sibajx/davis-sdr-greenhouse.git
cd davis-sdr-greenhouse

# Install Python dependencies
pip install -r requirements.txt
```

## 3. Reproduction Steps

### 3.1 Unit Testing & Frame Integrity
Verify frame processing and CRC-16 integrity mechanics:
```bash
pytest tests/
```

### 3.2 Figure Generation & Statistical Analysis
Run the figure generation scripts on processed CSV datasets:
```bash
python scripts/scripts_Figures/generar_figuras_multidia.py
python scripts/scripts_Figures/generar_bland_altman_EN.py
python scripts/scripts_Figures/generar_figura_reliability_timeline_EN.py
```
Generated PDF figures will automatically save to `figures/`.

## 4. Benchmark Dataset Summary (Aug 29 – Sep 4, 2026)
* **Total Validated Records:** 8,612
* **Packet Delivery Ratio (PDR):** 95.10%
* **MTBF:** 90.95 min
* **MTTR:** 1.0 s
* **Availability:** 99.98%
