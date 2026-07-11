# Arquitectura del sistema

Ver Figura 1 del paper (`paper/IJSAMI.pdf`, sección 3.6) para el diagrama completo.
Resumen por capas:

## 1. Capa de sensado y RF

- **Davis Vantage Pro 2**: suite de sensores integrada (temperatura, humedad
  relativa, viento, lluvia, radiación solar, índice UV).
- **Telemetría FHSS** en la banda ISM 902–928 MHz (salto de canal cada pocos
  segundos), tramas RF propietarias.
- **RTL-SDR**: receptor de bajo costo que sustituye a la consola propietaria.

## 2. Capa de procesamiento de borde (edge)

- **Computadora ARM/Linux** (Ubuntu aarch64).
- **Daemon Python asíncrono** (`src/davis_monitor.py`):
  - Un hilo dedicado a la escucha SDR (`lector_rtldavis_worker`), invoca el
    binario externo `rtldavis -tf US` vía `subprocess`.
  - Watchdog: si no hay actividad de RF en 30 s, se termina y reinicia el
    subproceso (`TIEMPO_MAX_ESPERA_SENSORES`, reinicios registrados en
    `EstadoSDR.reinicios_rtldavis`).
  - Filtro CRC-16: cada trama de 8 bytes se valida (6 bytes de payload + 2
    bytes de CRC); las tramas corruptas se descartan antes de decodificar.
  - Decodificador de variables: extracción bit a bit según el tipo de paquete
    (`TipoPaquete`: viento/ráfaga, temperatura, humedad, lluvia, humedad de
    hoja, radiación solar, índice UV).
  - Estructuras protegidas por locks (`clonar()` en `TelemetriaEstacion` y
    `EstadoSDR`) para evitar condiciones de carrera entre el hilo SDR y el
    bucle principal.

## 3. Capa de almacenamiento y soporte de decisiones

- **Log rotativo** (`RotatingFileHandler`, 5 MB x 5 backups) en
  `~/capturas_davis/davis_monitor.log`.
- **Respaldo local en CSV** como bitácora redundante ante fallos de red o de
  base de datos.
- **Ingesta a base de datos de series temporales** (ej. InfluxDB) cada ~60 s
  (ver Tabla 2 del paper: intervalo medio 60.18 s, jitter 0.3815 s).
- **Dashboard/API** para consulta de estado reciente (fuera del alcance de
  este repositorio en su estado actual).
- **Controlador CPS futuro** (ESP32/PLC) para actuadores de ventilación,
  calefacción y persianas — no implementado aún; ver sección "Future work"
  del paper.

## Métricas de confiabilidad reportadas

| Métrica | Fórmula (ver paper, sección 3.9) | Resultado |
|---|---|---|
| PDR | N_válidos / (N_válidos + N_error_CRC) × 100 | 93.23% |
| MTTR | promedio de tiempos de recuperación del watchdog | 1.03 s |
| Jitter de escritura | desviación estándar de intervalos entre escrituras en BD | 0.3815 s |
| MTBF empírico | tiempo medio entre fallos del receptor | 65.81 min |
| Weibull β | ajuste de tiempos entre fallos a distribución Weibull | 0.3552 (<1, fallas tempranas) |

## Identificadores de paquete decodificados (`TipoPaquete`)

| Nombre | Código hex |
|---|---|
| VIENTO_RAFAGA | 0x9 |
| TEMPERATURE | 0x8 |
| HUMIDITY | 0xA |
| RAIN_RATE | 0x5 |
| LEAF_MOISTURE | 0xE |
| SOLAR_RAD | 0x6 |
| UV_INDEX | 0x4 |
