# Davis SDR Greenhouse — Low-Cost SDR-Based Edge IoT Architecture

![CI](https://github.com/Sibajx/davis-sdr-greenhouse/actions/workflows/ci.yml/badge.svg)
![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.9%2B-blue.svg)
![Status](https://img.shields.io/badge/paper-in%20review-yellow.svg)

Arquitectura IoT de borde (edge), basada en radio definida por software (SDR), para
la recepción, validación, decodificación y almacenamiento en tiempo real de la
telemetría meteorológica de una estación **Davis Vantage Pro 2** (banda ISM
902–928 MHz), pensada como capa de datos externa para el control futuro de un
sistema de secado en invernadero (cyber-physical drying system).

Este repositorio acompaña el artículo:

> Juárez-Rosales, M.U., Ramírez-Sibaja, A., Cruz-Martínez, M.S., Nicolas-Bautista, H.,
> Sánchez-Domínguez, D. y Hernández-Flores, O.A. *A Low-Cost SDR-Based Edge IoT
> Architecture for Real-Time Decoding of Weather Telemetry in Cyber-Physical
> Greenhouse Drying Systems*. International Journal of Sustainable Agricultural
> Management and Informatics (en revisión).

## Resultados principales (evaluación de campo, 12–16 junio 2026)

| Métrica | Valor |
|---|---|
| Registros validados en base de datos | 7,167 |
| Paquetes interceptados (estimado) | 184,508 |
| Packet Delivery Ratio (PDR) | 93.23% |
| Intervenciones del watchdog | 154 |
| Tiempo medio de recuperación (MTTR) | 1.03 s |
| Intervalo medio de escritura en BD | 60.18 s |
| Jitter de escritura | 0.3815 s |
| MTBF empírico | 65.81 min |
| Parámetro de forma Weibull (β) | 0.3552 |

## Estructura del repositorio

```
├── paper/            Manuscrito completo (PDF)
├── src/               Código fuente del daemon de adquisición (Python, stdlib)
├── data/
│   ├── raw/           Muestras crudas / payloads hexadecimales (si se agregan)
│   └── processed/     Dataset limpio usado para las figuras del paper
├── logs/              Fragmento representativo del log de operación
├── figures/           Figuras del paper (temperatura, humedad, solar/UV)
│   └── exploratorio/  Gráficas exploratorias adicionales (no incluidas en el paper)
├── scripts/           Scripts auxiliares (generación de figuras, análisis)
├── tests/             Pruebas unitarias (CRC-16, decodificación de dirección)
├── docs/              Documentación de arquitectura y notas técnicas
└── .github/workflows/ Integración continua (CI): compilación, lint y tests
```

## Requisitos

- Python 3.9+ (solo librería estándar — ver `requirements.txt`)
- [`rtldavis`](https://github.com/rtldavis) instalado y accesible en el `PATH`
  (binario externo, no es un paquete de Python; se invoca vía `subprocess`)
- Un receptor RTL-SDR conectado por USB
- Linux (probado en ARM/aarch64, Ubuntu Server)

## Uso

```bash
# 1. Instalar y verificar rtldavis
rtldavis -tf US   # debe detectar actividad de la estación Davis

# 2. Ejecutar el monitor
python3 src/davis_monitor.py
```

El script:
- Lanza `rtldavis` en un hilo dedicado y seis lecturas de payload hexadecimal.
- Valida cada trama con CRC-16 (descarta tramas corruptas).
- Decodifica viento, temperatura, humedad, radiación solar, índice UV y lluvia.
- Escribe un log rotativo (`~/capturas_davis/davis_monitor.log`) y un respaldo CSV local.
- Reinicia automáticamente el subproceso SDR si no detecta actividad de RF en 30 s
  (watchdog).

## Pruebas

Las funciones puras de decodificación (validación CRC-16, conversión de
grados a punto cardinal) tienen pruebas unitarias en `tests/`:

```bash
pip install pytest
pytest tests/ -v
```

Estas pruebas se ejecutan automáticamente en cada push/PR vía GitHub Actions
(`.github/workflows/ci.yml`), junto con una verificación de sintaxis
(`py_compile`) y un lint mínimo (`flake8`, solo errores graves de sintaxis o
nombres indefinidos).

## Mejoras recomendadas / trabajo futuro sobre el código

- Separar constantes de configuración (`TIEMPO_MAX_ESPERA_SENSORES`,
  `TX_ID_OBJETIVO`, rutas de directorios) en un archivo `config.yaml` o
  variables de entorno, en lugar de constantes embebidas en el módulo.
- Ampliar la cobertura de pruebas a las funciones de decodificación de
  temperatura, humedad, radiación solar e índice UV (actualmente solo se
  prueban CRC-16 y dirección de viento).
- Agregar payloads de ejemplo reales en `data/raw/` para usarlos como casos
  de prueba deterministas.
- Notebook de validación contra datalogger Davis (`scripts/`) cuando esos
  datos estén disponibles, calculando bias, MAE, RMSE y correlación, tal
  como se describe en la sección 3.8 del paper.

## Datos

`data/processed/dataset_fase1_limpio.csv` contiene el dataset limpio (7,168 filas,
1 min de resolución) usado para generar las Figuras 2–4 del paper: temperatura,
humedad relativa, viento, radiación solar, índice UV, lluvia y estado de batería
del transmisor.

## Disponibilidad de datos y código

El código fuente completo, los logs anonimizados, los datasets procesados y los
scripts de generación de figuras se depositarán en un repositorio público antes
del envío final o revisión por pares, o estarán disponibles bajo petición razonable
al autor de correspondencia (ver sección *Data and Code Availability* del paper).
El log completo de operación (>10,000 líneas) no se incluye completo en este
repositorio por su tamaño y redundancia; `logs/davis_monitor_sample.log` contiene
un fragmento representativo.

## Declaración ética y de interoperabilidad

Este flujo de decodificación SDR fue desarrollado con fines de investigación
académica e interoperabilidad, para integrar un equipo de sensado ambiental
propiedad de los autores en un sistema ciberfísico agrícola propio. El sistema
realiza **recepción pasiva** de telemetría de la propia estación y no está
diseñado para interferir con sistemas de comunicación de terceros. Verifica la
normativa de radiofrecuencia local antes de cualquier despliegue en campo.

## Cómo citar

Cita pendiente de asignación de volumen/número/DOI tras la publicación final.
Mientras tanto, referencia este repositorio y el título del manuscrito indicado
arriba.

## Licencia

Código bajo licencia MIT (ver `LICENSE`). El manuscrito y las figuras del paper
están sujetos a los términos de copyright de la revista (Inderscience
Enterprises Ltd.) y se incluyen aquí únicamente como referencia del trabajo
correspondiente al código.
