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
from datetime import datetime, timedelta, timezone

import httpx

RANGES = {
    "normal": {
        "h2s": (0, 20), "co": (0, 50), "co2": (300, 800), "ch4": (0, 10), "o2": (19.5, 21.0),
        "flow_rate": (0.5, 1.0), "temperature": (40, 80), "pressure": (2, 6),
        "humidity": (30, 55),
    },
    "corrosion": {
        "h2s": (25, 80), "co": (30, 120), "co2": (800, 5000), "ch4": (5, 15), "o2": (16, 19),
        "flow_rate": (0.3, 0.8), "temperature": (55, 95), "pressure": (2.5, 5.5),
        "humidity": (55, 85),
    },
}

DEVICES = [
    {"device_id": "ESP32-001", "name": "Pipe Section A - Inlet", "type": "ESP32", "location": "Unit 12, Pipe A", "ip_address": "192.168.1.101"},
    {"device_id": "ESP32-002", "name": "Pipe Section B - Mid", "type": "ESP32", "location": "Unit 12, Pipe B", "ip_address": "192.168.1.102"},
    {"device_id": "ESP32-003", "name": "Pipe Section C - Outlet", "type": "ESP32", "location": "Unit 12, Pipe C", "ip_address": "192.168.1.103"},
]


def generate_reading(mode: str) -> dict:
    r = RANGES[mode]
    return {
        "h2s": round(random.uniform(*r["h2s"]), 2),
        "co": round(random.uniform(*r["co"]), 2),
        "co2": round(random.uniform(*r["co2"]), 1),
        "ch4": round(random.uniform(*r["ch4"]), 2),
        "o2": round(random.uniform(*r["o2"]), 2),
        "flow_rate": round(random.uniform(*r["flow_rate"]), 3),
        "temperature": round(random.uniform(*r["temperature"]), 1),
        "pressure": round(random.uniform(*r["pressure"]), 2),
        "humidity": round(random.uniform(*r["humidity"]), 1),
    }


async def seed_devices(url: str) -> None:
    """Register demo devices."""
    async with httpx.AsyncClient(timeout=10) as client:
        for i, dev in enumerate(DEVICES):
            status = "online" if i < 2 else "offline"
            dev_copy = {**dev, "status": status}
            try:
                await client.post(f"{url}/api/devices/heartbeat", json=dev_copy)
                print(f"  Registered device: {dev['name']} ({status})")
            except httpx.RequestError as e:
                print(f"  Error registering {dev['name']}: {e}")


async def seed_days(days: int, url: str) -> None:
    """Bulk-insert N days of historical data directly via the API."""
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=days)
    interval_seconds = 60  # one reading per minute
    total = int(days * 86400 / interval_seconds)

    print(f"Seeding {total} readings over {days} days...")
    print("Registering devices...")
    await seed_devices(url)

    # 80% normal, 20% corrosion
    modes = ["normal"] * 80 + ["corrosion"] * 20
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
    print("Sending device heartbeats...")
    await seed_devices(url)

    elapsed = 0.0
    async with httpx.AsyncClient(timeout=10) as client:
        while True:
            reading = generate_reading(mode)
            try:
                resp = await client.post(f"{url}/api/ingest", json=reading)
                print(f"[{mode}] h2s={reading['h2s']} co={reading['co']} temp={reading['temperature']} hum={reading['humidity']} -> {resp.status_code}")
            except httpx.RequestError as e:
                print(f"Error: {e}")

            await asyncio.sleep(interval)
            elapsed += interval
            if duration and elapsed >= duration:
                print("Duration reached. Stopping.")
                break


def main() -> None:
    parser = argparse.ArgumentParser(description="Corrosion Gas Monitor Simulator")
    parser.add_argument("--mode", choices=["normal", "corrosion"], default="normal")
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
