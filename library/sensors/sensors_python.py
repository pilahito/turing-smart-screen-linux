# SPDX-License-Identifier: GPL-3.0-or-later
#
# turing-smart-screen-python - a Python system monitor and library for USB-C displays like Turing Smart Screen or XuanFang
# https://github.com/mathoudebine/turing-smart-screen-python/
#
# Copyright (C) 2021 Matthieu Houdebine (mathoudebine)
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

# This file will use Python libraries (psutil, GPUtil, etc.) to get hardware sensors
# For all platforms (Linux, Windows, macOS) but not all HW is supported

import json
import math
import os
import platform
import re
import shutil
import subprocess
import sys
from collections import namedtuple
from enum import IntEnum, auto
from pathlib import Path
from typing import Tuple

# Nvidia GPU
import GPUtil
# CPU & disk sensors
import psutil

import library.sensors.sensors as sensors
from library.log import logger

# AMD GPU on Linux
try:
    import pyamdgpuinfo
except:
    pyamdgpuinfo = None

# AMD GPU on Windows
try:
    import pyadl
except:
    pyadl = None

PNIC_BEFORE = {}


class GpuType(IntEnum):
    UNSUPPORTED = auto()
    AMD = auto()
    NVIDIA = auto()


DETECTED_GPU = GpuType.UNSUPPORTED

MOTHERBOARD_FAN_CHIPS = ("it86", "it87", "it88", "it89", "nct6683", "nct677", "nct679")
SFAN = namedtuple('sfan', ['label', 'current', 'percent'])


def _pwm_percent(pwm_path: str) -> int:
    from psutil._common import bcat
    try:
        pwm_val = int(bcat(pwm_path))
        return min(100, max(0, int(pwm_val / 255 * 100)))
    except (IOError, OSError, ValueError):
        return 0


