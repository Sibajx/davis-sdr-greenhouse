"""
davis_monitor.py
=================

Daemon de adquisición SDR para telemetría meteorológica de una estación
Davis Vantage Pro 2 (banda ISM 902-928 MHz, FHSS), usado como capa de borde
(edge) de un sistema ciberfísico de secado en invernadero.

Flujo general (ver docs/arquitectura.md para el diagrama completo):

    1. Hilo SDR (lector_rtldavis_worker): lanza el binario externo
       `rtldavis -tf US` vía subprocess y lee payloads hexadecimales de su
       stdout. Un watchdog reinicia el subproceso si no hay actividad de RF
       dentro de TIEMPO_MAX_ESPERA_SENSORES segundos.
    2. Validación CRC-16 (DecodificadorDavis.validar_crc): cada trama de
       8 bytes se valida contra los 2 últimos bytes (CRC recibido); las
       tramas corruptas se descartan antes de decodificar.
    3. Decodificación (NucleoMonitoreo.procesar_trama): extrae viento,
       temperatura, humedad, radiación solar, índice UV y lluvia según el
       tipo de paquete (TipoPaquete), usando desplazamientos de bits sobre
       el payload.
    4. Persistencia (GestorAlmacenamiento): respaldo local en CSV y logging
       rotativo; la ingesta a base de datos de series temporales (ej.
       InfluxDB) ocurre cada ~60 s aguas abajo.
    5. Interfaz (MotorInterfazTUI): panel de consola en tiempo real basado
       en curses, con brújula de viento, sparklines de tendencias y estado
       del watchdog.

Requiere Python 3.9+ (solo librería estándar) y el binario externo
`rtldavis` disponible en el PATH del sistema. Ver requirements.txt.
"""

import subprocess
import curses
import threading
import time
import os
import re
import csv
import sys
import signal
import select
import struct
import logging
from logging.handlers import RotatingFileHandler
from enum import Enum
from dataclasses import dataclass, field
from collections import deque
from datetime import datetime
from typing import Dict, Optional

# === CONFIGURACIÓN GLOBAL ===
DIR_CAPTURAS: str = os.path.expanduser("~/capturas_davis")
os.makedirs(DIR_CAPTURAS, exist_ok=True)

