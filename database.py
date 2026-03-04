import sqlite3
import time
from typing import Optional

import config


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db() -> None:
    import os
    os.makedirs(os.path.dirname(config.DB_PATH), exist_ok=True)
    with _connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS samples (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                ts        REAL    NOT NULL,
                host      TEXT    NOT NULL,
                sent      INTEGER NOT NULL,
                received  INTEGER NOT NULL,
                loss_pct  REAL    NOT NULL,
                avg_ms    REAL,
                min_ms    REAL,
                max_ms    REAL,
                jitter_ms REAL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_samples_ts ON samples(ts)")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS hosts (
                id      INTEGER PRIMARY KEY AUTOINCREMENT,
                address TEXT    NOT NULL UNIQUE,
                enabled INTEGER NOT NULL DEFAULT 1
            )
        """)
        if conn.execute("SELECT COUNT(*) FROM hosts").fetchone()[0] == 0:
            for addr in config.TARGET_HOSTS:
                conn.execute(
                    "INSERT OR IGNORE INTO hosts (address, enabled) VALUES (?, 1)", (addr,)
                )
        conn.commit()


def get_hosts() -> list[dict]:
    with _connect() as conn:
        rows = conn.execute("SELECT id, address, enabled FROM hosts ORDER BY id").fetchall()
    return [dict(r) for r in rows]


def add_host(address: str) -> dict:
    try:
        with _connect() as conn:
            cur = conn.execute(
                "INSERT INTO hosts (address, enabled) VALUES (?, 1)", (address,)
            )
            conn.commit()
            row = conn.execute(
                "SELECT id, address, enabled FROM hosts WHERE id = ?", (cur.lastrowid,)
            ).fetchone()
        return dict(row)
    except sqlite3.IntegrityError:
        raise ValueError(f"Host '{address}' already exists")


def remove_host(address: str) -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM hosts WHERE address = ?", (address,))
        conn.commit()


def set_host_enabled(address: str, enabled: bool) -> dict:
    with _connect() as conn:
        conn.execute(
            "UPDATE hosts SET enabled = ? WHERE address = ?", (1 if enabled else 0, address)
        )
        conn.commit()
        row = conn.execute(
            "SELECT id, address, enabled FROM hosts WHERE address = ?", (address,)
        ).fetchone()
    if row is None:
        raise ValueError(f"Host '{address}' not found")
    return dict(row)


def insert_sample(
    host: str,
    sent: int,
    received: int,
    loss_pct: float,
    avg_ms: Optional[float],
    min_ms: Optional[float],
    max_ms: Optional[float],
    jitter_ms: Optional[float],
    ts: Optional[float] = None,
) -> None:
    if ts is None:
        ts = time.time()
    with _connect() as conn:
        conn.execute(
            """INSERT INTO samples
               (ts, host, sent, received, loss_pct, avg_ms, min_ms, max_ms, jitter_ms)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (ts, host, sent, received, loss_pct, avg_ms, min_ms, max_ms, jitter_ms),
        )
        conn.commit()


def query_samples(
    since: Optional[float] = None,
    until: Optional[float] = None,
    hours: Optional[float] = None,
    limit: Optional[int] = None,
) -> list[dict]:
    conditions = []
    params: list = []

    if hours is not None:
        since = time.time() - hours * 3600

    if since is not None:
        conditions.append("ts >= ?")
        params.append(since)
    if until is not None:
        conditions.append("ts <= ?")
        params.append(until)

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    limit_clause = f"LIMIT {int(limit)}" if limit else ""

    sql = f"SELECT * FROM samples {where} ORDER BY ts ASC {limit_clause}"
    with _connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


def delete_before(before_ts: float) -> int:
    with _connect() as conn:
        cur = conn.execute("DELETE FROM samples WHERE ts < ?", (before_ts,))
        conn.commit()
        return cur.rowcount


def count_samples() -> int:
    with _connect() as conn:
        row = conn.execute("SELECT COUNT(*) FROM samples").fetchone()
    return row[0]


def get_stats_last_n_hours(n: float) -> dict:
    since = time.time() - n * 3600
    with _connect() as conn:
        row = conn.execute(
            """SELECT
                COUNT(*) as total,
                SUM(CASE WHEN loss_pct < 100 THEN 1 ELSE 0 END) as ok,
                AVG(avg_ms) as avg_latency,
                AVG(jitter_ms) as avg_jitter,
                AVG(loss_pct) as avg_loss
               FROM samples WHERE ts >= ?""",
            (since,),
        ).fetchone()
    total = row["total"] or 0
    ok = row["ok"] or 0
    return {
        "total": total,
        "uptime_pct": round(ok / total * 100, 2) if total else 0.0,
        "avg_latency_ms": round(row["avg_latency"], 2) if row["avg_latency"] else None,
        "avg_jitter_ms": round(row["avg_jitter"], 2) if row["avg_jitter"] else None,
        "avg_loss_pct": round(row["avg_loss"], 2) if row["avg_loss"] is not None else 0.0,
    }
