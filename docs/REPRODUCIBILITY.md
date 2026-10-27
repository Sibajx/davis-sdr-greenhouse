# Reproducibility Guide: Davis Vantage Pro 2 Telemetry Decoding via RTL-SDR

This document provides step-by-step instructions to reproduce the experimental validation and analysis reported in the manuscript *A Low-Cost SDR-Edge Architecture for Weather Telemetry in Cyber-Physical Greenhouse Drying Systems* (IJSAMI, manuscript 362170, under review).

## 1. Hardware Setup
* **SBC:** Raspberry Pi 5 (16 GB RAM)
* **SDR:** Nooelec NESDR SMArt (RTL2832U / R820T2, 0.5 PPM TCXO)
* **Transmitter:** Davis Vantage Pro2 (902–928 MHz ISM band)
* **Antenna:** 915 MHz fibreglass LoRa antenna, RG58 coaxial cable

## 2. Environment Setup
```bash
# Clone the repository
git clone https://github.com/Sibajx/davis-sdr-greenhouse.git
cd davis-sdr-greenhouse

# Install Python dependencies
pip install -r requirements.txt
```

### 2.1 rtldavis (external binary)
The acquisition daemon (`src/davis_monitor.py`) runs the `rtldavis` binary, which is not on PyPI. The paper uses the multi-channel hopping fork by Heijst (2019) with the `-tf US` hop set, and the WeeWX driver `weewx-rtldavis` (Wall and Heijst, 2019):

```bash
git clone https://github.com/lheijst/rtldavis.git
# Follow the build instructions in that repository, then make sure
# `rtldavis` is on the PATH:
which rtldavis
```

### 2.2 Input data
The figure scripts read CSV and log files by bare name, from the **current working directory**. Run them from the folder that contains these files:

| File | Used by | Notes |
|---|---|---|
| `historial_davis_2026-08-29.csv` … `historial_davis_2026-09-03.csv` | Figures 2–9, Supplementary S1–S6 | Daily SDR-decoded records, one file per day |
| `davis_wifi_logger.csv` | Figure 2, Supplementary S1–S6 | Davis reference station records (validation) |
| `davis_monitor.log` | Figure 9 | Daemon log: watchdog restarts and database writes |

These files are versioned in `data/raw/`, except `davis_monitor.log`, which is ignored by `.gitignore` and must be copied there manually (see `data/raw/README.md`).

## 3. Reproduction Steps

### 3.1 Unit Testing & Frame Integrity
Verify frame processing and CRC-16 integrity mechanics:
```bash
pytest tests/
```

### 3.2 Figure Generation & Statistical Analysis
Run the scripts from the folder that holds the input files (section 2.2). Each script writes its PDF to the **current working directory**:

| Output | Script |
|---|---|
| Figure 2 (Bland–Altman) | `scripts/scripts_Figures/generar_bland_altman_EN.py` |
| Figures 3–8 (multi-day profiles) | `scripts/scripts_Figures/generar_figuras_multidia.py` |
| Figure 9 (reliability timeline) | `scripts/scripts_Figures/generar_figura_reliability_timeline_EN.py` |
| Supplementary S1 / S2 | `scripts/scripts_Figures/generar_figura7_corregido.py` / `generar_figura8_corregido.py` |
| Supplementary S3 / S4 (1:1 scatter) | `scripts/scripts_Figures/generar_scatter_EN.py` |
| Supplementary S5 | `scripts/scripts_Figures/generar_bland_altman_EN.py` |
| Supplementary S6 | `scripts/scripts_Figures/generar_supplementary_s6_EN.py` |

Example:
```bash
cd /path/to/data
python /path/to/davis-sdr-greenhouse/scripts/scripts_Figures/generar_figuras_multidia.py
```

Table 3 values are stored in `figures/tabla_comparacion_promediado_davis.csv`.

## 4. Reported Metrics (paper, Table 4)

The values below are the ones reported in the paper for the field evaluation (29 Aug – 4 Sep 2026). The reliability script (`generar_figura_reliability_timeline_EN.py`) uses the window 29 Aug – 3 Sep when it reads the log, and prints the MTBF it computes for that window.
* **Total Validated Records:** 8,612
* **Packet Delivery Ratio (PDR):** 95.10%
* **MTBF:** 90.95 min (paper text, abstract and Table 4)

**MTBF discrepancy.** The paper's Figure 9(b) shows an MTBF of 71.70 min, which is the value `generar_figura_reliability_timeline_EN.py` computes from `davis_monitor.log` for 29 Aug – 3 Sep (95 watchdog events, 94 intervals between them). The 90.95 min value in the paper text and table cannot be reproduced from the supplied log with the window used by the script. Other windows give different values (full log, 200 events: 65.94 min; 29 Aug – 4 Sep, 169 events: 48.64 min). The script output is the reproducible value; the source of 90.95 min is not documented here.
* **MTTR:** 1.0 s
* **Availability:** 99.98%
