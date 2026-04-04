from fastapi import APIRouter

from database import get_stats
from models import StatsResponse

router = APIRouter()


@router.get("/stats", response_model=StatsResponse)
async def stats() -> StatsResponse:
    data = await get_stats()
    return StatsResponse(**data)
