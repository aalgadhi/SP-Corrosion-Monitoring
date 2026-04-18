import aiosqlite
from pathlib import Path
from typing import Any

DB_PATH = Path(__file__).resolve().parent.parent / "corrosion_monitor.db"


async def get_db() -> aiosqlite.Connection:
    db = await aiosqlite.connect(str(DB_PATH))
    db.row_factory = aiosqlite.Row
    return db


async def init_db() -> None:
    db = await get_db()
    try:
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS sensor_readings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
                h2s REAL NOT NULL,
                co REAL NOT NULL,
                ch4 REAL NOT NULL,
                o2 REAL NOT NULL,
                co2 REAL,
                flow_rate REAL,
                temperature REAL,
                pressure REAL,
                humidity REAL
            );
            CREATE INDEX IF NOT EXISTS idx_readings_ts ON sensor_readings(timestamp);

            CREATE TABLE IF NOT EXISTS diagnostics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
                condition TEXT NOT NULL,
                rul_days REAL,
                confidence REAL,
                corrosion_rate REAL,
                health_score REAL,
                model_version TEXT DEFAULT 'xgb-v1'
            );
            CREATE INDEX IF NOT EXISTS idx_diag_ts ON diagnostics(timestamp);

            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
                severity TEXT NOT NULL,
                message TEXT NOT NULL,
                condition TEXT,
                acknowledged INTEGER DEFAULT 0
            );
            CREATE INDEX IF NOT EXISTS idx_alerts_ts ON alerts(timestamp);

            CREATE TABLE IF NOT EXISTS devices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_id TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                type TEXT DEFAULT 'ESP32',
                location TEXT,
                status TEXT DEFAULT 'offline',
                last_seen TEXT,
                ip_address TEXT
            );
        """)
        await db.commit()
    finally:
        await db.close()


async def insert_reading(data: dict[str, Any]) -> int:
    db = await get_db()
    try:
        cursor = await db.execute(
            """INSERT INTO sensor_readings (h2s, co, ch4, o2, co2, flow_rate, temperature, pressure, humidity)
               VALUES (:h2s, :co, :ch4, :o2, :co2, :flow_rate, :temperature, :pressure, :humidity)""",
            data,
        )
        await db.commit()
        return cursor.lastrowid
    finally:
        await db.close()


async def insert_reading_with_timestamp(data: dict[str, Any]) -> int:
    db = await get_db()
    try:
        cursor = await db.execute(
            """INSERT INTO sensor_readings (timestamp, h2s, co, ch4, o2, co2, flow_rate, temperature, pressure, humidity)
               VALUES (:timestamp, :h2s, :co, :ch4, :o2, :co2, :flow_rate, :temperature, :pressure, :humidity)""",
            data,
        )
        await db.commit()
        return cursor.lastrowid
    finally:
        await db.close()


async def insert_diagnostic(data: dict[str, Any]) -> int:
    db = await get_db()
    try:
        payload = {
            "timestamp": data.get("timestamp"),
            "condition": data["condition"],
            "rul_days": data.get("rul_days"),
            "confidence": data.get("confidence"),
            "corrosion_rate": data.get("corrosion_rate"),
            "health_score": data.get("health_score"),
            "model_version": data.get("model_version", "xgb-v1"),
        }
        cursor = await db.execute(
            """INSERT INTO diagnostics (timestamp, condition, rul_days, confidence, corrosion_rate, health_score, model_version)
               VALUES (COALESCE(:timestamp, strftime('%Y-%m-%dT%H:%M:%SZ', 'now')), :condition, :rul_days, :confidence, :corrosion_rate, :health_score, :model_version)""",
            payload,
        )
        await db.commit()
        return cursor.lastrowid
    finally:
        await db.close()


async def insert_alert(data: dict[str, Any]) -> int:
    db = await get_db()
    try:
        cursor = await db.execute(
            """INSERT INTO alerts (severity, message, condition)
               VALUES (:severity, :message, :condition)""",
            data,
        )
        await db.commit()
        return cursor.lastrowid
    finally:
        await db.close()


async def upsert_device(data: dict[str, Any]) -> None:
    db = await get_db()
    try:
        await db.execute(
            """INSERT INTO devices (device_id, name, type, location, status, last_seen, ip_address)
               VALUES (:device_id, :name, :type, :location, :status, :last_seen, :ip_address)
               ON CONFLICT(device_id) DO UPDATE SET
                   status = :status,
                   last_seen = :last_seen,
                   ip_address = :ip_address""",
            data,
        )
        await db.commit()
    finally:
        await db.close()


async def get_devices() -> list[dict]:
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM devices ORDER BY name")
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        await db.close()


async def get_readings(
    limit: int = 60,
    offset: int = 0,
    since: str | None = None,
    until: str | None = None,
) -> list[dict]:
    db = await get_db()
    try:
        query = "SELECT * FROM sensor_readings WHERE 1=1"
        params: list[Any] = []
        if since:
            query += " AND timestamp >= ?"
            params.append(since)
        if until:
            query += " AND timestamp <= ?"
            params.append(until)
        query += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        cursor = await db.execute(query, params)
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        await db.close()


async def get_diagnostics_list(limit: int = 1) -> list[dict]:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM diagnostics ORDER BY timestamp DESC LIMIT ?", (limit,)
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        await db.close()


async def get_rul_history(limit: int = 100) -> list[dict]:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT timestamp, rul_days, corrosion_rate, health_score FROM diagnostics ORDER BY timestamp DESC LIMIT ?",
            (limit,),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        await db.close()


async def get_alerts_list(
    limit: int = 20, active_only: bool = False
) -> list[dict]:
    db = await get_db()
    try:
        query = "SELECT * FROM alerts"
        if active_only:
            query += " WHERE acknowledged = 0"
        query += " ORDER BY timestamp DESC LIMIT ?"
        cursor = await db.execute(query, (limit,))
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        await db.close()


async def get_reading_count() -> int:
    db = await get_db()
    try:
        cursor = await db.execute("SELECT COUNT(*) as cnt FROM sensor_readings")
        row = await cursor.fetchone()
        return row["cnt"]
    finally:
        await db.close()


async def get_stats() -> dict:
    db = await get_db()
    try:
        cursor = await db.execute("""
            SELECT
                COUNT(*) as total_readings,
                MIN(timestamp) as oldest_reading,
                MAX(timestamp) as newest_reading
            FROM sensor_readings
        """)
        r = dict(await cursor.fetchone())

        cursor = await db.execute("SELECT COUNT(*) as cnt FROM diagnostics")
        d = await cursor.fetchone()

        cursor = await db.execute("SELECT COUNT(*) as cnt FROM alerts")
        a = await cursor.fetchone()

        cursor = await db.execute("SELECT COUNT(*) as cnt FROM devices WHERE status = 'online'")
        dev_online = await cursor.fetchone()

        cursor = await db.execute("SELECT COUNT(*) as cnt FROM devices")
        dev_total = await cursor.fetchone()

        days_of_data = 0.0
        if r["oldest_reading"] and r["newest_reading"]:
            from datetime import datetime
            fmt = "%Y-%m-%dT%H:%M:%SZ"
            oldest = datetime.strptime(r["oldest_reading"], fmt)
            newest = datetime.strptime(r["newest_reading"], fmt)
            days_of_data = (newest - oldest).total_seconds() / 86400

        db_size_mb = DB_PATH.stat().st_size / (1024 * 1024) if DB_PATH.exists() else 0

        days_rounded = round(days_of_data, 1)
        return {
            "total_readings": r["total_readings"],
            "total_diagnostics": d["cnt"],
            "total_alerts": a["cnt"],
            "oldest_reading": r["oldest_reading"],
            "newest_reading": r["newest_reading"],
            "days_of_data": days_rounded,
            "db_size_mb": round(db_size_mb, 1),
            "spec_s8_met": days_rounded >= 90,
            "devices_online": dev_online["cnt"],
            "devices_total": dev_total["cnt"],
        }
    finally:
        await db.close()
