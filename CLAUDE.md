# Corrosion Gas Monitor — Dashboard & Backend

## Project Context

This is the ICS/SWE component of a KFUPM Senior Design Project (Team M056, Term 252).
The full project is: **"Design and Prototype of a Compact Multi-Gas Detection System with AI-Based Diagnostics for Refinery Common Piping Problems."**

The system detects corrosion in refinery piping by monitoring 4 gases (H₂S, CO, CH₄, O₂) plus environmental readings (flow rate, temperature, pressure), then uses an XGBoost model to classify pipeline condition and estimate Remaining Useful Life (RUL).

This repo covers **Block 9 (Data Storage)** and **Block 10 (Real-Time Dashboard)** from the system architecture, and provides evidence for:
- **S8**: Database stores ≥ 10 days of sensor data
- **C6**: End-to-end processing time < 60 seconds (measured later)
- **I1**: Early warning accuracy ≥ 90% (classification recall)

---

## Tech Stack

- **Backend**: FastAPI (Python 3.10+)
- **Database**: SQLite (via aiosqlite for async)
- **AI Model**: XGBoost (pre-trained, loaded via joblib)
- **Frontend**: React (Vite), Recharts for charts, TailwindCSS for styling
- **Data Source**: Simulator script (fake sensor data) → later swapped for real ESP32 over HTTP

---

## Project Structure

```
corrosion-monitor/
├── backend/
│   ├── main.py              # FastAPI app, CORS, lifespan, route includes
│   ├── database.py          # SQLite schema, connection, CRUD helpers
│   ├── models.py            # Pydantic request/response schemas
│   ├── inference.py         # Load XGBoost model, run predictions
│   ├── routes/
│   │   ├── ingest.py        # POST /api/ingest
│   │   ├── readings.py      # GET /api/readings
│   │   ├── diagnostics.py   # GET /api/diagnostics
│   │   ├── alerts.py        # GET /api/alerts
│   │   └── stats.py         # GET /api/stats (S8 evidence)
│   └── simulator.py         # Standalone script: generates fake data, POSTs to /api/ingest
├── frontend/
│   ├── src/
│   │   ├── App.jsx
│   │   ├── main.jsx
│   │   ├── components/
│   │   │   ├── GasCards.jsx         # 4 cards: H₂S, CO, CH₄, O₂ with sparklines
│   │   │   ├── DiagnosticsPanel.jsx # AI status badge, RUL, confidence
│   │   │   ├── AlertsPanel.jsx      # Recent alerts list
│   │   │   └── HistoryChart.jsx     # Time-series chart with time range selector
│   │   ├── hooks/
│   │   │   └── usePolling.js        # Custom hook: polls an endpoint at interval
│   │   └── lib/
│   │       └── api.js               # Axios/fetch wrapper for backend calls
│   ├── index.html
│   ├── vite.config.js
│   ├── tailwind.config.js
│   └── package.json
├── model/                           # Pre-trained model artifacts (gitignored if large)
│   ├── xgb_rul_model.joblib
│   └── scaler.joblib
├── corrosion_monitor.db             # SQLite DB (auto-created on first run)
├── requirements.txt
└── README.md
```

---

## Database Schema (SQLite)

### Table: `sensor_readings`
```sql
CREATE TABLE IF NOT EXISTS sensor_readings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    h2s REAL NOT NULL,          -- ppm
    co REAL NOT NULL,           -- ppm
    ch4 REAL NOT NULL,          -- % LEL
    o2 REAL NOT NULL,           -- % v/v
    flow_rate REAL,             -- m³/hr
    temperature REAL,           -- °C
    pressure REAL               -- bar
);
CREATE INDEX IF NOT EXISTS idx_readings_ts ON sensor_readings(timestamp);
```

### Table: `diagnostics`
```sql
CREATE TABLE IF NOT EXISTS diagnostics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    condition TEXT NOT NULL,       -- 'normal', 'corrosion', 'fouling', 'leak'
    rul_days REAL,                 -- Remaining Useful Life in days
    confidence REAL,               -- 0.0–1.0
    model_version TEXT DEFAULT 'xgb-v1'
);
CREATE INDEX IF NOT EXISTS idx_diag_ts ON diagnostics(timestamp);
```

