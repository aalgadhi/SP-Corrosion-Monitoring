from fastapi import APIRouter, Query

from database import get_diagnostics_list
from models import DiagnosticsResponse, DiagnosticResult

router = APIRouter()


@router.get("/diagnostics", response_model=DiagnosticsResponse)
async def diagnostics(limit: int = Query(1, ge=1, le=100)) -> DiagnosticsResponse:
    rows = await get_diagnostics_list(limit=max(limit, 10))
    if not rows:
        return DiagnosticsResponse(latest=None, history=[])
    latest = DiagnosticResult(**rows[0])
    history = [DiagnosticResult(**r) for r in rows[1:]]
    return DiagnosticsResponse(latest=latest, history=history)
