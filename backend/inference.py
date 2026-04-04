from pathlib import Path

MODEL_DIR = Path(__file__).resolve().parent.parent / "model"
MODEL_PATH = MODEL_DIR / "xgb_rul_model.joblib"
SCALER_PATH = MODEL_DIR / "scaler.joblib"

_model = None
_scaler = None
_use_placeholder = True


def load_model() -> None:
    global _model, _scaler, _use_placeholder
    if MODEL_PATH.exists() and SCALER_PATH.exists():
        import joblib
        _model = joblib.load(str(MODEL_PATH))
        _scaler = joblib.load(str(SCALER_PATH))
        _use_placeholder = False
    else:
        _use_placeholder = True


def predict(
    h2s: float,
    co: float,
    ch4: float,
    o2: float,
    flow_rate: float | None = None,
    temperature: float | None = None,
    pressure: float | None = None,
    humidity: float | None = None,
) -> dict:
    if _use_placeholder:
        return _placeholder_predict(h2s, co, ch4, o2, flow_rate, temperature, pressure, humidity)

    import numpy as np
    features = np.array([[h2s, co, ch4, o2,
                          flow_rate or 0.75,
                          temperature or 60.0,
                          pressure or 4.0]])
    scaled = _scaler.transform(features)
    rul_days = float(_model.predict(scaled)[0])
    condition = "corrosion" if rul_days < 365 else "normal"
    confidence = min(0.95, max(0.5, 1.0 - (abs(rul_days - 1000) / 5000)))
    corrosion_rate = _estimate_corrosion_rate(h2s, co, temperature, humidity)
    health_score = _compute_health_score(rul_days, corrosion_rate)
    return {
        "condition": condition,
        "rul_days": round(rul_days, 1),
        "confidence": round(confidence, 2),
        "corrosion_rate": round(corrosion_rate, 3),
        "health_score": round(health_score, 1),
    }


def _estimate_corrosion_rate(
    h2s: float, co: float,
    temperature: float | None,
    humidity: float | None,
) -> float:
    """Estimate corrosion rate in mm/year based on gas levels and environment."""
    base_rate = 0.05
    # H2S contribution (major corrosion driver)
    h2s_factor = h2s / 100 * 0.8
    # CO contribution
    co_factor = co / 300 * 0.3
    # Temperature accelerates corrosion
    temp = temperature or 60.0
    temp_factor = max(0, (temp - 40) / 60) * 0.4
    # Humidity accelerates corrosion
    hum = humidity or 50.0
    hum_factor = max(0, (hum - 30) / 70) * 0.3

    rate = base_rate + h2s_factor + co_factor + temp_factor + hum_factor
    return max(0.01, min(rate, 5.0))


def _compute_health_score(rul_days: float, corrosion_rate: float) -> float:
    """Compute 0-100 health score from RUL and corrosion rate."""
    # RUL component (0-70 points): 1825 days (5 years) = full score
    rul_score = min(70, (rul_days / 1825) * 70)
    # Corrosion rate component (0-30 points): lower is better
    rate_score = max(0, 30 - (corrosion_rate / 2.0) * 30)
    return max(0, min(100, rul_score + rate_score))


def _placeholder_predict(
    h2s: float,
    co: float,
    ch4: float,
    o2: float,
    flow_rate: float | None,
    temperature: float | None,
    pressure: float | None,
    humidity: float | None,
) -> dict:
    # Simplified: only normal vs corrosion
    if h2s > 25 or co > 100 or (o2 is not None and o2 < 18.5):
        condition = "corrosion"
        rul_days = max(30, 365 - (h2s - 20) * 8 - max(0, co - 50) * 1.5)
        confidence = min(0.95, 0.65 + h2s / 200 + co / 1000)
    else:
        condition = "normal"
        rul_days = 1825 + (20.9 - h2s) * 10
        confidence = 0.94

    corrosion_rate = _estimate_corrosion_rate(h2s, co, temperature, humidity)
    health_score = _compute_health_score(rul_days, corrosion_rate)

    return {
        "condition": condition,
        "rul_days": round(rul_days, 1),
        "confidence": round(confidence, 2),
        "corrosion_rate": round(corrosion_rate, 3),
        "health_score": round(health_score, 1),
    }


load_model()
