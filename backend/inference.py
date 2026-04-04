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
) -> dict:
    if _use_placeholder:
        return _placeholder_predict(h2s, co, ch4, o2, flow_rate, temperature, pressure)

    import numpy as np
    features = np.array([[h2s, co, ch4, o2,
                          flow_rate or 0.75,
                          temperature or 60.0,
                          pressure or 4.0]])
    scaled = _scaler.transform(features)
    rul_days = float(_model.predict(scaled)[0])
    condition = _classify_from_rul(rul_days)
    confidence = min(0.95, max(0.5, 1.0 - (abs(rul_days - 1000) / 5000)))
    return {"condition": condition, "rul_days": round(rul_days, 1), "confidence": round(confidence, 2)}


def _classify_from_rul(rul_days: float) -> str:
    if rul_days > 365:
        return "normal"
    if rul_days > 90:
        return "corrosion"
    if rul_days > 30:
        return "fouling"
    return "leak"


def _placeholder_predict(
    h2s: float,
    co: float,
    ch4: float,
    o2: float,
    flow_rate: float | None,
    temperature: float | None,
    pressure: float | None,
) -> dict:
    if co > 150:
        condition = "leak"
        rul_days = max(5, 30 - (co - 150) * 0.1)
        confidence = min(0.95, 0.7 + (co - 150) / 500)
    elif h2s > 30:
        condition = "corrosion"
        rul_days = max(30, 365 - (h2s - 30) * 5)
        confidence = min(0.92, 0.65 + (h2s - 30) / 100)
    elif ch4 > 15:
        condition = "fouling"
        rul_days = max(60, 200 - (ch4 - 15) * 3)
        confidence = min(0.88, 0.6 + (ch4 - 15) / 50)
    else:
        condition = "normal"
        rul_days = 1825 + (20.9 - h2s) * 10
        confidence = 0.94
    return {
        "condition": condition,
        "rul_days": round(rul_days, 1),
        "confidence": round(confidence, 2),
    }


load_model()