# === LOGGING ===
LOG_FILE = os.path.join(DIR_CAPTURAS, "davis_monitor.log")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(threadName)s: %(message)s',
    handlers=[
        RotatingFileHandler(
            LOG_FILE,
            maxBytes=5 * 1024 * 1024,
            backupCount=5,
            encoding='utf-8'
        )
        # BÓRRALE LA LÍNEA QUE DECÍA: logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger("DavisMonitor")

# ¡CORRECCIÓN APLICADA AQUÍ! (Tu estación usa el ID 0)
TX_ID_OBJETIVO: str = "0"
TIEMPO_MAX_ESPERA_SENSORES: int = 300 

class TipoPaquete(Enum):
    VIENTO_RAFAGA  = 0x9
    TEMPERATURE    = 0x8
    HUMIDITY       = 0xA
    RAIN_RATE      = 0x5
    LEAF_MOISTURE  = 0xE
    SOLAR_RAD      = 0x6
    UV_INDEX       = 0x4

@dataclass
class TelemetriaEstacion:
    __slots__ = (
        'viento_vel', 'viento_dir', 'viento_cardinal', 'rafaga',
        'temp', 'humedad', 'tasa_lluvia', 'estado_lluvia',
        'humedad_hoja', 'uv', 'meds', 'solar', 'tx_id', 'bateria'
    )
    viento_vel: str; viento_dir: str; viento_cardinal: str; rafaga: str
    temp: str; humedad: str; tasa_lluvia: str; estado_lluvia: str
    humedad_hoja: str; uv: str; meds: str; solar: str; tx_id: str; bateria: str

    @classmethod
    def inicializar_vacio(cls) -> 'TelemetriaEstacion':
        return cls(
            viento_vel="--", viento_dir="--", viento_cardinal="--", rafaga="--",
            temp="--", humedad="--", tasa_lluvia="--", estado_lluvia="--",
            humedad_hoja="--", uv="--", meds="--", solar="--", tx_id="-", bateria="-"
        )
    
    def clonar(self) -> 'TelemetriaEstacion':
        """Crea una copia física de los datos para liberar el Lock rápidamente."""
        return TelemetriaEstacion(
            viento_vel=self.viento_vel, viento_dir=self.viento_dir, viento_cardinal=self.viento_cardinal,
            rafaga=self.rafaga, temp=self.temp, humedad=self.humedad, tasa_lluvia=self.tasa_lluvia,
            estado_lluvia=self.estado_lluvia, humedad_hoja=self.humedad_hoja, uv=self.uv,
            meds=self.meds, solar=self.solar, tx_id=self.tx_id, bateria=self.bateria
        )

@dataclass
class EstadoSDR:
    freq: str = "Buscando..."
    canal: str = "-"
    paquetes: int = 0
    paquetes_descartados_crc: int = 0
    paquetes_descartados_id: int = 0
    reinicios_rtldavis: int = 0
    ultimo_reinicio: str = "Nunca"
    ultimo_guardado_csv: float = 0.0
    estado_csv: str = "Esperando..."
    ultima_actividad_rf: float = field(default_factory=time.time)
    ultima_trama: str = ""

    def clonar(self) -> 'EstadoSDR':
        return EstadoSDR(
            freq=self.freq, canal=self.canal, paquetes=self.paquetes,
            paquetes_descartados_crc=self.paquetes_descartados_crc,
            paquetes_descartados_id=self.paquetes_descartados_id,
            reinicios_rtldavis=self.reinicios_rtldavis, ultimo_reinicio=self.ultimo_reinicio,
            ultimo_guardado_csv=self.ultimo_guardado_csv, estado_csv=self.estado_csv,
            ultima_actividad_rf=self.ultima_actividad_rf, ultima_trama=self.ultima_trama
        )

class AnalizadorTendencias:
    def __init__(self, maxlen: int = 10):
        self._historial = deque(maxlen=maxlen)

    def registrar_y_obtener_flecha(self, valor_str: str) -> str:
        try:
            valor = float(valor_str)
            if not self._historial:
                self._historial.append(valor)
                return "─"
            promedio = sum(self._historial) / len(self._historial)
            self._historial.append(valor)
            if valor > promedio + 0.1: return "▲"
            elif valor < promedio - 0.1: return "▼"
            return "─"
        except ValueError:
            return "─"

class GestorAlmacenamiento:
    def __init__(self, directorio: str):
        self.directorio = directorio

    def registrar_datos(self, hub: TelemetriaEstacion) -> None:
        fecha_hoy = datetime.now().strftime('%Y-%m-%d')

        archivo_csv = os.path.join(
            self.directorio,
            f"historial_davis_{fecha_hoy}.csv"
        )

        existe = os.path.isfile(archivo_csv)

        fila = [
            datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            hub.temp,
            hub.humedad,
            hub.viento_vel,
            hub.viento_dir,
            hub.viento_cardinal,
            hub.rafaga,
            hub.tasa_lluvia,
            hub.humedad_hoja,
            hub.uv,
            hub.solar,
            hub.bateria
        ]

        try:
            with open(
                archivo_csv,
                mode='a',
                newline='',
                encoding='utf-8'
            ) as f:

                escritor = csv.writer(f)

                if not existe:
                    escritor.writerow([
                        "Fecha_Hora",
                        "Temp_C",
                        "Humedad_%",
                        "Viento_kmh",
                        "Direccion_Grados",
                        "Cardinal",
                        "Rafaga_kmh",
                        "Lluvia_mm_h",
                        "Hoja_0_15",
                        "Indice_UV",
                        "Radiacion_W_m2",
                        "Bateria_TX"
                    ])

                escritor.writerow(fila)

        except IOError as e:
            logger.exception(f"Error escribiendo CSV: {e}")

class DecodificadorDavis:
    @staticmethod
    def validar_crc(hex_str: str) -> bool:
        try:
            data = bytes.fromhex(hex_str)
            if len(data) < 8: return False
            crc = 0
            for byte in data[:6]:
                crc ^= byte << 8
                for _ in range(8):
                    if crc & 0x8000: crc = (crc << 1) ^ 0x1021
                    else: crc <<= 1
                    crc &= 0xFFFF
            return crc == (data[6] << 8 | data[7])
        except Exception as e:
            logger.exception(f"Error validando CRC: {e}")
            return False

    @staticmethod
    def grados_a_cardinal(grados: float) -> str:
        direcciones = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", 
                       "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
        return direcciones[round(grados / 22.5) % 16]

class NucleoMonitoreo:
    def __init__(self, db_manager: GestorAlmacenamiento):
        self.hub = TelemetriaEstacion.inicializar_vacio()
        self.sdr = EstadoSDR()
        self.db = db_manager
        self.lock = threading.Lock()  # Protege TODA mutación entre hilos
        self.shutdown_event = threading.Event()
        self.proc_rtldavis: Optional[subprocess.Popen] = None
        self.hora_inicio = time.time()
        
        self.tendencia_temp = AnalizadorTendencias()
        self.tendencia_viento = AnalizadorTendencias()
        self.arrow_temp = "─"
        self.arrow_viento = "─"
        
        # === HISTÓRICOS EN RAM ===
        self.hist_temp = deque(maxlen=120)
        self.hist_humedad = deque(maxlen=120)
        self.hist_viento = deque(maxlen=120)
        self.hist_uv = deque(maxlen=120)

    def procesar_trama(self, hex_str: str) -> bool:

        with self.lock:

            # Validación básica y CRC
            if len(hex_str) < 16 or not DecodificadorDavis.validar_crc(hex_str):

                self.sdr.paquetes_descartados_crc += 1

                if self.sdr.paquetes_descartados_crc % 100 == 0:
                    logger.warning(
                        f"CRC inválidos acumulados: "
                        f"{self.sdr.paquetes_descartados_crc}"
                    )

                return False

            try:

                data = bytes.fromhex(hex_str[:10])

                if len(data) != 5:
                    return False

                b0, b1, b2, b3, b4 = struct.unpack(">BBBBB", data)

                tx_id_detectado = str((b0 >> 1) & 0x07)

                if tx_id_detectado != TX_ID_OBJETIVO:
                    self.sdr.paquetes_descartados_id += 1
                    return False

                updates: Dict[str, str] = {
                    "tx_id": tx_id_detectado,
                    "bateria": "Baja" if (b0 & 0x01) else "OK",
                    "viento_vel": f"{(b1 * 1.60934):.1f}"
                }

                # Historial viento
                if updates["viento_vel"] != "--":
                    self.hist_viento.append(
                        float(updates["viento_vel"])
                    )

                self.arrow_viento = (
                    self.tendencia_viento
                    .registrar_y_obtener_flecha(
                        updates["viento_vel"]
                    )
                )

                # Dirección viento
                direccion_grados = (b2 * 360) / 255.0

                updates["viento_dir"] = f"{direccion_grados:.0f}"

                updates["viento_cardinal"] = (
                    DecodificadorDavis.grados_a_cardinal(
                        direccion_grados
                    )
                )

                # Tipo paquete
                try:

                    tipo = TipoPaquete(b0 >> 4)

                    # TEMPERATURA
                    if tipo == TipoPaquete.TEMPERATURE:
                        raw_temp = (b3 << 8) | b4
                        if raw_temp >= 32768:
                            raw_temp -= 65536

                        celsius = (((raw_temp / 160.0) - 32) * 5.0 / 9.0)
                        celsius_str = f"{celsius:.1f}"

                        updates["temp"] = celsius_str
                        self.hist_temp.append(celsius)

                        self.arrow_temp = (
                            self.tendencia_temp
                            .registrar_y_obtener_flecha(celsius_str)
                        )

                    # HUMEDAD
                    elif tipo == TipoPaquete.HUMIDITY:
                        texto_concatenado= hex_str[8] + hex_str[6:8]
                        hum=int(texto_concatenado, 16) /10.0
                        hum=min(hum, 100.0)
                        updates["humedad"] = f"{hum:.1f}"
                        self.hist_humedad.append(hum)

                    # LLUVIA
                    elif tipo == TipoPaquete.RAIN_RATE:
                        if hex_str[6:8].upper() == "FF":
                            updates["estado_lluvia"] = "⚪ Seco"
                            updates["tasa_lluvia"] = "0.0"
                        else:
                            rain = (int(hex_str[8] + hex_str[6:8], 16) * 0.2)
                            updates["estado_lluvia"] = "🔴 Lloviendo"
                            updates["tasa_lluvia"] = f"{rain:.1f}"

                    # HUMEDAD HOJA
                    elif tipo == TipoPaquete.LEAF_MOISTURE:
                        leaf_raw = int(hex_str[8] + hex_str[6:8], 16)
                        if leaf_raw > 15:
                            valor = min(round(leaf_raw / 10.0), 15)
                        else:
                            valor = leaf_raw
                        updates["humedad_hoja"] = str(valor)

                    # RAFAGA
                    elif tipo == TipoPaquete.VIENTO_RAFAGA:
                        updates["rafaga"] = f"{(b3 * 1.60934):.1f}"

                    # SOLAR
                    elif tipo == TipoPaquete.SOLAR_RAD:
                        sr_raw = (((b3 << 2) | (b4 >> 6)) & 0x3FF)
                        if sr_raw < 0x3FF:
                            updates["solar"] = f"{(sr_raw * 1.757936):.1f}"
                        else:
                            updates["solar"] = "N/A"

                    # UV
                    elif tipo == TipoPaquete.UV_INDEX:
                        uv_raw = (((b3 << 2) | (b4 >> 6)) & 0x3FF)
                        if uv_raw < 0x3FF:
                            uv = uv_raw / 50.0
                            updates["uv"] = f"{uv:.1f}"
                            self.hist_uv.append(uv)
                            
                            meds = uv * (3.0 / 7.0)
                            updates["meds"] = f"{meds:.2f}"
                        else:
                            updates["uv"] = "N/A"
                            updates["meds"] = "N/A"

                except ValueError:
                    pass

                # Aplicar updates atómicamente
                for k, v in updates.items():
                    setattr(self.hub, k, v)

                return True

            except Exception as e:
                logger.exception(f"Error procesando trama [{hex_str}]: {e}")
                return False
                
    def lector_rtldavis_worker(self) -> None:
        # BORRA el '-g', '40' para que quede exactamente así:
        cmd = ['rtldavis', '-tf', 'US']

        regex_hop = re.compile(r'ChannelIdx:(\d+) ChannelFreq:(\d+)')
        regex_time = re.compile(r'^\d{2}:\d{2}:\d{2}\.\d+')

        logger.info("Iniciando hilo SDR rtldavis")
        timeout_counter = 0

        while not self.shutdown_event.is_set():
            try:
                with self.lock:
                    self.sdr.ultima_actividad_rf = time.time()

                self.proc_rtldavis = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1
                )

                logger.info("Proceso rtldavis iniciado")

                while not self.shutdown_event.is_set():

                    if self.proc_rtldavis is None or self.proc_rtldavis.stdout is None:
                        logger.warning("rtldavis no tiene stdout disponible")
                        break

                    # Espera máxima 1 segundo
                    ready, _, _ = select.select([self.proc_rtldavis.stdout], [], [], 1.0)

                    if not ready:
                        timeout_counter += 1
                        if timeout_counter >= 30:
                            logger.warning(f"Sin actividad RF durante {timeout_counter} segundos")
                        continue

                    stdout = self.proc_rtldavis.stdout
                    linea = stdout.readline()

                    if not linea:
                        logger.warning("rtldavis terminó o cerró stdout")
                        break

                    linea = linea.strip()
                    if not linea:
                        continue

                    timeout_counter = 0

                    with self.lock:
                        self.sdr.ultima_actividad_rf = time.time()

                    if "Hop:" in linea:
                        match = regex_hop.search(linea)
                        if match:
                            with self.lock:
                                self.sdr.canal = match.group(1)
                                self.sdr.freq = f"{int(match.group(2)) / 1000000.0:.3f}"

                    elif (regex_time.match(linea) and "Hop:" not in linea and "ppm" not in linea):
                        partes = linea.split(maxsplit=1)
                        if len(partes) > 1:
                            trama_limpia = partes[1].split()[0]

                            with self.lock:
                                self.sdr.ultima_trama = partes[1]

                            if self.procesar_trama(trama_limpia):
                                with self.lock:
                                    self.sdr.paquetes += 1

            except Exception as e:
                logger.exception(f"Error en lector_rtldavis_worker: {e}")

            finally:
                if self.proc_rtldavis is not None:
                    try:
                        self.proc_rtldavis.terminate()
                    except (OSError, subprocess.SubprocessError):
                        pass
                    self.proc_rtldavis = None

            time.sleep(1)

    def obtener_instantanea(self) -> tuple:
        """Devuelve copias seguras desconectadas de los hilos para evitar Race Conditions."""
        with self.lock:
            return (
                self.hub.clonar(),
                self.sdr.clonar(),
                self.arrow_temp,
                self.arrow_viento,
                list(self.hist_temp),
                list(self.hist_viento)
            )

    def forzar_reinicio_sdr(self, ahora: float) -> None:
        with self.lock:
            self.sdr.reinicios_rtldavis += 1
            logger.warning("Watchdog SDR activado: reiniciando rtldavis")
            self.sdr.ultimo_reinicio = datetime.now().strftime('%H:%M:%S')
            self.sdr.freq = "Reiniciando..."
            self.sdr.canal = "-"

        if self.proc_rtldavis:
            try:
                self.proc_rtldavis.terminate()
            except Exception as e:
                logger.exception(f"Error terminando proceso rtldavis: {e}")

        with self.lock:
            self.sdr.ultima_actividad_rf = ahora

    def actualizar_estado_csv(self, texto: str, tiempo_guardado: Optional[float] = None) -> None:
        with self.lock:
            self.sdr.estado_csv = texto
            if tiempo_guardado is not None:
                self.sdr.ultimo_guardado_csv = tiempo_guardado

    def verificar_datos_completos(self) -> bool:
        if time.time() - self.hora_inicio > TIEMPO_MAX_ESPERA_SENSORES: return True
        with self.lock:
            return all(getattr(self.hub, attr) != "--" for attr in self.hub.__slots__)

    def finalizar(self) -> None:
        self.shutdown_event.set()
        if self.proc_rtldavis:
            try:
                self.proc_rtldavis.terminate()
                self.proc_rtldavis.wait(timeout=1)
            except Exception as e:
                logger.exception(f"Error cerrando rtldavis limpiamente: {e}")
                try:
                    self.proc_rtldavis.kill()
                except Exception as kill_error:
                    logger.exception(f"Error forzando kill de rtldavis: {kill_error}")


