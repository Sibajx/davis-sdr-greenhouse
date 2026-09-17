# Davis Vantage Pro 2 Telemetry Decoding via RTL-SDR in Greenhouse Environments

[![CI/CD Pipeline](https://github.com/Sibajx/davis-sdr-greenhouse/actions/workflows/ci.yml/badge.svg)](https://github.com/Sibajx/davis-sdr-greenhouse/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Publication Status](https://img.shields.io/badge/Paper-Published_in_IJSAMI_Vol._20,_2026-blue.svg)](paper/)

Experimental validation and SDR telemetry decoding system for Davis Vantage Pro2 weather stations operating in the 902–928 MHz ISM band within greenhouse agricultural monitoring setups.

---

## 📄 Manuscript & Publication
* **Status:** Published in *IJSAMI Vol. 20, 2026*
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

---

## 🛠️ Hardware Requirements
* **Single Board Computer:** Raspberry Pi 5
* **SDR Receiver:** Nooelec NESDR SMArt v5 (RTL2832U / R820T2)
* **Weather Station:** Davis Vantage Pro2 (915 MHz ISM Band)

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
