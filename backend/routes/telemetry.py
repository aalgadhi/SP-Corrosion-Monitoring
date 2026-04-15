from fastapi import APIRouter

from database import insert_diagnostic, insert_reading_with_timestamp
from inference import build_external_diagnostic
from models import TelemetryTuple, TelemetryIngestResponse

router = APIRouter()


@router.post("/telemetry", response_model=TelemetryIngestResponse)
async def ingest_telemetry(payload: TelemetryTuple) -> TelemetryIngestResponse:
    reading_data = payload.reading.model_dump()
    timestamp = reading_data.get("timestamp")
    if timestamp:
        reading_id = await insert_reading_with_timestamp(reading_data)
    else:
        from database import insert_reading
        reading_data.pop("timestamp", None)
        reading_id = await insert_reading(reading_data)

    diagnostic_payload = build_external_diagnostic(
        reading=payload.reading,
        predicted_rul=payload.predicted_rul,
        confidence=payload.model_confidence,
        model_version=payload.model_version,
        timestamp=timestamp,
    )
    diagnostic_id = await insert_diagnostic(diagnostic_payload)

    return TelemetryIngestResponse(
        status="ok",
        reading_id=reading_id,
        diagnostic_id=diagnostic_id,
    )
