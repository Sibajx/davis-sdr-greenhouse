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
* **MTBF:** 90.95 min
* **MTTR:** 1.0 s
* **Availability:** 99.98%

### 4.1 Notes on these values

The paper's numbers are left as published. The notes below were recomputed from `data/raw/davis_monitor.log` and the daily CSVs for the window 29 Aug 00:00 – 3 Sep 23:59 (8,640 min), and explain how each value is obtained and where it differs from the figure scripts.

* **MTBF.** 90.95 min = 8,640 min / 95 watchdog restarts (observation time over number of restarts). Figure 9(b) shows 71.70 min because `generar_figura_reliability_timeline_EN.py` averages the 94 intervals between consecutive restarts, which leaves out the time before the first and after the last restart.
* **Frame counters.** The daemon's HEARTBEAT counters are cumulative since the last daemon start (28 Aug 15:57), not per evaluation window. At the end of the log they read 230,798 valid frames, 11,899 `no_hex` lines and `crc_fail = 0`. `no_hex` counts rtldavis output lines that start with a timestamp but whose first token is not hexadecimal (the daemon's `lector_rtldavis_worker` discards them before decoding; per the rtldavis source these are diagnostics such as missed- or duplicate-packet messages). They are not frames: rtldavis drops packets that fail its own CRC check before printing, so the daemon's CRC-16 never fails. The published 95.10 % equals valid / (valid + `no_hex`); because `no_hex` is not a frame count, it is not a conventional packet delivery ratio. The campaign log did not keep the discarded lines (DEBUG level), so their types cannot be separated afterwards. Inside the window the counters give 198,838 valid frames and 9,573 `no_hex` lines.
* **MTTR and availability.** 1.0 s is the pause between stopping and relaunching rtldavis. The watchdog fires after 30 s without RF, so each restart implies at least about 31 s without new data, and 62 of the 94 intervals between restarts are shorter than 1 min (retries within the same outage). Grouping restarts less than 5 min apart gives 26 interruptions, a time to recovery of 143–172 s each and an availability of 99.14–99.29 %.
* **Clock offset.** The Davis data-logging module used a time zone about one hour ahead of local time and stores 30-min records. The figure scripts align the SDR clock with the logger by a least-squares shift of the temperature series (`DESFASE_RELOJ_MIN = 61` in the scatter script), i.e. the 60 min time-zone difference plus a 1 min residual.
* **Records.** 40 of the 8,612 records have `Muestras_Ventana = 0` (written without new RF samples).
