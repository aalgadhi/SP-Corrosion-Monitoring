from fastapi import APIRouter, Query

from database import get_alerts_list

router = APIRouter()


@router.get("/alerts")
async def alerts(
    limit: int = Query(20, ge=1, le=100),
    active_only: bool = Query(False),
) -> list[dict]:
    return await get_alerts_list(limit=limit, active_only=active_only)
