from pydantic import BaseModel, Field


class SensorReading(BaseModel):
    h2s: float = Field(..., ge=0, description="H2S in ppm")
    co: float = Field(..., ge=0, description="CO in ppm")
    ch4: float = Field(..., ge=0, description="CH4 in % LEL")
    o2: float = Field(..., ge=0, le=100, description="O2 in % v/v")
    co2: float | None = Field(None, ge=0, description="CO2 in ppm")
    flow_rate: float | None = Field(None, ge=0, description="Flow rate in m3/hr")
    temperature: float | None = Field(None, description="Temperature in C")
    pressure: float | None = Field(None, ge=0, description="Pressure in bar")
    humidity: float | None = Field(None, ge=0, le=100, description="Relative humidity %")
    timestamp: str | None = Field(None, description="ISO 8601 timestamp (optional, for seeding)")


class IngestResponse(BaseModel):
    status: str = "ok"
    reading_id: int


class DiagnosticResult(BaseModel):
    condition: str
    rul_days: float | None
    confidence: float
    corrosion_rate: float | None = None
    health_score: float | None = None
    timestamp: str | None = None


class DiagnosticsResponse(BaseModel):
    latest: DiagnosticResult | None
    history: list[DiagnosticResult]


class RULPoint(BaseModel):
    timestamp: str
    rul_days: float | None
    corrosion_rate: float | None
    health_score: float | None


class Alert(BaseModel):
    id: int
    timestamp: str
    severity: str
    message: str
    condition: str | None
    acknowledged: int


class Device(BaseModel):
    id: int
    device_id: str
    name: str
    type: str
    location: str | None
    status: str
    last_seen: str | None
    ip_address: str | None


class StatsResponse(BaseModel):
    total_readings: int
    total_diagnostics: int
    total_alerts: int
    oldest_reading: str | None
    newest_reading: str | None
    days_of_data: float
    db_size_mb: float
    spec_s8_met: bool
    devices_online: int
    devices_total: int
