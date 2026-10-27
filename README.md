# A Low-Cost SDR-Edge Architecture for Weather Telemetry in Cyber-Physical Greenhouse Drying Systems

[![CI/CD Pipeline](https://github.com/Sibajx/davis-sdr-greenhouse/actions/workflows/ci.yml/badge.svg)](https://github.com/Sibajx/davis-sdr-greenhouse/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Publication Status](https://img.shields.io/badge/Paper-In_review_IJSAMI_(362170)-orange.svg)](paper/)

Software-defined radio (RTL-SDR) edge architecture that receives, validates (CRC-16), decodes and stores the weather telemetry of a Davis Vantage Pro 2 station in the 902–928 MHz ISM band, for greenhouse drying monitoring and control.

---

## 📄 Manuscript & Publication
* **Status:** In review, *International Journal of Sustainable Agricultural Management and Informatics* (IJSAMI), manuscript 362170. Volume and issue to be assigned.
* **Full Manuscript PDF:** Available in [`paper/`](paper/)
* **Reproducibility Guide:** See [`docs/REPRODUCIBILITY.md`](docs/REPRODUCIBILITY.md)

---

## 📊 Experimental Results (Aug 29 – Sep 4, 2026)

| Metric / Parameter | Evaluation Value |
| :--- | :--- |
| **Evaluation Period** | August 29 – September 4, 2026 |
| **Validated Records** | 8,612 records |
| **Packet Delivery Ratio (PDR)** | 95.10% |
| **Watchdog Interventions** | 95 |
| **Mean Time Between Failures (MTBF)** | 90.95 min |
| **Mean Time To Recovery (MTTR)** | 1.0 s |
| **Writing Jitter** | 0.398 s |
| **System Availability** | 99.98% |
| **MAE Temperature** | 0.156 °C |
| **MAE Humidity** | 0.352 % |

Values as published in the paper. See [`docs/REPRODUCIBILITY.md`](docs/REPRODUCIBILITY.md), section 4.1, for how they relate to the raw data in `data/raw/`.

---

## 🛠️ Hardware Requirements
* **Single Board Computer:** Raspberry Pi 5 (16 GB RAM, Ubuntu aarch64)
* **SDR Receiver:** Nooelec NESDR SMArt (RTL2832U / R820T2, 0.5 PPM TCXO)
* **Receiving Antenna:** 915 MHz fibreglass LoRa antenna (RG58 coaxial cable)
* **Weather Station:** Davis Vantage Pro2 (902–928 MHz ISM band)
* **Field Site:** Oaxaca de Juárez, Oaxaca, Mexico (~1,550 m a.s.l.), receiver ~15 m from the station

---

## 🚀 Quick Start & Reproducibility
```bash
# Clone repository
git clone https://github.com/Sibajx/davis-sdr-greenhouse.git
cd davis-sdr-greenhouse

# Install dependencies
pip install -r requirements.txt

# Run unit tests & CRC validation
pytest tests/
```

For full details on dataset processing and figure reproduction, refer to [`docs/REPRODUCIBILITY.md`](docs/REPRODUCIBILITY.md).

## 📜 License
This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
