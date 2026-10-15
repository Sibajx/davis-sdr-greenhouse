# Processed data

## `dataset_phase1_clean.csv`

Weather variables decoded by the SDR system from the Davis Vantage Pro 2,
one row per minute, 12–16 June 2026 (phase 1 tests, 7,167 rows). This is not
the paper's field-evaluation period (29 Aug–4 Sep 2026).

| Column | Meaning | Unit |
|---|---|---|
| `Fecha_Hora` | Timestamp, `DD/MM/YYYY HH:MM` | — |
| `Temp_C` | Air temperature | °C |
| `Humedad_%` | Relative humidity | % |
| `Viento_kmh` | Wind speed | km/h |
| `Direccion_Grados` | Wind direction | degrees |
| `Cardinal` | Wind direction as a compass point | — |
| `Rafaga_kmh` | Wind gust | km/h |
| `Lluvia_mm_h` | Rain rate | mm/h |
| `Hoja_0_15` | Leaf wetness (see note below) | 0–15 scale |
| `Indice_UV` | UV index | UVI |
| `Radiacion_W_m2` | Solar radiation | W/m² |
| `Bateria_TX` | Transmitter battery status | — |

### Notes

- **`Hoja_0_15` carries no measurement.** The station has no leaf wetness
  sensor installed; the transmitter still sends that packet type
  (`LEAF_MOISTURE`, `0xE`) and the column holds a constant 13 throughout.
  Do not use it in analyses.
- **Empty cells are invalid readings removed on purpose**, not missing
  rows. They are physically impossible values caused by reception glitches:
  - 13/06/2026 18:56–19:01: `Temp_C` of −10.3 °C (6 rows) and `Viento_kmh`
    of 56.3 km/h (18:56–18:57).
  - 14/06/2026 06:05–06:08: `Viento_kmh` of 154.5 km/h and
    `Radiacion_W_m2` of 1466.1 W/m² at dawn with a UV index of 0 (4 rows).

  The analysis scripts drop empty values with `dropna()`.
- Some minutes are missing (22 gaps of 1–8 min) because packets were not
  received; they were not interpolated.
