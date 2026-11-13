"""
Watch the API's live feed (/ws/live) in the terminal, like a dashboard would receive it.

Usage (from the project root, API running):
    python scripts/watch_live.py
    python scripts/watch_live.py --url ws://localhost:8000/api/v1/ws/live --pings
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime

import websockets
from websockets.exceptions import ConnectionClosed


def describe(event: dict) -> str:
    kind, data = event["type"], event["data"]
    now = datetime.now().strftime("%H:%M:%S")
    if kind == "anomaly.created":
        reasons = "; ".join(data.get("summary", {}).get("reasons", []))
        return (f"{now}  ANOMALY  window {data['window_start'][11:16]} UTC  {data['service']:<18} "
                f"{data['severity']:<8} score {data['anomaly_score']:.2f}  {reasons}")
    if kind in ("alert.created", "alert.updated"):
        return f"{now}  {kind.upper():<14} {data['service']:<18} {data['severity']:<8} {data['status']}: {data['title']}"
    if kind == "ping":
        return f"{now}  ping"
    return f"{now}  {kind}: {json.dumps(data)}"


async def watch(url: str, show_pings: bool) -> None:
    async with websockets.connect(url) as ws:
        print(f"Connected to {url}. Waiting for events (Ctrl+C to stop)...")
        async for raw in ws:
            event = json.loads(raw)
            if event["type"] == "ping" and not show_pings:
                continue
            print(describe(event), flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Print events from the API's /ws/live feed.")
    parser.add_argument("--url", default="ws://localhost:8000/api/v1/ws/live")
    parser.add_argument("--pings", action="store_true", help="also show the 30-second pings")
    args = parser.parse_args()
    try:
        asyncio.run(watch(args.url, args.pings))
    except KeyboardInterrupt:
        pass
    except ConnectionClosed as exc:
        code = exc.rcvd.code if exc.rcvd else "none"
        print(f"Connection closed by the server (code {code}); the API was stopped or restarted.")
    except OSError as exc:
        print(f"[FAIL] cannot connect to {args.url} ({exc}). Is the API running?")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())