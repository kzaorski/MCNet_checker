import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler

import config
import database
from collector import collect_sample

_scheduler: BackgroundScheduler | None = None


def _collect_all() -> None:
    hosts = [h["address"] for h in database.get_hosts()]
    if not hosts:
        return
    slot_ts = time.time()
    with ThreadPoolExecutor(max_workers=len(hosts)) as pool:
        futures = {pool.submit(collect_sample, h, slot_ts): h for h in hosts}
        for f in as_completed(futures):
            exc = f.exception()
            if exc:
                print(f"[SCHEDULER] Uncaught error for {futures[f]}: {exc}")


def start() -> None:
    global _scheduler
    _scheduler = BackgroundScheduler()
    _scheduler.add_job(
        _collect_all,
        "interval",
        seconds=config.INTERVAL_SECONDS,
        next_run_time=datetime.now(),
        misfire_grace_time=30,
        id="collect_all",
    )
    _scheduler.add_job(
        _log_hourly_status,
        "cron",
        minute=0,
        id="hourly_status",
    )
    _scheduler.start()
    hosts = [h["address"] for h in database.get_hosts()]
    print(f"[SCHEDULER] Started — collecting every {config.INTERVAL_SECONDS}s from {hosts}")


def stop() -> None:
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        print("[SCHEDULER] Stopped")


def is_running() -> bool:
    return bool(_scheduler and _scheduler.running)


def add_host_job(address: str) -> None:
    pass  # hosts are read from DB dynamically in _collect_all


def remove_host_job(address: str) -> None:
    pass  # hosts are read from DB dynamically in _collect_all


def _log_hourly_status() -> None:
    stats = database.get_stats_last_n_hours(1)
    now = datetime.now().strftime("%H:%M")
    lat = f"{stats['avg_latency_ms']}ms" if stats["avg_latency_ms"] is not None else "N/A"
    jitter = f"{stats['avg_jitter_ms']}ms" if stats["avg_jitter_ms"] is not None else "N/A"
    print(
        f"[STATUS {now}] Uptime: {stats['uptime_pct']}% | "
        f"Avg latency last 1h: {lat} | "
        f"Jitter: {jitter} | "
        f"Loss: {stats['avg_loss_pct']}% | "
        f"Samples: {stats['total']}"
    )
