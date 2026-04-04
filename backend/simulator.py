"""
Sensor data simulator for the Corrosion Gas Monitor.

Usage:
    python simulator.py --mode normal --interval 1 --url http://localhost:8000
    python simulator.py --mode corrosion --interval 1 --duration 3600
    python simulator.py --seed-days 10
"""

import argparse
import asyncio
import random
import sys
from datetime import datetime, timedelta, timezone

import httpx

RANGES = {
    "normal": {
        "h2s": (0, 20), "co": (0, 50), "ch4": (0, 10), "o2": (19.5, 21.0),
        "flow_rate": (0.5, 1.0), "temperature": (40, 80), "pressure": (2, 6),
    },
    "corrosion": {
        "h2s": (40, 80), "co": (30, 70), "ch4": (5, 15), "o2": (16, 18),
        "flow_rate": (0.4, 0.8), "temperature": (55, 95), "pressure": (2.5, 5.5),
    },
    "fouling": {
        "h2s": (5, 25), "co": (10, 40), "ch4": (20, 40), "o2": (18.5, 20.5),
        "flow_rate": (0.3, 0.7), "temperature": (45, 75), "pressure": (2, 5),
    },
    "leak": {
        "h2s": (10, 30), "co": (100, 300), "ch4": (5, 15), "o2": (17, 19),
        "flow_rate": (0.6, 1.0), "temperature": (50, 85), "pressure": (1.5, 4.0),
    },
}


def generate_reading(mode: str) -> dict:
    r = RANGES[mode]
    return {
        "h2s": round(random.uniform(*r["h2s"]), 2),
        "co": round(random.uniform(*r["co"]), 2),
        "ch4": round(random.uniform(*r["ch4"]), 2),
        "o2": round(random.uniform(*r["o2"]), 2),
        "flow_rate": round(random.uniform(*r["flow_rate"]), 3),
        "temperature": round(random.uniform(*r["temperature"]), 1),
        "pressure": round(random.uniform(*r["pressure"]), 2),
    }


async def seed_days(days: int, url: str) -> None:
    """Bulk-insert N days of historical data directly via the API."""
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=days)
    interval_seconds = 60  # one reading per minute
    total = int(days * 86400 / interval_seconds)

    print(f"Seeding {total} readings over {days} days...")

    modes = ["normal"] * 70 + ["corrosion"] * 15 + ["fouling"] * 10 + ["leak"] * 5
    batch_size = 100
    async with httpx.AsyncClient(timeout=30) as client:
        for i in range(total):
            ts = start + timedelta(seconds=i * interval_seconds)
            mode = random.choice(modes)
            reading = generate_reading(mode)
            reading["timestamp"] = ts.strftime("%Y-%m-%dT%H:%M:%SZ")

            try:
                resp = await client.post(f"{url}/api/ingest", json=reading)
                if resp.status_code != 200:
                    print(f"Error at {i}: {resp.status_code}")
            except httpx.RequestError as e:
                print(f"Connection error at {i}: {e}")
                return

            if (i + 1) % batch_size == 0:
                pct = (i + 1) / total * 100
                print(f"  {i + 1}/{total} ({pct:.1f}%)")

    print(f"Done! Seeded {total} readings.")


async def live_stream(mode: str, interval: float, duration: float | None, url: str) -> None:
    """Send readings in real time."""
    print(f"Streaming '{mode}' readings every {interval}s to {url}")
    elapsed = 0.0
    async with httpx.AsyncClient(timeout=10) as client:
        while True:
            reading = generate_reading(mode)
            try:
                resp = await client.post(f"{url}/api/ingest", json=reading)
                print(f"[{mode}] h2s={reading['h2s']} co={reading['co']} → {resp.status_code}")
            except httpx.RequestError as e:
                print(f"Error: {e}")

            await asyncio.sleep(interval)
            elapsed += interval
            if duration and elapsed >= duration:
                print("Duration reached. Stopping.")
                break


def main() -> None:
    parser = argparse.ArgumentParser(description="Corrosion Gas Monitor Simulator")
    parser.add_argument("--mode", choices=["normal", "corrosion", "fouling", "leak"], default="normal")
    parser.add_argument("--interval", type=float, default=1.0, help="Seconds between readings")
    parser.add_argument("--duration", type=float, default=None, help="Total seconds to run")
    parser.add_argument("--url", default="http://localhost:8000", help="Backend URL")
    parser.add_argument("--seed-days", type=int, default=None, help="Bulk-seed N days of data")
    args = parser.parse_args()

    if args.seed_days:
        asyncio.run(seed_days(args.seed_days, args.url))
    else:
        asyncio.run(live_stream(args.mode, args.interval, args.duration, args.url))


if __name__ == "__main__":
    main()