def _sensors_json_fans() -> dict:
    if shutil.which("sensors") is None:
        return {}
    try:
        result = subprocess.run(
            ["sensors", "-j"],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
        if result.returncode != 0 or not result.stdout.strip():
            return {}
        data = json.loads(result.stdout)
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
        return {}

    ret = {}
    fan_re = re.compile(r"^fan(\d+)$")
    pwm_re = re.compile(r"^pwm(\d+)$")
    for chip_name, chip_data in data.items():
        if not isinstance(chip_data, dict):
            continue
        entries = []
        fan_items = {}
        pwm_items = {}
        for key, value in chip_data.items():
            if not isinstance(value, dict):
                continue
            fan_match = fan_re.match(key)
            pwm_match = pwm_re.match(key)
            if fan_match:
                fan_items[int(fan_match.group(1))] = value
            elif pwm_match:
                pwm_items[int(pwm_match.group(1))] = value

        for fan_idx in sorted(fan_items):
            fan_data = fan_items[fan_idx]
            rpm = fan_data.get("fan", {}).get("input")
            if rpm is None:
                continue
            try:
                current_rpm = int(rpm)
            except (TypeError, ValueError):
                continue
            max_rpm = 2200 if current_rpm > 1500 else 1500
            percent = min(100, max(0, int(current_rpm / max_rpm * 100)))
            if fan_idx in pwm_items:
                pwm_input = pwm_items[fan_idx].get("pwm", {}).get("input")
                if pwm_input is not None:
                    try:
                        percent = min(100, max(percent, int(float(pwm_input) / 255 * 100)))
                    except (TypeError, ValueError):
                        pass
            entries.append(SFAN(f"fan{fan_idx}", current_rpm, percent))

        if not entries and pwm_items:
            for pwm_idx in sorted(pwm_items):
                pwm_input = pwm_items[pwm_idx].get("pwm", {}).get("input")
                if pwm_input is None:
                    continue
                try:
                    percent = min(100, max(0, int(float(pwm_input) / 255 * 100)))
                except (TypeError, ValueError):
                    continue
                entries.append(SFAN(f"pwm{pwm_idx}", 0, percent))

        if entries:
            ret[chip_name] = entries
    return ret


# Function inspired of psutil/psutil/_pslinux.py:sensors_fans()
# Adapted to also get fan speed percentage instead of raw value
def sensors_fans():
    """Return hardware fans info (for CPU and other peripherals) as a
    dict including hardware label and current speed.

    Implementation notes:
    - /sys/class/hwmon looks like the most recent interface to
      retrieve this info, and this implementation relies on it
      only (old distros will probably use something else)
    - lm-sensors on Ubuntu 16.04 relies on /sys/class/hwmon
    """
    from psutil._common import bcat, cat
    import collections, glob, os

    ret = collections.defaultdict(list)
    basenames = glob.glob('/sys/class/hwmon/hwmon*/fan*_*')
    if not basenames:
        # CentOS has an intermediate /device directory:
        # https://github.com/giampaolo/psutil/issues/971
        basenames = glob.glob('/sys/class/hwmon/hwmon*/device/fan*_*')

    basenames = sorted(set([x.split('_')[0] for x in basenames]))
    for base in basenames:
        try:
            current_rpm = int(bcat(base + '_input'))

            try:
                max_rpm = int(bcat(base + '_max'))
            except:
                max_rpm = False  # Real maximum speed not found
            if not max_rpm:
                if current_rpm > 2200:
                    max_rpm = 3000  # AIO Pumps are usualy 3000 RPM
                elif current_rpm > 1500:
                    max_rpm = 2200  # High speed fans are usualy 2200 RPM
                else:
                    max_rpm = 1500  # Approximated: max fan speed is 1500 RPM

            try:
                min_rpm = int(bcat(base + '_min'))
            except:
                min_rpm = 0  # Approximated: min fan speed is 0 RPM
            percent = int((current_rpm - min_rpm) / (max_rpm - min_rpm) * 100)
        except (IOError, OSError) as err:
            continue
        unit_name = cat(os.path.join(os.path.dirname(base), 'name')).strip()
        label = cat(base + '_label', fallback=os.path.basename(base)).strip()

        ret[unit_name].append(SFAN(label, current_rpm, percent))

    if not ret:
        for pwm_path in sorted(glob.glob('/sys/class/hwmon/hwmon*/pwm[0-9]')):
            try:
                unit_name = cat(os.path.join(os.path.dirname(pwm_path), 'name')).strip()
                fan_idx = os.path.basename(pwm_path).replace('pwm', '')
                percent = _pwm_percent(pwm_path)
                ret[unit_name].append(SFAN(f"pwm{fan_idx}", 0, percent))
            except (IOError, OSError):
                continue

    if not ret:
        ret = _sensors_json_fans()

    return dict(ret)


def is_cpu_fan(label: str) -> bool:
    label_lower = label.lower().replace('_', ' ')
    if any(m in label_lower for m in ('cpu', 'proc', 'processor', 'pump', 'aio', 'sys', 'chassis')):
        return True
    return label_lower in ('fan1', 'fan 1', 'pwm1', 'fan2', 'pwm2', 'fan 2')


def _read_external_fps() -> int:
    """Lee FPS real desde archivo opcional (MangoHud, script propio, etc.)."""
    candidates = []
    try:
        from library import config
        fps_file = config.CONFIG_DATA.get('config', {}).get('FPS_FILE', '')
        if fps_file:
            candidates.append(os.path.expanduser(fps_file))
    except Exception:
        pass
    candidates.extend([
        '/tmp/turing-fps',
        os.path.expanduser('~/.cache/turing-fps'),
        os.path.expanduser('~/.local/share/turing-fps'),
    ])
    for path in candidates:
        try:
            if not path or not os.path.isfile(path):
                continue
            raw = Path(path).read_text(encoding='utf-8', errors='ignore').strip().split()[0]
            fps_val = int(float(raw.replace(',', '.')))
            if 0 <= fps_val <= 9999:
                return fps_val
        except (OSError, ValueError, IndexError):
            continue
    return -1


def _motherboard_fan_percent(fans: dict) -> float:
    best = math.nan
    for chip_name, entries in fans.items():
        chip_lower = chip_name.lower()
        if not any(token in chip_lower for token in MOTHERBOARD_FAN_CHIPS):
            continue
        for entry in entries:
            pct = float(entry.percent)
            if math.isnan(pct):
                continue
            if pct > 0:
                return pct
            if math.isnan(best):
                best = pct
    return best


def _resolve_cpu_fan_entry(fan_name: str = None) -> SFAN | None:
    fans = sensors_fans()
    if not fans:
        return None
    for name, entries in fans.items():
        for entry in entries:
            if fan_name is not None and fan_name == "%s/%s" % (name, entry.label):
                return entry
            if fan_name is None and (is_cpu_fan(entry.label) or is_cpu_fan(name)):
                return entry
    for chip_name, entries in fans.items():
        chip_lower = chip_name.lower()
        if not any(token in chip_lower for token in MOTHERBOARD_FAN_CHIPS):
            continue
        for entry in entries:
            if entry.percent > 0 or entry.current > 0:
                return entry
        if entries:
            return entries[0]
    return None


class Cpu(sensors.Cpu):
    @staticmethod
    def percentage(interval: float) -> float:
        try:
            return psutil.cpu_percent(interval=interval)
        except:
            return math.nan

    @staticmethod
    def frequency() -> float:
        try:
            return psutil.cpu_freq().current
        except:
            return math.nan

    @staticmethod
    def load() -> Tuple[float, float, float]:  # 1 / 5 / 15min avg (%):
        try:
            return psutil.getloadavg()
        except:
            return math.nan, math.nan, math.nan

    @staticmethod
    def temperature() -> float:
        cpu_temp = math.nan
        try:
            sensors_temps = psutil.sensors_temperatures()
            if 'coretemp' in sensors_temps:
                # Intel CPU
                cpu_temp = sensors_temps['coretemp'][0].current
            elif 'k10temp' in sensors_temps:
                # AMD CPU
                cpu_temp = sensors_temps['k10temp'][0].current
            elif 'cpu_thermal' in sensors_temps:
                # ARM CPU
                cpu_temp = sensors_temps['cpu_thermal'][0].current
            elif 'zenpower' in sensors_temps:
                # AMD CPU with zenpower (k10temp is in blacklist)
                cpu_temp = sensors_temps['zenpower'][0].current
        except:
            # psutil.sensors_temperatures not available on Windows / MacOS
            pass
        return cpu_temp

    @staticmethod
    def fan_percent(fan_name: str = None) -> float:
        try:
            entry = _resolve_cpu_fan_entry(fan_name)
            if entry is not None:
                return float(entry.percent)
            fans = sensors_fans()
            if fans:
                return _motherboard_fan_percent(fans)
        except:
            pass

        return math.nan

    @staticmethod
    def fan_rpm(fan_name: str = None) -> float:
        try:
            entry = _resolve_cpu_fan_entry(fan_name)
            if entry is not None and entry.current > 0:
                return float(entry.current)
        except:
            pass
        return math.nan


class Gpu(sensors.Gpu):
    @staticmethod
    def stats() -> Tuple[
        float, float, float, float, float]:  # load (%) / used mem (%) / used mem (Mb) / total mem (Mb) / temp (°C)
        if DETECTED_GPU == GpuType.AMD:
            return GpuAmd.stats()
        elif DETECTED_GPU == GpuType.NVIDIA:
            return GpuNvidia.stats()
        else:
            return math.nan, math.nan, math.nan, math.nan, math.nan

    @staticmethod
    def fps() -> int:
        if DETECTED_GPU == GpuType.AMD:
            return GpuAmd.fps()
        elif DETECTED_GPU == GpuType.NVIDIA:
            return GpuNvidia.fps()
        else:
            return -1

    @staticmethod
    def fan_percent() -> float:
        if DETECTED_GPU == GpuType.AMD:
            return GpuAmd.fan_percent()
        elif DETECTED_GPU == GpuType.NVIDIA:
            return GpuNvidia.fan_percent()
        else:
            return math.nan

    @staticmethod
    def frequency() -> float:
        if DETECTED_GPU == GpuType.AMD:
            return GpuAmd.frequency()
        elif DETECTED_GPU == GpuType.NVIDIA:
            return GpuNvidia.frequency()
        else:
            return math.nan

    @staticmethod
    def is_available() -> bool:
        global DETECTED_GPU
        # Always use Nvidia GPU if available
        if GpuNvidia.is_available():
            logger.info("Detected Nvidia GPU(s)")
            DETECTED_GPU = GpuType.NVIDIA
        # Otherwise, use the AMD GPU / APU if available
        elif GpuAmd.is_available():
            logger.info("Detected AMD GPU(s)")
            DETECTED_GPU = GpuType.AMD
        else:
            logger.warning("No supported GPU found")
            DETECTED_GPU = GpuType.UNSUPPORTED
            if sys.version_info >= (3, 11) and (platform.system() == "Linux" or platform.system() == "Darwin"):
                logger.warning("If you have an AMD GPU, you may need to install some  libraries manually: see "
                               "https://github.com/mathoudebine/turing-smart-screen-python/wiki/Troubleshooting#linux--macos-no-supported-gpu-found-with-an-amd-gpu-and-python-311")

        return DETECTED_GPU != GpuType.UNSUPPORTED


_NVIDIA_CACHE: dict[str, float] = {}
_NVIDIA_CACHE_TIME = 0.0
_NVIDIA_CACHE_TTL = 3.0


def _nvidia_smi_bin() -> str | None:
    found = shutil.which("nvidia-smi")
    if found:
        return found
    for candidate in ("/usr/bin/nvidia-smi", "/usr/local/bin/nvidia-smi"):
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    return None


def _parse_nvidia_field(raw: str) -> float:
    cleaned = raw.replace("%", "").strip().strip("[]")
    if not cleaned or cleaned.upper() in ("N/A", "NA", "NONE", "NOT SUPPORTED"):
        return math.nan
    return float(cleaned)


def _refresh_nvidia_cache() -> None:
    global _NVIDIA_CACHE, _NVIDIA_CACHE_TIME
    smi = _nvidia_smi_bin()
    if smi is None:
        return
    now = __import__("time").time()
    if _NVIDIA_CACHE and now - _NVIDIA_CACHE_TIME < _NVIDIA_CACHE_TTL:
        return
    try:
        result = subprocess.run(
            [smi, "--query-gpu=fan.speed,clocks.gr", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=3,
            check=False,
        )
        if result.returncode != 0 or not result.stdout.strip():
            return
        parts = result.stdout.strip().split("\n")[0].split(",")
        if len(parts) >= 2:
            fan_val = _parse_nvidia_field(parts[0])
            clock_val = _parse_nvidia_field(parts[1])
            cache: dict[str, float] = {}
            if not math.isnan(fan_val):
                cache["fan.speed"] = fan_val
            if not math.isnan(clock_val):
                cache["clocks.gr"] = clock_val
            if cache:
                _NVIDIA_CACHE = cache
                _NVIDIA_CACHE_TIME = now
    except (OSError, subprocess.SubprocessError, ValueError):
        pass


def _nvidia_smi_float(field: str) -> float:
    _refresh_nvidia_cache()
    value = _NVIDIA_CACHE.get(field)
    return value if value is not None else math.nan


class GpuNvidia(sensors.Gpu):
    @staticmethod
    def stats() -> Tuple[
        float, float, float, float, float]:  # load (%) / used mem (%) / used mem (Mb) / total mem (Mb) / temp (°C)
        # Unlike other sensors, Nvidia GPU with GPUtil pulls in all the stats at once
        nvidia_gpus = GPUtil.getGPUs()

        try:
            memory_used_all = [item.memoryUsed for item in nvidia_gpus]
            memory_used_mb = sum(memory_used_all) / len(memory_used_all)
        except:
            memory_used_mb = math.nan

        try:
            memory_total_all = [item.memoryTotal for item in nvidia_gpus]
            memory_total_mb = sum(memory_total_all) / len(memory_total_all)
        except:
            memory_total_mb = math.nan

        try:
            memory_percentage = (memory_used_mb / memory_total_mb) * 100
        except:
            memory_percentage = math.nan

        try:
            load_all = [item.load for item in nvidia_gpus]
            load = (sum(load_all) / len(load_all)) * 100
        except:
            load = math.nan

        try:
            temperature_all = [item.temperature for item in nvidia_gpus]
            temperature = sum(temperature_all) / len(temperature_all)
        except:
            temperature = math.nan

        return load, memory_percentage, memory_used_mb, memory_total_mb, temperature

    @staticmethod
    def fps() -> int:
        # FPS real solo vía archivo externo en Linux (MangoHud/script). No confundir con MHz de GPU.
        if sys.platform == "linux":
            external = _read_external_fps()
            if external >= 0:
                return external
        return -1

    @staticmethod
    def fan_percent() -> float:
        if sys.platform == "linux":
            fan_speed = _nvidia_smi_float("fan.speed")
            if not math.isnan(fan_speed) and fan_speed >= 0:
                return fan_speed

        try:
            fans = sensors_fans()
            if fans:
                for name, entries in fans.items():
                    for entry in entries:
                        if "gpu" in (entry.label.lower() or name.lower()):
                            return entry.percent
        except:
            pass

        return math.nan

    @staticmethod
    def frequency() -> float:
        if sys.platform == "linux":
            clock_mhz = _nvidia_smi_float("clocks.gr")
            if not math.isnan(clock_mhz):
                return clock_mhz
        return math.nan

    @staticmethod
    def is_available() -> bool:
        try:
            return len(GPUtil.getGPUs()) > 0
        except:
            return False


class GpuAmd(sensors.Gpu):
    @staticmethod
    def stats() -> Tuple[
        float, float, float, float, float]:  # load (%) / used mem (%) / used mem (Mb) / total mem (Mb) / temp (°C)
        if pyamdgpuinfo:
            # Unlike other sensors, AMD GPU with pyamdgpuinfo pulls in all the stats at once
            pyamdgpuinfo.detect_gpus()
            amd_gpu = pyamdgpuinfo.get_gpu(0)

            try:
                memory_used_bytes = amd_gpu.query_vram_usage()
                memory_used = memory_used_bytes / 1024 / 1024
            except:
                memory_used_bytes = math.nan
                memory_used = math.nan

            try:
                memory_total_bytes = amd_gpu.memory_info["vram_size"]
                memory_total = memory_total_bytes / 1024 / 1024
            except:
                memory_total_bytes = math.nan
                memory_total = math.nan

            try:
                memory_percentage = (memory_used_bytes / memory_total_bytes) * 100
            except:
                memory_percentage = math.nan

            try:
                load = amd_gpu.query_load() * 100
            except:
                load = math.nan

            try:
                temperature = amd_gpu.query_temperature()
            except:
                temperature = math.nan

            return load, memory_percentage, memory_used, memory_total, temperature
        elif pyadl:
            amd_gpu = pyadl.ADLManager.getInstance().getDevices()[0]

            try:
                load = amd_gpu.getCurrentUsage()
            except:
                load = math.nan

            try:
                temperature = amd_gpu.getCurrentTemperature()
            except:
                temperature = math.nan

            # GPU memory data not supported by pyadl
            return load, math.nan, math.nan, math.nan, temperature

    @staticmethod
    def fps() -> int:
        # Not supported by Python libraries
        return -1

    @staticmethod
    def fan_percent() -> float:
        try:
            # Try with psutil fans
            fans = sensors_fans()
            if fans:
                for name, entries in fans.items():
                    for entry in entries:
                        if "gpu" in (entry.label.lower() or name.lower()):
                            return entry.percent

            # Try with pyadl if psutil did not find GPU fan
            if pyadl:
                return pyadl.ADLManager.getInstance().getDevices()[0].getCurrentFanSpeed(
                    pyadl.ADL_DEVICE_FAN_SPEED_TYPE_PERCENTAGE)
        except:
            pass

        return math.nan

    @staticmethod
    def frequency() -> float:
        try:
            if pyamdgpuinfo:
                pyamdgpuinfo.detect_gpus()
                return pyamdgpuinfo.get_gpu(0).query_sclk() / 1000000
            elif pyadl:
                return pyadl.ADLManager.getInstance().getDevices()[0].getCurrentEngineClock()
            else:
                return math.nan
        except:
            return math.nan

    @staticmethod
    def is_available() -> bool:
        try:
            if pyamdgpuinfo and pyamdgpuinfo.detect_gpus() > 0:
                return True
            elif pyadl and len(pyadl.ADLManager.getInstance().getDevices()) > 0:
                return True
            else:
                return False
        except:
            return False


class Memory(sensors.Memory):
    @staticmethod
    def swap_percent() -> float:
        try:
            return psutil.swap_memory().percent
        except:
            return math.nan

    @staticmethod
    def virtual_percent() -> float:
        try:
            return psutil.virtual_memory().percent
        except:
            return math.nan

    @staticmethod
    def virtual_used() -> int:  # In bytes
        try:
            # Do not use psutil.virtual_memory().used: from https://psutil.readthedocs.io/en/latest/#memory
            # "It is calculated differently depending on the platform and designed for informational purposes only"
            return psutil.virtual_memory().total - psutil.virtual_memory().available
        except:
            return -1

    @staticmethod
    def virtual_free() -> int:  # In bytes
        try:
            # Do not use psutil.virtual_memory().free: from https://psutil.readthedocs.io/en/latest/#memory
            # "note that this doesn’t reflect the actual memory available (use available instead)."
            return psutil.virtual_memory().available
        except:
            return -1


class Disk(sensors.Disk):
    @staticmethod
    def disk_usage_percent() -> float:
        try:
            return psutil.disk_usage("/").percent
        except:
            return math.nan

    @staticmethod
    def disk_used() -> int:  # In bytes
        try:
            return psutil.disk_usage("/").used
        except:
            return -1

    @staticmethod
    def disk_free() -> int:  # In bytes
        try:
            return psutil.disk_usage("/").free
        except:
            return -1


class Net(sensors.Net):
    @staticmethod
    def stats(if_name, interval) -> Tuple[
        int, int, int, int]:  # up rate (B/s), uploaded (B), dl rate (B/s), downloaded (B)
        try:
            # Get current counters
            pnic_after = psutil.net_io_counters(pernic=True)

            upload_rate = 0
            uploaded = 0
            download_rate = 0
            downloaded = 0

            if if_name != "":
                if if_name in pnic_after:
                    try:
                        upload_rate = (pnic_after[if_name].bytes_sent - PNIC_BEFORE[if_name].bytes_sent) / interval
                        uploaded = pnic_after[if_name].bytes_sent
                        download_rate = (pnic_after[if_name].bytes_recv - PNIC_BEFORE[if_name].bytes_recv) / interval
                        downloaded = pnic_after[if_name].bytes_recv
                    except:
                        # Interface might not be in PNIC_BEFORE for now
                        pass

                    PNIC_BEFORE.update({if_name: pnic_after[if_name]})
                else:
                    logger.warning("Network interface '%s' not found. Check names in config.yaml." % if_name)

            return upload_rate, uploaded, download_rate, downloaded
        except:
            return -1, -1, -1, -1
