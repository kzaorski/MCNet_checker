# MCNet_checker

*Named after MCNet — my home WiFi network.*

A lightweight internet connection stability monitor. Runs 24h+, collects latency/packet-loss/jitter samples via `ping`, stores them in SQLite, and serves a live chart in your browser.

## Requirements

- Python 3.9+
- macOS, Linux, or Windows 10/11
- `ping` available in `$PATH`

## Installation

```bash
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Configuration

Copy `.env.example` to `.env` (optional) or set environment variables directly.

| Variable           | Default                 | Description                                            |
|--------------------|-------------------------|--------------------------------------------------------|
| `TARGET_HOSTS`     | `8.8.8.8`               | Comma-separated list of hosts to ping                  |
| `TARGET_HOST`      | `8.8.8.8`               | Single host fallback (used when `TARGET_HOSTS` is unset) |
| `PING_COUNT`       | `10`                    | Packets per sample                                     |
| `INTERVAL_SECONDS` | `60`                    | Seconds between samples                                |
| `DB_PATH`          | `data/MCNet_checker.db` | SQLite database path                                   |
| `HOST`             | `127.0.0.1`             | Bind address for the web server                        |
| `PORT`             | `8000`                  | Port for the web server                                |

Example `.env`:

```dotenv
TARGET_HOSTS=1.1.1.1,8.8.8.8,9.9.9.9
INTERVAL_SECONDS=30
PORT=8080
```

## Usage

```bash
python main.py
```

Open **http://127.0.0.1:8000** in your browser. The first sample is collected immediately on startup; subsequent samples follow the configured interval.

The UI supports **light, dark, and system** themes — toggle via the button in the top-right corner. All configured hosts are pinged simultaneously on every interval tick, and each host can be shown or hidden using the checkboxes in the UI.

## API Reference

### `GET /api/v1/samples`

Returns an array of sample objects.

Query parameters:

| Param   | Type  | Description                           |
|---------|-------|---------------------------------------|
| `hours` | float | Return samples from the last N hours  |
| `since` | float | Unix timestamp lower bound            |
| `until` | float | Unix timestamp upper bound            |
| `limit` | int   | Maximum number of results             |

```bash
curl "http://127.0.0.1:8000/api/v1/samples?hours=1"
```

### `DELETE /api/v1/samples?before=<timestamp>`

Deletes all samples with `ts < before`.

```bash
# Delete samples older than 24 hours
curl -X DELETE "http://127.0.0.1:8000/api/v1/samples?before=$(date -d '24 hours ago' +%s)"
# macOS:
curl -X DELETE "http://127.0.0.1:8000/api/v1/samples?before=$(date -v-24H +%s)"
```

### `GET /api/v1/status`

Returns current configuration, uptime, sample count, and last-hour aggregates.

```bash
curl http://127.0.0.1:8000/api/v1/status
```

### `GET /api/v1/hosts`

Returns all monitored hosts with their enabled/disabled status.

```bash
curl http://127.0.0.1:8000/api/v1/hosts
```

### `POST /api/v1/hosts`

Adds a new host to monitor.

```bash
curl -X POST http://127.0.0.1:8000/api/v1/hosts \
  -H "Content-Type: application/json" \
  -d '{"address": "1.1.1.1"}'
```

Returns `409` if the host already exists.

### `DELETE /api/v1/hosts/{address}`

Removes a host and stops collecting samples for it.

```bash
curl -X DELETE http://127.0.0.1:8000/api/v1/hosts/1.1.1.1
```

### `PATCH /api/v1/hosts/{address}`

Enables or disables display of a host in the UI without removing it.

```bash
curl -X PATCH http://127.0.0.1:8000/api/v1/hosts/1.1.1.1 \
  -H "Content-Type: application/json" \
  -d '{"enabled": false}'
```

## Metrics Explained

| Metric        | Meaning                                                              |
|---------------|----------------------------------------------------------------------|
| **Latency**   | Round-trip time in milliseconds. Higher = slower connection.         |
| **Packet loss** | % of ping packets that never returned. >1% indicates problems.    |
| **Jitter**    | Standard deviation of round-trip times. High jitter hurts VoIP/video.|
| **Uptime**    | % of samples with <100% packet loss over the selected time window.   |

## Data Management

Delete old samples from the UI: enter the age in hours and click **Delete**.

From the command line:

```bash
# Keep only the last 7 days
curl -X DELETE "http://127.0.0.1:8000/api/v1/samples?before=$(python3 -c 'import time; print(time.time()-7*86400)')"
```

## Troubleshooting

**`ping: socket: Operation not permitted`** — on some Linux systems, `ping` requires elevated privileges:

```bash
sudo setcap cap_net_raw+ep $(which ping)
```

**No samples appearing** — check terminal output for `[COLLECTOR]` lines. If ping times out repeatedly, verify that `TARGET_HOST` is reachable from your machine.

**Port already in use** — set `PORT=8001` (or any free port) in your `.env`.

### Windows

**`asyncio` event loop** — automatically handled by `main.py` (sets `WindowsSelectorEventLoopPolicy` before uvicorn starts).

**Firewall blocking ping** — if `ping` returns no replies, allow ICMPv4 through Windows Firewall:

```cmd
netsh advfirewall firewall add rule name="Allow ICMPv4" protocol=icmpv4:8,any dir=out action=allow
```

**Jitter on Windows** — Windows `ping` does not report standard deviation natively. MCNet_checker calculates jitter from individual reply times (`time=Xms` lines) as population standard deviation.
