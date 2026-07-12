"""
davis_monitor.py
=================

SDR acquisition daemon for weather telemetry from a Davis Vantage Pro 2
station (902-928 MHz ISM band, FHSS), used as the edge layer of a
cyber-physical greenhouse drying system.

General flow (see docs/architecture.md for the full diagram):

    1. SDR thread (rtldavis_reader_worker): launches the external binary
       `rtldavis -tf US` via subprocess and reads hexadecimal payloads from
       its stdout. A watchdog restarts the subprocess if there is no RF
       activity within MAX_SENSOR_WAIT_TIME seconds.
    2. CRC-16 validation (DavisDecoder.validate_crc): every 8-byte frame is
       validated against its last 2 bytes (received CRC); corrupted frames
       are discarded before decoding.
    3. Decoding (MonitoringCore.process_frame): extracts wind, temperature,
       humidity, solar radiation, UV index and rain according to the packet
       type (PacketType), using bit shifts over the payload.
    4. Persistence (StorageManager): local CSV backup and rotating logging;
       ingestion into a time-series database (e.g. InfluxDB) happens
       downstream every ~60 s.
    5. Interface (TUIInterfaceEngine): real-time console panel based on
       curses, with a wind compass, trend sparklines and watchdog status.

Requires Python 3.9+ (standard library only) and the external binary
`rtldavis` available on the system PATH. See requirements.txt.
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

# === GLOBAL CONFIGURATION ===
CAPTURES_DIR: str = os.path.expanduser("~/davis_captures")
os.makedirs(CAPTURES_DIR, exist_ok=True)

# === LOGGING ===
LOG_FILE = os.path.join(CAPTURES_DIR, "davis_monitor.log")

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
        # DELETE THE LINE THAT SAID: logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger("DavisMonitor")

# FIX APPLIED HERE! (your station uses ID 0)
TARGET_TX_ID: str = "0"
MAX_SENSOR_WAIT_TIME: int = 300

class PacketType(Enum):
    WIND_GUST      = 0x9
    TEMPERATURE    = 0x8
    HUMIDITY       = 0xA
    RAIN_RATE      = 0x5
    LEAF_MOISTURE  = 0xE
    SOLAR_RAD      = 0x6
    UV_INDEX       = 0x4

@dataclass
class StationTelemetry:
    __slots__ = (
        'wind_speed', 'wind_dir', 'wind_cardinal', 'gust',
        'temp', 'humidity', 'rain_rate', 'rain_state',
        'leaf_moisture', 'uv', 'meds', 'solar', 'tx_id', 'battery'
    )
    wind_speed: str; wind_dir: str; wind_cardinal: str; gust: str
    temp: str; humidity: str; rain_rate: str; rain_state: str
    leaf_moisture: str; uv: str; meds: str; solar: str; tx_id: str; battery: str

    @classmethod
    def init_empty(cls) -> 'StationTelemetry':
        return cls(
            wind_speed="--", wind_dir="--", wind_cardinal="--", gust="--",
            temp="--", humidity="--", rain_rate="--", rain_state="--",
            leaf_moisture="--", uv="--", meds="--", solar="--", tx_id="-", battery="-"
        )

    def clone(self) -> 'StationTelemetry':
        """Creates a physical copy of the data to release the Lock quickly."""
        return StationTelemetry(
            wind_speed=self.wind_speed, wind_dir=self.wind_dir, wind_cardinal=self.wind_cardinal,
            gust=self.gust, temp=self.temp, humidity=self.humidity, rain_rate=self.rain_rate,
            rain_state=self.rain_state, leaf_moisture=self.leaf_moisture, uv=self.uv,
            meds=self.meds, solar=self.solar, tx_id=self.tx_id, battery=self.battery
        )

@dataclass
class SDRState:
    freq: str = "Searching..."
    channel: str = "-"
    packets: int = 0
    crc_rejected_packets: int = 0
    id_rejected_packets: int = 0
    rtldavis_restarts: int = 0
    last_restart: str = "Never"
    last_csv_write: float = 0.0
    csv_status: str = "Waiting..."
    last_rf_activity: float = field(default_factory=time.time)
    last_frame: str = ""

    def clone(self) -> 'SDRState':
        return SDRState(
            freq=self.freq, channel=self.channel, packets=self.packets,
            crc_rejected_packets=self.crc_rejected_packets,
            id_rejected_packets=self.id_rejected_packets,
            rtldavis_restarts=self.rtldavis_restarts, last_restart=self.last_restart,
            last_csv_write=self.last_csv_write, csv_status=self.csv_status,
            last_rf_activity=self.last_rf_activity, last_frame=self.last_frame
        )

class TrendAnalyzer:
    def __init__(self, maxlen: int = 10):
        self._history = deque(maxlen=maxlen)

    def record_and_get_arrow(self, value_str: str) -> str:
        try:
            value = float(value_str)
            if not self._history:
                self._history.append(value)
                return "─"
            average = sum(self._history) / len(self._history)
            self._history.append(value)
            if value > average + 0.1: return "▲"
            elif value < average - 0.1: return "▼"
            return "─"
        except ValueError:
            return "─"

class StorageManager:
    def __init__(self, directory: str):
        self.directory = directory

    def log_data(self, hub: StationTelemetry) -> None:
        today_date = datetime.now().strftime('%Y-%m-%d')

        csv_file = os.path.join(
            self.directory,
            f"davis_history_{today_date}.csv"
        )

        exists = os.path.isfile(csv_file)

        row = [
            datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            hub.temp,
            hub.humidity,
            hub.wind_speed,
            hub.wind_dir,
            hub.wind_cardinal,
            hub.gust,
            hub.rain_rate,
            hub.leaf_moisture,
            hub.uv,
            hub.solar,
            hub.battery
        ]

        try:
            with open(
                csv_file,
                mode='a',
                newline='',
                encoding='utf-8'
            ) as f:

                writer = csv.writer(f)

                if not exists:
                    writer.writerow([
                        "Date_Time",
                        "Temp_C",
                        "Humidity_%",
                        "Wind_kmh",
                        "Direction_Degrees",
                        "Cardinal",
                        "Gust_kmh",
                        "Rain_mm_h",
                        "Leaf_0_15",
                        "UV_Index",
                        "Radiation_W_m2",
                        "TX_Battery"
                    ])

                writer.writerow(row)

        except IOError as e:
            logger.exception(f"Error writing CSV: {e}")

class DavisDecoder:
    @staticmethod
    def validate_crc(hex_str: str) -> bool:
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
            logger.exception(f"Error validating CRC: {e}")
            return False

    @staticmethod
    def degrees_to_cardinal(degrees: float) -> str:
        directions = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
                      "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
        return directions[round(degrees / 22.5) % 16]

class MonitoringCore:
    def __init__(self, db_manager: StorageManager):
        self.hub = StationTelemetry.init_empty()
        self.sdr = SDRState()
        self.db = db_manager
        self.lock = threading.Lock()  # Protects ALL mutation between threads
        self.shutdown_event = threading.Event()
        self.rtldavis_proc: Optional[subprocess.Popen] = None
        self.start_time = time.time()

        self.temp_trend = TrendAnalyzer()
        self.wind_trend = TrendAnalyzer()
        self.arrow_temp = "─"
        self.wind_arrow = "─"

        # === IN-RAM HISTORY BUFFERS ===
        self.temp_history = deque(maxlen=120)
        self.humidity_history = deque(maxlen=120)
        self.wind_history = deque(maxlen=120)
        self.uv_history = deque(maxlen=120)

    def process_frame(self, hex_str: str) -> bool:

        with self.lock:

            # Basic validation and CRC
            if len(hex_str) < 16 or not DavisDecoder.validate_crc(hex_str):

                self.sdr.crc_rejected_packets += 1

                if self.sdr.crc_rejected_packets % 100 == 0:
                    logger.warning(
                        f"Accumulated invalid CRCs: "
                        f"{self.sdr.crc_rejected_packets}"
                    )

                return False

            try:

                data = bytes.fromhex(hex_str[:10])

                if len(data) != 5:
                    return False

                b0, b1, b2, b3, b4 = struct.unpack(">BBBBB", data)

                detected_tx_id = str((b0 >> 1) & 0x07)

                if detected_tx_id != TARGET_TX_ID:
                    self.sdr.id_rejected_packets += 1
                    return False

                updates: Dict[str, str] = {
                    "tx_id": detected_tx_id,
                    "battery": "Low" if (b0 & 0x01) else "OK",
                    "wind_speed": f"{(b1 * 1.60934):.1f}"
                }

                # Wind history
                if updates["wind_speed"] != "--":
                    self.wind_history.append(
                        float(updates["wind_speed"])
                    )

                self.wind_arrow = (
                    self.wind_trend
                    .record_and_get_arrow(
                        updates["wind_speed"]
                    )
                )

                # Wind direction
                direction_degrees = (b2 * 360) / 255.0

                updates["wind_dir"] = f"{direction_degrees:.0f}"

                updates["wind_cardinal"] = (
                    DavisDecoder.degrees_to_cardinal(
                        direction_degrees
                    )
                )

                # Packet type
                try:

                    packet_type = PacketType(b0 >> 4)

                    # TEMPERATURE
                    if packet_type == PacketType.TEMPERATURE:
                        raw_temp = (b3 << 8) | b4
                        if raw_temp >= 32768:
                            raw_temp -= 65536

                        celsius = (((raw_temp / 160.0) - 32) * 5.0 / 9.0)
                        celsius_str = f"{celsius:.1f}"

                        updates["temp"] = celsius_str
                        self.temp_history.append(celsius)

                        self.arrow_temp = (
                            self.temp_trend
                            .record_and_get_arrow(celsius_str)
                        )

                    # HUMIDITY
                    elif packet_type == PacketType.HUMIDITY:
                        concatenated_text = hex_str[8] + hex_str[6:8]
                        hum = int(concatenated_text, 16) / 10.0
                        hum = min(hum, 100.0)
                        updates["humidity"] = f"{hum:.1f}"
                        self.humidity_history.append(hum)

                    # RAIN
                    elif packet_type == PacketType.RAIN_RATE:
                        if hex_str[6:8].upper() == "FF":
                            updates["rain_state"] = "⚪ Dry"
                            updates["rain_rate"] = "0.0"
                        else:
                            rain = (int(hex_str[8] + hex_str[6:8], 16) * 0.2)
                            updates["rain_state"] = "🔴 Raining"
                            updates["rain_rate"] = f"{rain:.1f}"

                    # LEAF MOISTURE
                    elif packet_type == PacketType.LEAF_MOISTURE:
                        leaf_raw = int(hex_str[8] + hex_str[6:8], 16)
                        if leaf_raw > 15:
                            value = min(round(leaf_raw / 10.0), 15)
                        else:
                            value = leaf_raw
                        updates["leaf_moisture"] = str(value)

                    # GUST
                    elif packet_type == PacketType.WIND_GUST:
                        updates["gust"] = f"{(b3 * 1.60934):.1f}"

                    # SOLAR
                    elif packet_type == PacketType.SOLAR_RAD:
                        sr_raw = (((b3 << 2) | (b4 >> 6)) & 0x3FF)
                        if sr_raw < 0x3FF:
                            updates["solar"] = f"{(sr_raw * 1.757936):.1f}"
                        else:
                            updates["solar"] = "N/A"

                    # UV
                    elif packet_type == PacketType.UV_INDEX:
                        uv_raw = (((b3 << 2) | (b4 >> 6)) & 0x3FF)
                        if uv_raw < 0x3FF:
                            uv = uv_raw / 50.0
                            updates["uv"] = f"{uv:.1f}"
                            self.uv_history.append(uv)

                            meds = uv * (3.0 / 7.0)
                            updates["meds"] = f"{meds:.2f}"
                        else:
                            updates["uv"] = "N/A"
                            updates["meds"] = "N/A"

                except ValueError:
                    pass

                # Apply updates atomically
                for k, v in updates.items():
                    setattr(self.hub, k, v)

                return True

            except Exception as e:
                logger.exception(f"Error processing frame [{hex_str}]: {e}")
                return False

    def rtldavis_reader_worker(self) -> None:
        # DELETE the '-g', '40' so it reads exactly like this:
        cmd = ['rtldavis', '-tf', 'US']

        hop_regex = re.compile(r'ChannelIdx:(\d+) ChannelFreq:(\d+)')
        time_regex = re.compile(r'^\d{2}:\d{2}:\d{2}\.\d+')

        logger.info("Starting rtldavis SDR thread")
        timeout_counter = 0

        while not self.shutdown_event.is_set():
            try:
                with self.lock:
                    self.sdr.last_rf_activity = time.time()

                self.rtldavis_proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1
                )

                logger.info("rtldavis process started")

                while not self.shutdown_event.is_set():

                    if self.rtldavis_proc is None or self.rtldavis_proc.stdout is None:
                        logger.warning("rtldavis has no stdout available")
                        break

                    # Wait a maximum of 1 second
                    ready, _, _ = select.select([self.rtldavis_proc.stdout], [], [], 1.0)

                    if not ready:
                        timeout_counter += 1
                        if timeout_counter >= 30:
                            logger.warning(f"No RF activity for {timeout_counter} seconds")
                        continue

                    stdout = self.rtldavis_proc.stdout
                    line = stdout.readline()

                    if not line:
                        logger.warning("rtldavis exited or closed stdout")
                        break

                    line = line.strip()
                    if not line:
                        continue

                    timeout_counter = 0

                    with self.lock:
                        self.sdr.last_rf_activity = time.time()

                    if "Hop:" in line:
                        match = hop_regex.search(line)
                        if match:
                            with self.lock:
                                self.sdr.channel = match.group(1)
                                self.sdr.freq = f"{int(match.group(2)) / 1000000.0:.3f}"

                    elif (time_regex.match(line) and "Hop:" not in line and "ppm" not in line):
                        parts = line.split(maxsplit=1)
                        if len(parts) > 1:
                            clean_frame = parts[1].split()[0]

                            with self.lock:
                                self.sdr.last_frame = parts[1]

                            if self.process_frame(clean_frame):
                                with self.lock:
                                    self.sdr.packets += 1

            except Exception as e:
                logger.exception(f"Error in rtldavis_reader_worker: {e}")

            finally:
                if self.rtldavis_proc is not None:
                    try:
                        self.rtldavis_proc.terminate()
                    except (OSError, subprocess.SubprocessError):
                        pass
                    self.rtldavis_proc = None

            time.sleep(1)

    def get_snapshot(self) -> tuple:
        """Returns thread-disconnected safe copies to avoid Race Conditions."""
        with self.lock:
            return (
                self.hub.clone(),
                self.sdr.clone(),
                self.arrow_temp,
                self.wind_arrow,
                list(self.temp_history),
                list(self.wind_history)
            )

    def force_sdr_restart(self, now: float) -> None:
        with self.lock:
            self.sdr.rtldavis_restarts += 1
            logger.warning("SDR watchdog triggered: restarting rtldavis")
            self.sdr.last_restart = datetime.now().strftime('%H:%M:%S')
            self.sdr.freq = "Restarting..."
            self.sdr.channel = "-"

        if self.rtldavis_proc:
            try:
                self.rtldavis_proc.terminate()
            except Exception as e:
                logger.exception(f"Error terminating rtldavis process: {e}")

        with self.lock:
            self.sdr.last_rf_activity = now

    def update_csv_status(self, text: str, saved_time: Optional[float] = None) -> None:
        with self.lock:
            self.sdr.csv_status = text
            if saved_time is not None:
                self.sdr.last_csv_write = saved_time

    def check_data_complete(self) -> bool:
        if time.time() - self.start_time > MAX_SENSOR_WAIT_TIME: return True
        with self.lock:
            return all(getattr(self.hub, attr) != "--" for attr in self.hub.__slots__)

    def shutdown(self) -> None:
        self.shutdown_event.set()
        if self.rtldavis_proc:
            try:
                self.rtldavis_proc.terminate()
                self.rtldavis_proc.wait(timeout=1)
            except Exception as e:
                logger.exception(f"Error closing rtldavis cleanly: {e}")
                try:
                    self.rtldavis_proc.kill()
                except Exception as kill_error:
                    logger.exception(f"Error forcing rtldavis kill: {kill_error}")


class TUIInterfaceEngine:
    def __init__(self, core: MonitoringCore):
        self.core = core

    @staticmethod
    def safe_addstr(stdscr, y: int, x: int, text: str, attr: int = 0) -> None:
        try:
            stdscr.addstr(y, x, text, attr)
        except curses.error:
            pass

    @staticmethod
    def safe_float(val_str: str) -> float:
        try:
            return float(val_str)
        except ValueError:
            return 0.0

    @staticmethod
    def generate_sparkline(data, width=20):
        if not data:
            return "─" * width

        blocks = "▁▂▃▄▅▆▇█"
        data = list(data)[-width:]
        minimum = min(data)
        maximum = max(data)

        if maximum == minimum:
            return blocks[0] * len(data)

        result = ""
        for value in data:
            index = int((value - minimum) / (maximum - minimum) * (len(blocks) - 1))
            result += blocks[index]

        return result

    def draw_container(self, stdscr, y: int, x: int, height: int, width: int, title: str) -> None:
        c_border = curses.color_pair(1)
        c_title = curses.color_pair(5) | curses.A_BOLD

        self.safe_addstr(stdscr, y, x, "╭" + "─" * (width - 2) + "╮", c_border)
        for i in range(1, height - 1):
            self.safe_addstr(stdscr, y + i, x, "│", c_border)
            self.safe_addstr(stdscr, y + i, x + width - 1, "│", c_border)

        self.safe_addstr(stdscr, y + height - 1, x, "╰" + "─" * (width - 2) + "╯", c_border)
        self.safe_addstr(stdscr, y, x + 3, f" {title} ", c_title)

    def draw_compass(self, stdscr, y: int, x: int, cardinal: str) -> None:
        c_base = curses.color_pair(7) | curses.A_BOLD
        c_active = curses.color_pair(4) | curses.A_BOLD
        c_text = curses.color_pair(6)

        self.safe_addstr(stdscr, y + 1, x + 6, "│", c_base)
        self.safe_addstr(stdscr, y + 2, x + 2, "────┼────", c_base)
        self.safe_addstr(stdscr, y + 3, x + 6, "│", c_base)

        points = {
            "N": (0, 5, "[N]"), "NE": (1, 9, "NE"), "E": (2, 12, "[E]"),
            "SE": (3, 9, "SE"), "S": (4, 5, "[S]"), "SW": (3, 1, "SW"),
            "W": (2, -1, "[W]"), "NW": (1, 1, "NW")
        }

        map_8 = {
            "N": "N", "NNE": "N", "NE": "NE", "ENE": "NE", "E": "E", "ESE": "E",
            "SE": "SE", "SSE": "SE", "S": "S", "SSW": "S", "SW": "SW", "WSW": "SW",
            "W": "W", "WNW": "W", "NW": "NW", "NNW": "NW"
        }

        target = map_8.get(cardinal, "-")

        for k, (dy, dx, txt) in points.items():
            self.safe_addstr(stdscr, y + dy, x + dx, txt, c_active if k == target else c_text)

    @staticmethod
    def get_temperature_color(temp_str: str) -> int:
        try:
            val = float(temp_str)
            if val <= 10.0:
                return curses.color_pair(1) | curses.A_BOLD
            if val <= 28.0:
                return curses.color_pair(2) | curses.A_BOLD
            return curses.color_pair(3) | curses.A_BOLD
        except ValueError:
            return curses.color_pair(6)

    def run(self, stdscr) -> None:
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
            target=self.core.rtldavis_reader_worker,
            daemon=True
        ).start()

        while True:
            now = time.time()

            (
                h,
                s,
                arrow_temp,
                wind_arrow,
                hist_temp,
                hist_wind
            ) = self.core.get_snapshot()

            spark_temp = self.generate_sparkline(hist_temp, 18)
            spark_wind = self.generate_sparkline(hist_wind, 18)

            if now - s.last_rf_activity > 30.0:
                self.core.force_sdr_restart(now)

            if self.core.check_data_complete():
                if now - s.last_csv_write >= 60.0:
                    self.core.db.log_data(h)
                    self.core.update_csv_status("Local DB: OK", saved_time=now)
            else:
                self.core.update_csv_status("Syncing...")

            c = stdscr.getch()
            if c in [ord('q'), ord('Q')]:
                break

            stdscr.erase()

            screen_h, screen_w = stdscr.getmaxyx()

            if screen_h < 24 or screen_w < 94:
                self.safe_addstr(stdscr, 1, 1, "⚠️ Screen too small. Enlarge the terminal.", curses.color_pair(3))
                stdscr.refresh()
                time.sleep(0.2)
                continue

            panel_w = (screen_w - 4) // 2
            x_right = panel_w + 3
            panel_w_bottom = (panel_w * 2) + 2

            time_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            uptime_sec = int(now - self.core.start_time)
            uptime_str = f"UPTIME: {uptime_sec // 3600:02d}:{(uptime_sec % 3600) // 60:02d}:{uptime_sec % 60:02d}"

            title = f" 📡 DAVIS VP2 STATION │ {time_str} │ {uptime_str} "

            self.safe_addstr(stdscr, 0, (screen_w - len(title)) // 2, title, curses.color_pair(4) | curses.A_BOLD | curses.A_REVERSE)

            # WIND PANEL
            self.draw_container(stdscr, 2, 1, 9, panel_w, "WIND MONITORING")
            self.safe_addstr(stdscr, 4, 3, "Speed     :", curses.color_pair(6))
            self.safe_addstr(stdscr, 4, 15, f"{h.wind_speed:>5} km/h {wind_arrow}", curses.color_pair(2) | curses.A_BOLD)
            self.safe_addstr(stdscr, 5, 3, "Direction :", curses.color_pair(6))
            self.safe_addstr(stdscr, 5, 15, f"{h.wind_dir:>5} °", curses.color_pair(6) | curses.A_BOLD)
            self.safe_addstr(stdscr, 6, 3, "Max Gust  :", curses.color_pair(6))
            self.safe_addstr(stdscr, 6, 15, f"{h.gust:>5} km/h", curses.color_pair(3) | curses.A_BOLD)
            self.safe_addstr(stdscr, 7, 3, f"Trend     : {spark_wind}", curses.color_pair(4))
            self.draw_compass(stdscr, 3, panel_w - 18, h.wind_cardinal)

            # TEMPERATURE PANEL
            self.draw_container(stdscr, 2, x_right, 9, panel_w, "THERMODYNAMICS")
            self.safe_addstr(stdscr, 4, x_right + 3, "Temperature :", curses.color_pair(6))
            self.safe_addstr(stdscr, 4, x_right + 17, f"{h.temp:>5} °C {arrow_temp}", self.get_temperature_color(h.temp))
            self.safe_addstr(stdscr, 5, x_right + 3, "Humidity    :", curses.color_pair(6))
            self.safe_addstr(stdscr, 5, x_right + 17, f"{h.humidity:>5} %", curses.color_pair(1) | curses.A_BOLD)
            self.safe_addstr(stdscr, 6, x_right + 3, f"Trend       : {spark_temp}", curses.color_pair(4))

            # Safe numeric alerts
            f_temp = self.safe_float(h.temp)
            f_rain = self.safe_float(h.rain_rate)
            if h.temp != "--" and f_temp <= 2.0:
                self.safe_addstr(stdscr, 7, x_right + 3, "⚠️ WARNING: FROST", curses.color_pair(3) | curses.A_BOLD)
            elif h.rain_rate != "--" and f_rain >= 25.0:
                self.safe_addstr(stdscr, 7, x_right + 3, "⚠️ CRITICAL: SEVERE STORM", curses.color_pair(3) | curses.A_BOLD)

            # RAIN GAUGE PANEL
            self.draw_container(stdscr, 11, 1, 6, panel_w, "RAIN GAUGE")
            self.safe_addstr(stdscr, 13, 3, "Rain Rate   :", curses.color_pair(6))
            self.safe_addstr(stdscr, 13, 17, f"{h.rain_rate:>5} mm/h", curses.color_pair(1) | curses.A_BOLD)
            self.safe_addstr(stdscr, 14, 3, "State       :", curses.color_pair(6))
            c_rain = curses.color_pair(3) | curses.A_BOLD if "Raining" in h.rain_state else curses.color_pair(2) | curses.A_BOLD
            self.safe_addstr(stdscr, 14, 17, f" {h.rain_state}", c_rain)
            self.safe_addstr(stdscr, 15, 3, "Leaf Wetness:", curses.color_pair(6))
            self.safe_addstr(stdscr, 15, 17, f"   {h.leaf_moisture:>2} / 15", curses.color_pair(2))

            # RADIATION PANEL
            self.draw_container(stdscr, 11, x_right, 6, panel_w, "RADIATION THREADS")
            self.safe_addstr(stdscr, 13, x_right + 3, "UV Index  :", curses.color_pair(6))
            self.safe_addstr(stdscr, 13, x_right + 15, f"{h.uv:>6} UVI", curses.color_pair(5) | curses.A_BOLD)
            self.safe_addstr(stdscr, 14, x_right + 3, "Radiation :", curses.color_pair(6))
            self.safe_addstr(stdscr, 14, x_right + 15, f"{h.solar:>6} W/m²", curses.color_pair(4) | curses.A_BOLD)
            self.safe_addstr(stdscr, 15, x_right + 3, "UV Dose   :", curses.color_pair(6))
            self.safe_addstr(stdscr, 15, x_right + 15, f"{h.meds:>6} MEDs", curses.color_pair(5))

            # DIAGNOSTICS
            self.draw_container(stdscr, 17, 1, 8, panel_w_bottom, "RF SYSTEM DIAGNOSTICS (SDR)")
            rf_info = f"📡 FREQ: {s.freq} MHz │ CHANNEL: {s.channel}/51 │ TX BATTERY: {h.battery}"
            self.safe_addstr(stdscr, 19, 3, rf_info, curses.color_pair(1) | curses.A_BOLD)
            self.safe_addstr(stdscr, 19, panel_w_bottom - 26, f" {s.csv_status} ", curses.color_pair(2) | curses.A_REVERSE)

            telemetry = f"Valid Frames: {s.packets} │ CRC Failures: {s.crc_rejected_packets} │ TX Discards: {s.id_rejected_packets}"
            self.safe_addstr(stdscr, 20, 3, telemetry, curses.color_pair(6))

            watchdog_txt = f"SDR Link Recoveries: {s.rtldavis_restarts} (Last: {s.last_restart})"
            self.safe_addstr(stdscr, 21, 3, watchdog_txt, curses.color_pair(4))

            self.safe_addstr(stdscr, 22, panel_w_bottom - 20, "['Q'] Quit", curses.color_pair(3) | curses.A_BOLD)
            self.safe_addstr(stdscr, 23, 3, f"Binary Buffer: {s.last_frame[:60]}...", curses.color_pair(6) | curses.A_DIM)

            stdscr.refresh()
            time.sleep(0.25)

if __name__ == "__main__":
    local_db = StorageManager(CAPTURES_DIR)
    monitor = MonitoringCore(local_db)
    interface = TUIInterfaceEngine(monitor)

    def interrupt_handler(_sig, _frame):
        monitor.shutdown()
        sys.exit(0)

    signal.signal(signal.SIGINT, interrupt_handler)
    signal.signal(signal.SIGTERM, interrupt_handler)

    try:
        logger.info("===== DAVIS VP2 SYSTEM STARTUP =====")
        curses.wrapper(interface.run)
    finally:
        logger.info("===== SYSTEM SHUTDOWN =====")
        monitor.shutdown()
