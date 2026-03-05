import math
import re
import subprocess
import sys
from typing import Optional

import config
import database

IS_WINDOWS = sys.platform == "win32"


def collect_sample(host: str, ts: Optional[float] = None) -> None:
    count = config.PING_COUNT
    timeout = count * 3 + 5

    try:
        kwargs = {}
        if IS_WINDOWS:
            kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
        result = subprocess.run(
            _build_ping_cmd(host, count),
            capture_output=True,
            text=True,
            timeout=timeout,
            **kwargs,
        )
        output = result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        _save_failed(host, count, ts)
        print(f"[COLLECTOR] Timeout pinging {host}")
        return
    except Exception as e:
        _save_failed(host, count, ts)
        print(f"[COLLECTOR] Error: {e}")
        return

    sent, received, loss_pct = _parse_loss(output, count)
    avg_ms, min_ms, max_ms, jitter_ms = _parse_rtt(output)

    database.insert_sample(host, sent, received, loss_pct, avg_ms, min_ms, max_ms, jitter_ms, ts)
    print(
        f"[COLLECTOR] host={host} loss={loss_pct:.1f}% "
        f"avg={avg_ms:.2f}ms" if avg_ms is not None else
        f"[COLLECTOR] host={host} loss={loss_pct:.1f}% avg=N/A"
    )


def _build_ping_cmd(host: str, count: int) -> list[str]:
    if IS_WINDOWS:
        return ["ping", "-n", str(count), host]
    return ["ping", "-c", str(count), host]


def _parse_loss(output: str, count: int) -> tuple[int, int, float]:
    if IS_WINDOWS:
        m = re.search(r"Sent\s*=\s*(\d+),\s*Received\s*=\s*(\d+)", output)
    else:
        m = re.search(r"(\d+) packets transmitted,\s*(\d+) (?:packets )?received", output)
    if m:
        sent = int(m.group(1))
        received = int(m.group(2))
        loss_pct = (sent - received) / sent * 100 if sent else 100.0
        return sent, received, round(loss_pct, 1)
    return count, 0, 100.0


def _parse_rtt(output: str) -> tuple[Optional[float], Optional[float], Optional[float], Optional[float]]:
    if IS_WINDOWS:
        avg_m = re.search(r"Average\s*=\s*(\d+)ms", output)
        min_m = re.search(r"Minimum\s*=\s*(\d+)ms", output)
        max_m = re.search(r"Maximum\s*=\s*(\d+)ms", output)
        if avg_m and min_m and max_m:
            times = [float(t) for t in re.findall(r"time[=<](\d+)ms", output, re.IGNORECASE)]
            jitter = _stddev(times) if len(times) >= 2 else None
            return float(avg_m.group(1)), float(min_m.group(1)), float(max_m.group(1)), jitter
        return None, None, None, None

    # macOS: min/avg/max/stddev
    m = re.search(
        r"round-trip min/avg/max/std-?dev\s*=\s*([\d.]+)/([\d.]+)/([\d.]+)/([\d.]+)",
        output,
    )
    if not m:
        # Linux: min/avg/max/mdev
        m = re.search(
            r"rtt min/avg/max/mdev\s*=\s*([\d.]+)/([\d.]+)/([\d.]+)/([\d.]+)",
            output,
        )
    if m:
        return float(m.group(2)), float(m.group(1)), float(m.group(3)), float(m.group(4))
    return None, None, None, None


def _stddev(values: list[float]) -> float:
    n = len(values)
    mean = sum(values) / n
    variance = sum((v - mean) ** 2 for v in values) / n
    return math.sqrt(variance)


def collect_sample_data(host: str, ts: float) -> tuple:
    """Ping host and return sample tuple. Does NOT write to DB."""
    count = config.PING_COUNT
    timeout = count * 3 + 5

    try:
        kwargs = {}
        if IS_WINDOWS:
            kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
        result = subprocess.run(
            _build_ping_cmd(host, count),
            capture_output=True,
            text=True,
            timeout=timeout,
            **kwargs,
        )
        output = result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        print(f"[COLLECTOR] Timeout pinging {host}")
        return (ts, host, count, 0, 100.0, None, None, None, None)
    except Exception as e:
        print(f"[COLLECTOR] Error: {e}")
        return (ts, host, count, 0, 100.0, None, None, None, None)

    sent, received, loss_pct = _parse_loss(output, count)
    avg_ms, min_ms, max_ms, jitter_ms = _parse_rtt(output)

    print(
        f"[COLLECTOR] host={host} loss={loss_pct:.1f}% "
        f"avg={avg_ms:.2f}ms" if avg_ms is not None else
        f"[COLLECTOR] host={host} loss={loss_pct:.1f}% avg=N/A"
    )
    return (ts, host, sent, received, loss_pct, avg_ms, min_ms, max_ms, jitter_ms)


def _save_failed(host: str, count: int, ts: Optional[float] = None) -> None:
    database.insert_sample(host, count, 0, 100.0, None, None, None, None, ts)
