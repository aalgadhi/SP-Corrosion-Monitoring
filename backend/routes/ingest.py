from fastapi import APIRouter, HTTPException

from database import insert_reading, insert_diagnostic, insert_alert, get_reading_count
from models import SensorReading, IngestResponse
from inference import predict

router = APIRouter()

INFERENCE_EVERY_N = 10


@router.post("/ingest", response_model=IngestResponse)
async def ingest(reading: SensorReading) -> IngestResponse:
    data = reading.model_dump()
    reading_id = await insert_reading(data)

    count = await get_reading_count()
    if count % INFERENCE_EVERY_N == 0:
        result = predict(
            h2s=reading.h2s,
            co=reading.co,
            ch4=reading.ch4,
            o2=reading.o2,
            flow_rate=reading.flow_rate,
            temperature=reading.temperature,
            pressure=reading.pressure,
        )
        await insert_diagnostic(result)

        if result["condition"] != "normal":
            severity = "critical" if result["condition"] in ("leak",) else "warning"
            msg = f"{result['condition'].capitalize()} detected — RUL: {result['rul_days']} days (confidence: {result['confidence']})"
            await insert_alert({
                "severity": severity,
                "message": msg,
                "condition": result["condition"],
            })

    return IngestResponse(status="ok", reading_id=reading_id)
