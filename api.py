import time
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel

import config
import database
import scheduler

_startup_dt: datetime = datetime.now()
_session_name: str = ""


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _startup_dt, _session_name
    _startup_dt = datetime.now()
    _session_name = f"MCNet_checker_{_startup_dt.strftime('%Y-%m-%d_%H-%M-%S')}"
    database.init_db()
    scheduler.start()
    yield
    scheduler.stop()


app = FastAPI(title="MCNet_checker", lifespan=lifespan)

_HTML_PATH = Path(__file__).parent / "static" / "index.html"


@app.get("/", include_in_schema=False)
def serve_ui():
    html = _HTML_PATH.read_bytes()
    return Response(
        content=html,
        media_type="text/html",
        headers={"Content-Disposition": f'inline; filename="{_session_name}.html"'},
    )


@app.get("/api/v1/samples")
def get_samples(
    since: Optional[float] = Query(None),
    until: Optional[float] = Query(None),
    hours: Optional[float] = Query(None),
    limit: Optional[int] = Query(None),
):
    rows = database.query_samples(since=since, until=until, hours=hours, limit=limit)
    return JSONResponse(content=rows)


@app.delete("/api/v1/samples")
def delete_samples(before: float = Query(..., description="Unix timestamp; delete samples older than this")):
    deleted = database.delete_before(before)
    return {"deleted": deleted}


@app.get("/api/v1/status")
def get_status():
    stats_1h = database.get_stats_last_n_hours(1)
    uptime_s = int(time.time() - _startup_dt.timestamp())
    return {
        "session": _session_name,
        "started_at": _startup_dt.isoformat(),
        "uptime_seconds": uptime_s,
        "config": {
            "target_hosts": config.TARGET_HOSTS,
            "ping_count": config.PING_COUNT,
            "interval_seconds": config.INTERVAL_SECONDS,
        },
        "scheduler_running": scheduler.is_running(),
        "total_samples": database.count_samples(),
        "last_1h": stats_1h,
    }


# --- Hosts ---

class AddHostRequest(BaseModel):
    address: str


class PatchHostRequest(BaseModel):
    enabled: bool


@app.get("/api/v1/hosts")
def list_hosts():
    return database.get_hosts()


@app.post("/api/v1/hosts", status_code=201)
def create_host(body: AddHostRequest):
    try:
        host = database.add_host(body.address.strip())
    except ValueError:
        raise HTTPException(status_code=409, detail=f"Host '{body.address}' already exists")
    scheduler.add_host_job(host["address"])
    return host


@app.delete("/api/v1/hosts/{address:path}", status_code=204)
def delete_host(address: str):
    scheduler.remove_host_job(address)
    database.remove_host(address)
    return Response(status_code=204)


@app.patch("/api/v1/hosts/{address:path}")
def patch_host(address: str, body: PatchHostRequest):
    try:
        host = database.set_host_enabled(address, body.enabled)
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Host '{address}' not found")
    return host