### Table: `alerts`
```sql
CREATE TABLE IF NOT EXISTS alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    severity TEXT NOT NULL,        -- 'warning', 'critical'
    message TEXT NOT NULL,
    condition TEXT,                 -- which condition triggered it
    acknowledged INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_alerts_ts ON alerts(timestamp);
```

---

## API Endpoints

### `POST /api/ingest`
Receives sensor readings from ESP32 or simulator.

**Request body:**
```json
{
  "h2s": 12.5,
  "co": 45.2,
  "ch4": 3.8,
  "o2": 20.1,
  "flow_rate": 0.77,
  "temperature": 55.0,
  "pressure": 3.2
}
```

**Behavior:**
1. Validate input ranges
2. Insert into `sensor_readings`
3. Optionally trigger inference (if enough recent data, e.g., every 10 readings)
4. If inference detects abnormal condition → insert into `diagnostics` and `alerts`
5. Return `{ "status": "ok", "reading_id": 123 }`

### `GET /api/readings`
Query recent sensor data.

**Query params:**
- `limit` (int, default 60) — number of rows
- `offset` (int, default 0)
- `since` (ISO datetime string, optional) — filter readings after this time
- `until` (ISO datetime string, optional) — filter readings before this time

**Response:** Array of reading objects, newest first.

### `GET /api/diagnostics`
Returns latest diagnostic results.

**Query params:**
- `limit` (int, default 1) — how many recent diagnostics to return

**Response:**
```json
{
  "latest": {
    "condition": "normal",
    "rul_days": 1825.3,
    "confidence": 0.94,
    "timestamp": "2025-04-04T12:00:00Z"
  },
  "history": [...]
}
```

### `GET /api/alerts`
Returns recent alerts.

**Query params:**
- `limit` (int, default 20)
- `active_only` (bool, default false) — only unacknowledged alerts

**Response:** Array of alert objects.

### `GET /api/stats`
**This endpoint provides S8 evidence.** Returns database statistics.

**Response:**
```json
{
  "total_readings": 864000,
  "total_diagnostics": 8640,
  "total_alerts": 12,
  "oldest_reading": "2025-03-25T00:00:00Z",
  "newest_reading": "2025-04-04T12:00:00Z",
  "days_of_data": 10.5,
  "db_size_mb": 9.8,
  "spec_s8_met": true
}
```

---

## Data Simulator (`backend/simulator.py`)

A standalone script that simulates sensor readings and POSTs them to the backend.

**Modes:**
1. **Normal operation** — gases fluctuate within safe ranges with small noise
2. **Corrosion onset** — H₂S gradually increases, O₂ drops slightly over hours
3. **Fouling** — CH₄ rises, flow rate decreases
4. **Leak scenario** — sudden CO spike, pressure drops

**Usage:**
```bash
python backend/simulator.py --mode normal --interval 1 --url http://localhost:8000
python backend/simulator.py --mode corrosion --interval 1 --duration 3600
python backend/simulator.py --seed-days 10  # Bulk-seed 10 days of historical data for S8
```

The `--seed-days` flag is critical — it bulk-inserts N days of synthetic data so we can immediately demonstrate S8 compliance without waiting 10 real days.

**Realistic ranges:**
| Gas   | Normal Range     | Corrosion Pattern         |
|-------|-----------------|---------------------------|
| H₂S   | 0–20 ppm        | Gradual rise to 40–80 ppm |
| CO    | 0–50 ppm        | Spikes to 100–300 ppm     |
| CH₄   | 0–10% LEL       | Rises to 20–40% LEL       |
| O₂    | 19.5–21% v/v    | Drops to 16–18% v/v       |
| Temp  | 40–80°C         | +5–15°C above baseline    |
| Press | 2–6 bar         | ±0.5 bar fluctuation      |
| Flow  | 0.5–1.0 m³/hr   | Decreases 10–30%          |

---

## Inference Module (`backend/inference.py`)

Loads the pre-trained XGBoost model and scaler from `model/` directory.

