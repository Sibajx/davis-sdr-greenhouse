# Davis SDR Greenhouse — Low-Cost SDR-Based Edge IoT Architecture

![CI](https://github.com/Sibajx/davis-sdr-greenhouse/actions/workflows/ci.yml/badge.svg)
![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.9%2B-blue.svg)
![Status](https://img.shields.io/badge/paper-in%20review-yellow.svg)

Edge Internet-of-Things (IoT) architecture, based on software-defined radio
(SDR), for the real-time reception, validation, decoding, and storage of
weather telemetry from a **Davis Vantage Pro 2** station (902-928 MHz ISM
band), designed as an external data layer for the future control of a
greenhouse fruit-drying system (cyber-physical drying system).

This repository accompanies the paper:

> Juárez-Rosales, M.U., Ramírez-Sibaja, A., Cruz-Martínez, M.S., Nicolas-Bautista, H.,
> Sánchez-Domínguez, D. and Hernández-Flores, O.A. *A Low-Cost SDR-Based Edge IoT
> Architecture for Real-Time Decoding of Weather Telemetry in Cyber-Physical
> Greenhouse Drying Systems*. International Journal of Sustainable Agricultural
> Management and Informatics (in review).

## Key results (field evaluation, June 12-16, 2026)

| Metric | Value |
|---|---|
| Validated database records | 7,167 |
| Estimated intercepted packets | 184,508 |
| Packet Delivery Ratio (PDR) | 93.23% |
| Watchdog interventions | 154 |
| Mean time to recovery (MTTR) | 1.03 s |
| Mean database writing interval | 60.18 s |
| Writing jitter | 0.3815 s |
| Empirical MTBF | 65.81 min |
| Weibull shape parameter (β) | 0.3552 |

## Repository structure

```
├── paper/            Full manuscript (PDF)
├── src/               Source code of the acquisition daemon (Python, stdlib)
├── data/
│   ├── raw/           Raw samples / hexadecimal payloads (if added)
│   └── processed/     Cleaned dataset used for the paper's figures
├── logs/              Representative excerpt of the operation log
├── figures/           Paper figures (temperature, humidity, solar/UV)
│   └── exploratory/   Additional exploratory plots (not included in the paper)
├── scripts/           Auxiliary scripts (figure generation, analysis)
├── tests/             Unit tests (CRC-16, direction decoding)
├── docs/              Architecture documentation and technical notes
└── .github/workflows/ Continuous integration (CI): build, lint, and tests
```

## Requirements

- Python 3.9+ (standard library only — see `requirements.txt`)
- [`rtldavis`](https://github.com/rtldavis) installed and available on the
  `PATH` (external binary, not a Python package; invoked via `subprocess`)
- An RTL-SDR receiver connected via USB
- Linux (tested on ARM/aarch64, Ubuntu Server)

## Usage

```bash
# 1. Install and verify rtldavis
rtldavis -tf US   # should detect activity from the Davis station

# 2. Run the monitor
python3 src/davis_monitor.py
```

The script:
- Launches `rtldavis` in a dedicated thread and reads hexadecimal payloads.
- Validates each frame with CRC-16 (discards corrupted frames).
- Decodes wind, temperature, humidity, solar radiation, UV index, and rain.
- Writes a rotating log (`~/davis_captures/davis_monitor.log`) and a local
  CSV backup.
- Automatically restarts the SDR subprocess if no RF activity is detected
  within 30 s (watchdog).

## Tests

The pure decoding functions (CRC-16 validation, degrees-to-cardinal
conversion) have unit tests in `tests/`:

```bash
pip install pytest
pytest tests/ -v
```

These tests run automatically on every push/PR via GitHub Actions
(`.github/workflows/ci.yml`), along with a syntax check (`py_compile`) and
a minimal lint (`flake8`, serious syntax or undefined-name errors only).

## Recommended improvements / future work on the code

- Separate configuration constants (`MAX_SENSOR_WAIT_TIME`,
  `TARGET_TX_ID`, directory paths) into a `config.yaml` file or environment
  variables, instead of constants embedded in the module.
- Expand test coverage to the temperature, humidity, solar radiation, and
  UV index decoding functions (currently only CRC-16 and wind direction
  are tested).
- Add real sample payloads to `data/raw/` to use as deterministic test
  cases.
- Notebook for validation against the Davis datalogger (`scripts/`) once
  that data is available, computing bias, MAE, RMSE, and correlation, as
  described in section 3.8 of the paper.

## Data

`data/processed/dataset_phase1_clean.csv` contains the cleaned dataset
(7,168 rows, 1-minute resolution) used to generate Figures 2-4 of the
paper: temperature, relative humidity, wind, solar radiation, UV index,
rain, and transmitter battery state.

## Data and code availability

The full source code, anonymized logs, processed datasets, and
figure-generation scripts will be deposited in a public repository before
final submission or peer review, or will be made available upon reasonable
request to the corresponding author (see the "Data and Code Availability"
section of the paper). The full operation log (>10,000 lines) is not
included in full in this repository due to its size and redundancy;
`logs/davis_monitor_sample.log` contains a representative excerpt.

## Ethical and interoperability statement

This SDR decoding workflow was developed for academic research and
interoperability purposes, to integrate environmental sensing equipment
owned by the authors into a custom agricultural cyber-physical system. The
system performs **passive reception** of telemetry from the authors' own
station and is not intended to interfere with third-party communication
systems. Verify local radiofrequency regulations before any field
deployment.

## How to cite

Citation pending assignment of volume/issue/DOI after final publication.
In the meantime, reference this repository and the manuscript title listed
above.

## License

Code under the MIT license (see `LICENSE`). The paper manuscript and its
figures are subject to the journal's copyright terms (Inderscience
Enterprises Ltd.) and are included here only as a reference for the
corresponding code.
