from fastapi import APIRouter

from database import get_devices, upsert_device

router = APIRouter()


@router.get("/devices")
async def list_devices() -> list[dict]:
    return await get_devices()


@router.post("/devices/heartbeat")
async def device_heartbeat(data: dict) -> dict:
    from datetime import datetime, timezone
    device_data = {
        "device_id": data["device_id"],
        "name": data.get("name", data["device_id"]),
        "type": data.get("type", "ESP32"),
        "location": data.get("location"),
        "status": "online",
        "last_seen": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "ip_address": data.get("ip_address"),
    }
    await upsert_device(device_data)
    return {"status": "ok"}
