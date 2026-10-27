This folder holds the raw inputs of the field evaluation (29 Aug – 4 Sep 2026)
that the figure scripts read. Scripts look for these files by bare name in
the working directory, so copy them here and run the scripts from this folder
(see `docs/REPRODUCIBILITY.md`, section 2.2):

| File | Contents |
|---|---|
| `historial_davis_2026-08-29.csv` … `historial_davis_2026-09-03.csv` | SDR-decoded records, one file per day |
| `davis_wifi_logger.csv` | Davis reference station records (validation) |
| `davis_monitor.log` | Daemon log: watchdog restarts and database writes |

Raw hexadecimal payloads or RF captures are not included; they are available
from the corresponding author on reasonable request.
