from fastapi import APIRouter, Query

from database import get_readings

router = APIRouter()


@router.get("/readings")
async def readings(
    limit: int = Query(60, ge=1, le=10000),
    offset: int = Query(0, ge=0),
    since: str | None = Query(None),
    until: str | None = Query(None),
) -> list[dict]:
    return await get_readings(limit=limit, offset=offset, since=since, until=until)
