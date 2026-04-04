from pydantic import BaseModel, Field


class SensorReading(BaseModel):
    h2s: float = Field(..., ge=0, description="H2S in ppm")
    co: float = Field(..., ge=0, description="CO in ppm")
    ch4: float = Field(..., ge=0, description="CH4 in % LEL")
    o2: float = Field(..., ge=0, le=100, description="O2 in % v/v")
    flow_rate: float | None = Field(None, ge=0, description="Flow rate in m3/hr")
    temperature: float | None = Field(None, description="Temperature in C")
    pressure: float | None = Field(None, ge=0, description="Pressure in bar")


class IngestResponse(BaseModel):
    status: str = "ok"
    reading_id: int


class DiagnosticResult(BaseModel):
    condition: str
    rul_days: float | None
    confidence: float
    timestamp: str | None = None


class DiagnosticsResponse(BaseModel):
    latest: DiagnosticResult | None
    history: list[DiagnosticResult]


class Alert(BaseModel):
    id: int
    timestamp: str
    severity: str
    message: str
    condition: str | None
    acknowledged: int


class StatsResponse(BaseModel):
    total_readings: int
    total_diagnostics: int
    total_alerts: int
    oldest_reading: str | None
    newest_reading: str | None
    days_of_data: float
    db_size_mb: float
    spec_s8_met: bool