class MotorInterfazTUI:
    def __init__(self, nucleo: NucleoMonitoreo):
        self.core = nucleo

    @staticmethod
    def safe_addstr(stdscr, y: int, x: int, text: str, attr: int = 0) -> None:
        try:
            stdscr.addstr(y, x, text, attr)
        except curses.error:
            pass

    @staticmethod
    def seguro_float(val_str: str) -> float:
        try:
            return float(val_str)
        except ValueError:
            return 0.0

    @staticmethod
    def generar_sparkline(datos, ancho=20):
        if not datos:
            return "─" * ancho

        bloques = "▁▂▃▄▅▆▇█"
        datos = list(datos)[-ancho:]
        minimo = min(datos)
        maximo = max(datos)

        if maximo == minimo:
            return bloques[0] * len(datos)

        resultado = ""
        for valor in datos:
            indice = int((valor - minimo) / (maximo - minimo) * (len(bloques) - 1))
            resultado += bloques[indice]

        return resultado

    def dibujar_contenedor(self, stdscr, y: int, x: int, alto: int, ancho: int, titulo: str) -> None:
        c_borde = curses.color_pair(1)
        c_titulo = curses.color_pair(5) | curses.A_BOLD

        self.safe_addstr(stdscr, y, x, "╭" + "─" * (ancho - 2) + "╮", c_borde)
        for i in range(1, alto - 1):
            self.safe_addstr(stdscr, y + i, x, "│", c_borde)
            self.safe_addstr(stdscr, y + i, x + ancho - 1, "│", c_borde)

        self.safe_addstr(stdscr, y + alto - 1, x, "╰" + "─" * (ancho - 2) + "╯", c_borde)
        self.safe_addstr(stdscr, y, x + 3, f" {titulo} ", c_titulo)

    def dibujar_brujula(self, stdscr, y: int, x: int, cardinal: str) -> None:
        c_base = curses.color_pair(7) | curses.A_BOLD
        c_act = curses.color_pair(4) | curses.A_BOLD
        c_txt = curses.color_pair(6)

        self.safe_addstr(stdscr, y + 1, x + 6, "│", c_base)
        self.safe_addstr(stdscr, y + 2, x + 2, "────┼────", c_base)
        self.safe_addstr(stdscr, y + 3, x + 6, "│", c_base)

        puntos = {
            "N": (0, 5, "[N]"), "NE": (1, 9, "NE"), "E": (2, 12, "[E]"),
            "SE": (3, 9, "SE"), "S": (4, 5, "[S]"), "SW": (3, 1, "SW"),
            "W": (2, -1, "[W]"), "NW": (1, 1, "NW")
        }

        mapa_8 = {
            "N": "N", "NNE": "N", "NE": "NE", "ENE": "NE", "E": "E", "ESE": "E",
            "SE": "SE", "SSE": "SE", "S": "S", "SSW": "S", "SW": "SW", "WSW": "SW",
            "W": "W", "WNW": "W", "NW": "NW", "NNW": "NW"
        }

        target = mapa_8.get(cardinal, "-")

        for k, (dy, dx, txt) in puntos.items():
            self.safe_addstr(stdscr, y + dy, x + dx, txt, c_act if k == target else c_txt)

    @staticmethod
    def obtener_color_temperatura(temp_str: str) -> int:
        try:
            val = float(temp_str)
            if val <= 10.0:
                return curses.color_pair(1) | curses.A_BOLD
            if val <= 28.0:
                return curses.color_pair(2) | curses.A_BOLD
            return curses.color_pair(3) | curses.A_BOLD
        except ValueError:
            return curses.color_pair(6)

    def ejecutar(self, stdscr) -> None:
        curses.curs_set(0)
        stdscr.nodelay(1)

        curses.start_color()
        curses.use_default_colors()

        curses.init_pair(1, curses.COLOR_CYAN, -1)
        curses.init_pair(2, curses.COLOR_GREEN, -1)
        curses.init_pair(3, curses.COLOR_RED, -1)
        curses.init_pair(4, curses.COLOR_YELLOW, -1)
        curses.init_pair(5, curses.COLOR_MAGENTA, -1)
        curses.init_pair(6, curses.COLOR_WHITE, -1)
        curses.init_pair(7, curses.COLOR_BLUE, -1)

        threading.Thread(
            target=self.core.lector_rtldavis_worker,
            daemon=True
        ).start()

        while True:
            ahora = time.time()

            (
                h,
                s,
                arrow_temp,
                arrow_viento,
                hist_temp,
                hist_viento
            ) = self.core.obtener_instantanea()

            spark_temp = self.generar_sparkline(hist_temp, 18)
            spark_viento = self.generar_sparkline(hist_viento, 18)

            if ahora - s.ultima_actividad_rf > 30.0:
                self.core.forzar_reinicio_sdr(ahora)

            if self.core.verificar_datos_completos():
                if ahora - s.ultimo_guardado_csv >= 60.0:
                    self.core.db.registrar_datos(h)
                    self.core.actualizar_estado_csv("Local Base: OK", tiempo_guardado=ahora)
            else:
                self.core.actualizar_estado_csv("Sincronizando...")

            c = stdscr.getch()
            if c in [ord('q'), ord('Q')]:
                break

            stdscr.erase()

            alto_p, ancho_p = stdscr.getmaxyx()

            if alto_p < 24 or ancho_p < 94:
                self.safe_addstr(stdscr, 1, 1, "⚠️ Pantalla pequeña. Agrande la terminal.", curses.color_pair(3))
                stdscr.refresh()
                time.sleep(0.2)
                continue

            w_panel = (ancho_p - 4) // 2
            x_right = w_panel + 3
            panel_w_bottom = (w_panel * 2) + 2

            str_tiempo = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            uptime_seg = int(ahora - self.core.hora_inicio)
            str_uptime = f"UPTIME: {uptime_seg // 3600:02d}:{(uptime_seg % 3600) // 60:02d}:{uptime_seg % 60:02d}"

            titulo = f" 📡 ESTACIÓN DAVIS VP2 │ {str_tiempo} │ {str_uptime} "

            self.safe_addstr(stdscr, 0, (ancho_p - len(titulo)) // 2, titulo, curses.color_pair(4) | curses.A_BOLD | curses.A_REVERSE)

            # PANEL VIENTO
            self.dibujar_contenedor(stdscr, 2, 1, 9, w_panel, "MONITOREO DE VIENTO")
            self.safe_addstr(stdscr, 4, 3, "Velocidad :", curses.color_pair(6))
            self.safe_addstr(stdscr, 4, 15, f"{h.viento_vel:>5} km/h {arrow_viento}", curses.color_pair(2) | curses.A_BOLD)
            self.safe_addstr(stdscr, 5, 3, "Dirección :", curses.color_pair(6))
            self.safe_addstr(stdscr, 5, 15, f"{h.viento_dir:>5} °", curses.color_pair(6) | curses.A_BOLD)
            self.safe_addstr(stdscr, 6, 3, "Ráfaga Max:", curses.color_pair(6))
            self.safe_addstr(stdscr, 6, 15, f"{h.rafaga:>5} km/h", curses.color_pair(3) | curses.A_BOLD)
            self.safe_addstr(stdscr, 7, 3, f"Tendencia   : {spark_viento}", curses.color_pair(4))
            self.dibujar_brujula(stdscr, 3, w_panel - 18, h.viento_cardinal)

            # PANEL TEMPERATURA
            self.dibujar_contenedor(stdscr, 2, x_right, 9, w_panel, "TERMODINÁMICA")
            self.safe_addstr(stdscr, 4, x_right + 3, "Temperatura :", curses.color_pair(6))
            self.safe_addstr(stdscr, 4, x_right + 17, f"{h.temp:>5} °C {arrow_temp}", self.obtener_color_temperatura(h.temp))
            self.safe_addstr(stdscr, 5, x_right + 3, "Humedad     :", curses.color_pair(6))
            self.safe_addstr(stdscr, 5, x_right + 17, f"{h.humedad:>5} %", curses.color_pair(1) | curses.A_BOLD)
            self.safe_addstr(stdscr, 6, x_right + 3, f"Tendencia   : {spark_temp}", curses.color_pair(4))

            # Alertas numéricas seguras
            f_temp = self.seguro_float(h.temp)
            f_rain = self.seguro_float(h.tasa_lluvia)
            if h.temp != "--" and f_temp <= 2.0:
                self.safe_addstr(stdscr, 7, x_right + 3, "⚠️ ADVERTENCIA: HELADA", curses.color_pair(3) | curses.A_BOLD)
            elif h.tasa_lluvia != "--" and f_rain >= 25.0:
                self.safe_addstr(stdscr, 7, x_right + 3, "⚠️ CRÍTICO: TORMENTA SEVERA", curses.color_pair(3) | curses.A_BOLD)

            # PANEL PLUVIOMETRÍA
            self.dibujar_contenedor(stdscr, 11, 1, 6, w_panel, "PLUVIOMETRÍA")
            self.safe_addstr(stdscr, 13, 3, "Tasa Lluvia :", curses.color_pair(6))
            self.safe_addstr(stdscr, 13, 17, f"{h.tasa_lluvia:>5} mm/h", curses.color_pair(1) | curses.A_BOLD)
            self.safe_addstr(stdscr, 14, 3, "Estado      :", curses.color_pair(6))
            c_ll = curses.color_pair(3) | curses.A_BOLD if "Lloviendo" in h.estado_lluvia else curses.color_pair(2) | curses.A_BOLD
            self.safe_addstr(stdscr, 14, 17, f" {h.estado_lluvia}", c_ll)
            self.safe_addstr(stdscr, 15, 3, "Humedad Hoja:", curses.color_pair(6))
            self.safe_addstr(stdscr, 15, 17, f"   {h.humedad_hoja:>2} / 15", curses.color_pair(2))

            # PANEL RADIACIÓN
            self.dibujar_contenedor(stdscr, 11, x_right, 6, w_panel, "HILOS DE RADIACIÓN")
            self.safe_addstr(stdscr, 13, x_right + 3, "Índice UV :", curses.color_pair(6))
            self.safe_addstr(stdscr, 13, x_right + 15, f"{h.uv:>6} UVI", curses.color_pair(5) | curses.A_BOLD)
            self.safe_addstr(stdscr, 14, x_right + 3, "Radiación :", curses.color_pair(6))
            self.safe_addstr(stdscr, 14, x_right + 15, f"{h.solar:>6} W/m²", curses.color_pair(4) | curses.A_BOLD)
            self.safe_addstr(stdscr, 15, x_right + 3, "Dosis UV  :", curses.color_pair(6))
            self.safe_addstr(stdscr, 15, x_right + 15, f"{h.meds:>6} MEDs", curses.color_pair(5))

            # DIAGNÓSTICOS
            self.dibujar_contenedor(stdscr, 17, 1, 8, panel_w_bottom, "DIAGNÓSTICO DE SISTEMA RF (SDR)")
            info_rf = f"📡 FREC: {s.freq} MHz │ CANAL: {s.canal}/51 │ BATERÍA TX: {h.bateria}"
            self.safe_addstr(stdscr, 19, 3, info_rf, curses.color_pair(1) | curses.A_BOLD)
            self.safe_addstr(stdscr, 19, panel_w_bottom - 26, f" {s.estado_csv} ", curses.color_pair(2) | curses.A_REVERSE)
            
            telemetria = f"Tramas Válidas: {s.paquetes} │ Fallas de CRC: {s.paquetes_descartados_crc} │ Descartes Transmisor: {s.paquetes_descartados_id}"
            self.safe_addstr(stdscr, 20, 3, telemetria, curses.color_pair(6))
            
            watchdog_txt = f"Recuperaciones de Enlace SDR: {s.reinicios_rtldavis} (Última: {s.ultimo_reinicio})"
            self.safe_addstr(stdscr, 21, 3, watchdog_txt, curses.color_pair(4))
                
            self.safe_addstr(stdscr, 22, panel_w_bottom - 20, "['Q'] Terminar", curses.color_pair(3) | curses.A_BOLD)
            self.safe_addstr(stdscr, 23, 3, f"Buffer Binario: {s.ultima_trama[:60]}...", curses.color_pair(6) | curses.A_DIM)

            stdscr.refresh()
            time.sleep(0.25)

if __name__ == "__main__":
    db_local = GestorAlmacenamiento(DIR_CAPTURAS)
    monitor = NucleoMonitoreo(db_local)
    interfaz = MotorInterfazTUI(monitor)
    
    def handler_interrupcion(_sig, _frame):
        monitor.finalizar()
        sys.exit(0)
        
    signal.signal(signal.SIGINT, handler_interrupcion)
    signal.signal(signal.SIGTERM, handler_interrupcion)

    try:
        logger.info("===== INICIO DEL SISTEMA DAVIS VP2 =====")
        curses.wrapper(interfaz.ejecutar)
    finally:
        logger.info("===== APAGADO DEL SISTEMA =====")
        monitor.finalizar()