**If model files are not present**, use a placeholder that:
- Returns `"normal"` if all gases within safe thresholds
- Returns `"corrosion"` if H₂S > 30 ppm
- Returns `"leak"` if CO > 150 ppm
- Estimates RUL based on simple linear degradation formula
- This allows development/demo without the actual model artifacts

**When model files ARE present:**
1. Load `xgb_rul_model.joblib` and `scaler.joblib`
2. Collect last N readings from DB
3. Apply scaler transform
4. Generate features (lag variables, rolling mean/std)
5. Run `model.predict()` → RUL in days
6. Apply threshold logic → condition classification
7. Return condition + RUL + confidence

---

## React Frontend

### Layout
Single-page dashboard with a header and 2x2 grid layout (responsive).

```
┌─────────────────────────────────────────────┐
│  Corrosion Gas Monitor        [status dot]  │
├─────────────────────┬───────────────────────┤
│   Gas Concentration │   AI Diagnostics      │
│   Cards (4 cards    │   - Status badge      │
│   in 2x2 grid)     │   - RUL display       │
│                     │   - Confidence bar     │
├─────────────────────┴───────────────────────┤
│   History Chart (time-series, full width)    │
│   [1h] [6h] [24h] [7d] [30d]               │
├─────────────────────────────────────────────┤
│   Recent Alerts                              │
│   - Alert rows with severity + timestamp     │
└─────────────────────────────────────────────┘
```

### Component Details

**GasCards.jsx**
- 4 cards, each showing: gas name, current value + unit, mini sparkline (last 60 readings)
- Color-coded: green (safe), amber (warning), red (critical) based on threshold
- Polls `GET /api/readings?limit=60` every 2 seconds

**DiagnosticsPanel.jsx**
- Large status badge: Normal (green), Warning (amber), Critical (red)
- RUL display: "Estimated remaining life: X days"
- Confidence bar/percentage
- Polls `GET /api/diagnostics` every 5 seconds

**HistoryChart.jsx**
- Recharts `LineChart` with 4 gas series
- Time range selector buttons: 1h, 6h, 24h, 7d, 30d
- Each series can be toggled on/off
- Fetches from `GET /api/readings?since=...&limit=...`

**AlertsPanel.jsx**
- List of recent alerts, color-coded by severity
- Shows timestamp, message, condition
- Polls `GET /api/alerts?limit=10` every 5 seconds

**usePolling.js**
- Custom hook: `usePolling(url, intervalMs)` → `{ data, loading, error }`
- Auto-fetches on mount and at interval
- Handles cleanup on unmount

### Frontend Styling
- Use TailwindCSS utility classes
- Dark theme preferred (industrial/monitoring feel)
- Monospace font for numeric values
- Status colors: green (#22c55e), amber (#f59e0b), red (#ef4444)

---

## Development Commands

```bash
# Backend
cd backend
pip install fastapi uvicorn aiosqlite pydantic joblib xgboost numpy
uvicorn main:app --reload --port 8000

# Seed 10 days of data (for S8 proof)
python simulator.py --seed-days 10

# Run live simulator
python simulator.py --mode normal --interval 1

# Frontend
cd frontend
npm install
npm run dev  # Vite dev server on port 5173
```

---

## Conventions

- Python: snake_case, type hints on all function signatures, async where possible
- React: functional components only, hooks for state, no class components
- API responses: always JSON, always include a top-level status or data field
- Error handling: FastAPI HTTPException with meaningful messages
- Timestamps: always ISO 8601 UTC (e.g., `2025-04-04T12:00:00Z`)
- Keep code clean and modular — each file should have a single responsibility
- Comments only where non-obvious; self-documenting names preferred

---

## Important Notes

- The SQLite DB file (`corrosion_monitor.db`) is auto-created on first backend start
- CORS must be enabled for `http://localhost:5173` (Vite dev server)
- The simulator's `--seed-days` is the fastest path to proving S8 — run it first
- If model artifacts aren't available, the placeholder inference is fine for demo
- The `/api/stats` endpoint is specifically designed for the Update Presentation 2 slide — it computes everything needed to prove S8 compliance
