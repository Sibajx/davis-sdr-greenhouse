cat > /tmp/REPRODUCIBILITY.md << 'EOF'
# Reproducibilidad de resultados del paper

## Entorno de evaluación

- **Ubicación:** Oaxaca de Juárez, Oaxaca (17°03'38" N, 96°43'31" W)
- **Período de evaluación:** 29 ago - 4 sep 2026
- **Distancia emisor-receptor:** 15 m
- **Plataforma:** Raspberry Pi 5, Ubuntu 24 (aarch64)

## Hardware exacto

| Componente | Modelo | Especificaciones |
|-----------|--------|-----------------|
| Computadora | Raspberry Pi 5 | 16 GB RAM, aarch64, Ubuntu 24 |
| Receptor SDR | Nooelec NESDR SMArt | RTL2832U + R820T2, 0.5 PPM TCXO |
| Antena | LoRa 915 MHz | Fibra de vidrio, RG58 de baja pérdida |
| Estación meteorológica | Davis Vantage Pro2 | 902-928 MHz ISM, FHSS |

## Instalación paso a paso

1. **Instalar dependencias del sistema**
   ```bash
   sudo apt update
   sudo apt install -y python3-venv python3-dev libsqlite3-dev \
       build-essential git python3-pip
   ```

2. **Instalar drivers RTL-SDR**
   ```bash
   sudo apt install -y rtl-sdr librtlsdr-dev librtlsdr0
   
   # Copiar reglas udev
   sudo cp deploy/99-rtlsdr.rules /etc/udev/rules.d/
   sudo udevadm control --reload-rules
   ```

3. **Configurar Python**
   ```bash
   git clone https://github.com/Sibajx/davis-sdr-greenhouse.git
   cd davis-sdr-greenhouse
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

4. **Configurar config.json**
   ```bash
   cp config.example.json config.json
   # Editar con frecuencias y rutas correctas
   nano config.json
   ```

## Ejecutar la evaluación

```bash
# Test unitarios
./run_tests.sh

# Verificar que el RTL-SDR se detecta
python -m davis_monitor --version
python -m davis_monitor --check-hardware

# Ejecutar adquisición en modo headless
python -m davis_monitor --mode headless --output data/raw/

# Interfaz TUI interactiva
python -m davis_monitor --mode tui
```

## Reproducir figuras del paper

```bash
# Analizar logs de consola Davis
python scripts/analizar_consola.py data/raw/YYYY-MM-DD.log

# Generar métricas de confiabilidad
python scripts/reliability_metrics.py data/raw/

# Plotear Bland-Altman
python scripts/bland_altman.py data/raw/sdr.csv data/raw/davis.csv
```

## Datos esperados

Después de 6 días, deberías tener:
- 8,612 registros validados en SQLite
- > 230,000 frames con CRC válido
- PDR ~95%
- MTBF ~90 minutos

## Resultados clave del paper

- **Mean Absolute Error (Temperature):** 0.156°C
- **Mean Absolute Error (Humidity):** 0.352%
- **Packet Delivery Ratio:** 95.10%
- **Mean Time Between Failures:** 90.95 min
- **Mean Time To Recovery:** 1.0 s
- **Database write interval:** 60.20 s (jitter: 0.398 s)
EOF
cat /tmp/REPRODUCIBILITY.md
Salida

# Reproducibilidad de resultados del paper

## Entorno de evaluación

- **Ubicación:** Oaxaca de Juárez, Oaxaca (17°03'38" N, 96°43'31" W)
- **Período de evaluación:** 29 ago - 4 sep 2026
- **Distancia emisor-receptor:** 15 m
- **Plataforma:** Raspberry Pi 5, Ubuntu 24 (aarch64)

## Hardware exacto

| Componente | Modelo | Especificaciones |
|-----------|--------|-----------------|
| Computadora | Raspberry Pi 5 | 16 GB RAM, aarch64, Ubuntu 24 |
| Receptor SDR | Nooelec NESDR SMArt | RTL2832U + R820T2, 0.5 PPM TCXO |
| Antena | LoRa 915 MHz | Fibra de vidrio, RG58 de baja pérdida |
| Estación meteorológica | Davis Vantage Pro2 | 902-928 MHz ISM, FHSS |

## Instalación paso a paso

1. **Instalar dependencias del sistema**
   ```bash
   sudo apt update
   sudo apt install -y python3-venv python3-dev libsqlite3-dev \
       build-essential git python3-pip
   ```

2. **Instalar drivers RTL-SDR**
   ```bash
   sudo apt install -y rtl-sdr librtlsdr-dev librtlsdr0
   
   # Copiar reglas udev
   sudo cp deploy/99-rtlsdr.rules /etc/udev/rules.d/
   sudo udevadm control --reload-rules
   ```

3. **Configurar Python**
   ```bash
   git clone https://github.com/Sibajx/davis-sdr-greenhouse.git
   cd davis-sdr-greenhouse
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

4. **Configurar config.json**
   ```bash
   cp config.example.json config.json
   # Editar con frecuencias y rutas correctas
   nano config.json
   ```

## Ejecutar la evaluación

```bash
# Test unitarios
./run_tests.sh

# Verificar que el RTL-SDR se detecta
python -m davis_monitor --version
python -m davis_monitor --check-hardware

# Ejecutar adquisición en modo headless
python -m davis_monitor --mode headless --output data/raw/

# Interfaz TUI interactiva
python -m davis_monitor --mode tui
```

## Reproducir figuras del paper

```bash
# Analizar logs de consola Davis
python scripts/analizar_consola.py data/raw/YYYY-MM-DD.log

# Generar métricas de confiabilidad
python scripts/reliability_metrics.py data/raw/

# Plotear Bland-Altman
python scripts/bland_altman.py data/raw/sdr.csv data/raw/davis.csv
```

## Datos esperados

Después de 6 días, deberías tener:
- 8,612 registros validados en SQLite
- > 230,000 frames con CRC válido
- PDR ~95%
- MTBF ~90 minutos

## Resultados clave del paper

- **Mean Absolute Error (Temperature):** 0.156°C
- **Mean Absolute Error (Humidity):** 0.352%
- **Packet Delivery Ratio:** 95.10%
- **Mean Time Between Failures:** 90.95 min
- **Mean Time To Recovery:** 1.0 s
- **Database write interval:** 60.20 s (jitter: 0.398 s)