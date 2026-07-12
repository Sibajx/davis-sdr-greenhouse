# System architecture

See Figure 1 of the paper (`paper/IJSAMI.pdf`, section 3.6) for the full
diagram. Layer-by-layer summary:

## 1. Sensing and RF layer

- **Davis Vantage Pro 2**: integrated sensor suite (temperature, relative
  humidity, wind, rain, solar radiation, UV index).
- **FHSS telemetry** in the 902-928 MHz ISM band (channel hopping every few
  seconds), proprietary RF frames.
- **RTL-SDR**: low-cost receiver that replaces the proprietary console.

## 2. Edge processing layer

- **ARM/Linux computer** (Ubuntu aarch64).
- **Asynchronous Python daemon** (`src/davis_monitor.py`):
  - A dedicated thread for SDR listening (`rtldavis_reader_worker`), invokes
    the external binary `rtldavis -tf US` via `subprocess`.
  - Watchdog: if no RF activity is detected within 30 s
    (`MAX_SENSOR_WAIT_TIME`), the subprocess is terminated and restarted;
    restarts are logged in `SDRState.rtldavis_restarts`.
  - CRC-16 filter: each 8-byte frame is validated (6 payload bytes + 2 CRC
    bytes); corrupted frames are discarded before decoding.
  - Variable decoder: bit-level extraction depending on packet type
    (`PacketType`: wind/gust, temperature, humidity, rain, leaf moisture,
    solar radiation, UV index).
  - Lock-protected structures (`clone()` in `StationTelemetry` and
    `SDRState`) to avoid race conditions between the SDR thread and the
    main loop.

## 3. Storage and decision-support layer

- **Rotating log file** (`RotatingFileHandler`, 5 MB x 5 backups) at
  `~/davis_captures/davis_monitor.log`.
- **Local CSV backup** as a redundant black-box log in case of network or
  database failure.
- **Ingestion into a time-series database** (e.g. InfluxDB) every ~60 s
  (see Table 2 of the paper: mean interval 60.18 s, jitter 0.3815 s).
- **Dashboard/API** for querying the latest state (outside the scope of
  this repository in its current form).
- **Future CPS controller** (ESP32/PLC) for ventilation, heating, and vent
  actuators — not yet implemented; see the paper's "Future work" section.

## Reported reliability metrics

| Metric | Formula (see paper, section 3.9) | Result |
|---|---|---|
| PDR | N_valid / (N_valid + N_crc_errors) × 100 | 93.23% |
| MTTR | average of watchdog recovery times | 1.03 s |
| Writing jitter | standard deviation of intervals between DB writes | 0.3815 s |
| Empirical MTBF | mean time between receiver failures | 65.81 min |
| Weibull β | fit of failure inter-arrival times to a Weibull distribution | 0.3552 (<1, early-life failures) |

## Decoded packet identifiers (`PacketType`)

| Name | Hex code |
|---|---|
| WIND_GUST | 0x9 |
| TEMPERATURE | 0x8 |
| HUMIDITY | 0xA |
| RAIN_RATE | 0x5 |
| LEAF_MOISTURE | 0xE |
| SOLAR_RAD | 0x6 |
| UV_INDEX | 0x4 |
