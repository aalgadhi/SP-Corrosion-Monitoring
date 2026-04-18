# Corrosion Gas Monitor — Dashboard, Backend & AI

## Project Context

This is the ICS/SWE + AI component of a KFUPM Senior Design Project (Team M056, Term 252).
The full project is: **"Design and Prototype of a Compact Multi-Gas Detection System with AI-Based Diagnostics for Refinery Common Piping Problems."**

The system detects corrosion in refinery piping by monitoring 5 gases (H₂S, CO, CO₂, CH₄, O₂) plus environmental readings (flow rate, temperature, pressure, humidity), then uses a PyTorch sequence model (Transformer + GRU) to estimate Remaining Useful Life (RUL) and derive condition, corrosion rate, and health score.

This repo covers **Block 9 (Data Storage)**, **Block 10 (Real-Time Dashboard)**, and the **AI pipeline** (Block 8) of the system architecture.

---

## Specifications & Constraints

These are the spec-sheet targets the system must meet. Each line names where in the code the measurement lives.

| ID | Target | How it's measured |
|----|--------|-------------------|
| **C7** — Model fits in RAM | ≤ 8 GB | Count trainable parameters × element size in `AI/model.py` after training; exported artifact on disk is a strict lower bound. |
| **C8** — Dataset size | ≥ 25,000 – 30,000 labeled samples | Row count of the generated `corrosion_dataset_real_rul.csv`. Current generator defaults (10,000 segments × 400 monthly steps) produce ~4,000,000 rows, comfortably above the floor. |
| **S7** — Prediction error | < 20% | MAPE (mean absolute percentage error) on the held-out test split, computed in `AI/model.py::compute_metrics`. |
| **S8** — DB retention | ≥ 90 days of sensor data | `GET /api/stats` returns `days_of_data` and `spec_s8_met`. Back-fill with `simulator.py --seed-days 90` to generate evidence. |
| **I1** — Early-warning accuracy | ≥ 80% **integrated**: `model_accuracy × sensor_accuracy` | Model accuracy is binary classification accuracy `(TP+TN)/N` on the "corrosion imminent" label (true RUL ≤ 365 days). Sensor accuracy is the compound sensor-chain accuracy from datasheets. Multiplied together they must meet the 80% bar. |

Definitions:
- **Model accuracy (for I1)**: `(TP + TN) / N`, *not* recall. Evaluated on the same test split as S7.
- **Sensor accuracy (for I1)**: worst-case or compound value taken from the H₂S / CO / CO₂ / O₂ / temperature datasheet specs for the deployed sensor chain.

---

## Tech Stack

- **Backend**: FastAPI (Python 3.10+)
- **Database**: SQLite (via `aiosqlite` for async)
- **AI Model**: PyTorch sequence model (Transformer + GRU). Training in `AI/model.py`, exported to `AI/exported/rul_sequence_model.pt` and loaded by `AI/runtime.py`.
- **Frontend**: React (Vite), Recharts for charts, TailwindCSS for styling.
- **Hardware**: Arduino Mega (sensor sampling) → ESP32 (Wi-Fi/UDP bridge + display) → PC UDP logger (runs the exported model) → backend over HTTP.
- **Data Source**: Simulator script *or* real hardware pipeline via `POST /api/telemetry`.

---

## Project Structure

```
corrosion-monitor/
├── AI/
│   ├── generate_dataset.py         # Physics-based synthetic corrosion dataset generator
│   ├── model.py                    # Train Transformer + GRU, export best as rul_sequence_model.pt
│   ├── runtime.py                  # Exported-artifact loader (SequenceRULPredictor)
│   └── exported/
│       └── rul_sequence_model.pt   # Pre-trained PyTorch checkpoint (~535 KB)
├── backend/
│   ├── main.py              # FastAPI app, CORS, lifespan, route includes
│   ├── database.py          # SQLite schema, connection, CRUD helpers
│   ├── models.py            # Pydantic request/response schemas
│   ├── inference.py         # Placeholder predictor + build_external_diagnostic helper
│   ├── routes/
│   │   ├── ingest.py        # POST /api/ingest       (raw sensor readings)
│   │   ├── telemetry.py     # POST /api/telemetry    (reading + logger-side predicted RUL)
│   │   ├── readings.py      # GET  /api/readings
│   │   ├── diagnostics.py   # GET  /api/diagnostics
│   │   ├── alerts.py        # GET  /api/alerts
│   │   ├── devices.py       # GET  /api/devices
│   │   └── stats.py         # GET  /api/stats        (S8 evidence)
│   └── simulator.py         # Standalone: generates fake data, POSTs to /api/ingest
├── microelectronics/
│   ├── mega_sensor_sender_wifi/    # Arduino Mega sketch — samples sensors, sends UDP frames
│   ├── esp32_display_wifi_bridge/  # ESP32 sketch — Wi-Fi bridge + local display
│   └── pc_udp_logger/
│       ├── pc_udp_logger.py        # Listens on UDP 5005, runs AI/runtime, POSTs /api/telemetry
│       └── sensor_log.csv          # Rolling CSV log of received frames
├── frontend/
│   ├── src/
│   │   ├── App.jsx
│   │   ├── main.jsx
│   │   ├── components/
│   │   │   ├── GasCards.jsx         # Gas concentration cards with sparklines
│   │   │   ├── EnvironmentCards.jsx # Temp/pressure/humidity/flow cards
│   │   │   ├── DiagnosticsPanel.jsx # AI status, RUL, confidence
│   │   │   ├── RULChart.jsx         # RUL trend over time
│   │   │   ├── HistoryChart.jsx     # Gas time-series, multi-range selector
│   │   │   ├── AlertsPanel.jsx      # Recent alerts
│   │   │   ├── DevicesPanel.jsx     # Connected devices (ESP32 status)
│   │   │   └── SystemStats.jsx      # DB stats surface (S8 evidence)
│   │   ├── hooks/
│   │   │   └── usePolling.js
│   │   └── lib/
│   │       └── api.js
│   ├── index.html
│   ├── vite.config.js
│   ├── tailwind.config.js
│   └── package.json
├── corrosion_monitor.db             # SQLite DB (auto-created on first backend start)
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
    co2 REAL,                   -- ppm
    flow_rate REAL,             -- m³/hr
    temperature REAL,           -- °C
    pressure REAL,              -- bar
    humidity REAL               -- % RH
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
    corrosion_rate REAL,           -- mm/year (derived)
    health_score REAL,             -- 0–100 composite of RUL + corrosion rate
    model_version TEXT DEFAULT 'xgb-v1'  -- e.g. 'sequence-rul-v1' when written by /api/telemetry
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
    condition TEXT,
    acknowledged INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_alerts_ts ON alerts(timestamp);
```

### Table: `devices`
```sql
CREATE TABLE IF NOT EXISTS devices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    type TEXT DEFAULT 'ESP32',
    location TEXT,
    status TEXT DEFAULT 'offline',
    last_seen TEXT,
    ip_address TEXT
);
```

---

## API Endpoints

### `POST /api/ingest`
Receives raw sensor readings from simulator or ESP32. Server-side placeholder inference may produce a diagnostic.

**Request body:**
```json
{
  "h2s": 12.5, "co": 45.2, "ch4": 3.8, "o2": 20.1,
  "co2": 420.0, "flow_rate": 0.77, "temperature": 55.0,
  "pressure": 3.2, "humidity": 48.0,
  "timestamp": "2026-04-18T12:00:00Z"
}
```
`co2`, `flow_rate`, `temperature`, `pressure`, `humidity`, `timestamp` are optional.

**Behavior:**
1. Validate input ranges
2. Insert into `sensor_readings`
3. Optionally trigger inference
4. If inference detects abnormal condition → insert into `diagnostics` and `alerts`
5. Return `{ "status": "ok", "reading_id": 123 }`

### `POST /api/telemetry`
Hardware path: reading **plus a model-predicted RUL** already produced by the PC UDP logger (which runs `AI/exported/rul_sequence_model.pt` locally).

**Request body:**
```json
{
  "reading": { "h2s": 12.5, "co": 45.2, "ch4": 3.8, "o2": 20.1, "co2": 420, "temperature": 55.0, "humidity": 48.0, "timestamp": "2026-04-18T12:00:00Z" },
  "predicted_rul": 1620.4,
  "model_confidence": 0.87,
  "model_version": "sequence-rul-v1"
}
```

**Behavior:**
1. Insert the reading (honoring `reading.timestamp` if provided)
2. Call `inference.build_external_diagnostic` to derive condition, corrosion rate, health score from the predicted RUL + reading
3. Insert the diagnostic with the supplied `model_version`
4. Return `{ "status": "ok", "reading_id": ..., "diagnostic_id": ... }`

### `GET /api/readings`
Query recent sensor data.

**Query params:** `limit` (default 60), `offset` (default 0), `since` (ISO), `until` (ISO).

### `GET /api/diagnostics`
Latest diagnostic + history.

**Query params:** `limit` (default 1).

### `GET /api/alerts`
Recent alerts.

**Query params:** `limit` (default 20), `active_only` (default false).

### `GET /api/devices`
Registered ESP32 / Mega devices and their status.

### `GET /api/stats`  *(S8 evidence)*
Returns DB statistics including `days_of_data` and `spec_s8_met` (true iff ≥ 90 days of retained data). Shape:
```json
{
  "total_readings": ..., "total_diagnostics": ..., "total_alerts": ...,
  "oldest_reading": "...", "newest_reading": "...",
  "days_of_data": 91.2, "db_size_mb": 32.4,
  "spec_s8_met": true,
  "devices_online": 2, "devices_total": 3
}
```

---

## AI Module

### Training (`AI/model.py`)
- Reads `corrosion_dataset_real_rul.csv`, splits train/test by segment id.
- Trains a Transformer and a GRU in parallel, exports the lower-MAE model to `AI/exported/rul_sequence_model.pt`.
- The exported artifact carries: `state_dict`, `model_type`, `model_kwargs`, feature means/stds, raw feature bounds, metrics.

### Inference runtime (`AI/runtime.py`)
- `SequenceRULPredictor` loads `rul_sequence_model.pt` and exposes `predict_remaining_rul(history_rows)`.
- Raw features (what the model actually consumes): `H2S_ppm, CO_ppm, CO2_ppm, CH4_LEL_pct, O2_vol_pct, temperature_C`, plus per-step derivatives.
- Field-mapping is centralized in `RAW_FEATURE_SPECS` so the same code handles CSV columns and live logger field names (e.g. `h2s_ppm` from the Mega → `H2S_ppm` inside the model).

### Dataset generator (`AI/generate_dataset.py`)
- Carbon Steel Sch-40 pipe (ASTM A106 Gr.B), T₀ = 6.02 mm, Tc = 3.0 mm.
- RUL = (T(t) − Tc) / CR, with CR = f(H₂S, pCO₂, O₂, temperature) + 10% noise (simplified de Waard–Milliams + NACE SP0106 inspired).
- Defaults: 10,000 segments × 400 monthly steps ⇒ ~4 M rows (easily satisfies **C8**).

---

## Data Simulator (`backend/simulator.py`)

Generates synthetic sensor readings and POSTs them to the backend.

**Modes:**
1. **Normal** — gases fluctuate within safe ranges with small noise.
2. **Corrosion onset** — H₂S gradually increases, O₂ drops.
3. **Fouling** — CH₄ rises, flow rate decreases.
4. **Leak** — sudden CO spike, pressure drops.

**Usage:**
```bash
python backend/simulator.py --mode normal --interval 1 --url http://localhost:8000
python backend/simulator.py --mode corrosion --interval 1 --duration 3600
python backend/simulator.py --seed-days 90   # Bulk-seed for S8 evidence
```

The `--seed-days` flag is the fastest path to S8 compliance — it bulk-inserts N days of synthetic data so we don't have to wait 90 real days.

---

## Hardware / Microelectronics

End-to-end data flow with real hardware:

```
Arduino Mega ── UDP ──► ESP32 bridge ── UDP ──► PC UDP logger ── HTTP ──► FastAPI /api/telemetry ──► SQLite
 (sensors)                (+ display)            (runs PyTorch model)
```

- `microelectronics/mega_sensor_sender_wifi/mega_sensor_sender_wifi.ino` — Mega reads gas + SCD30 (temp/humidity/CO₂) sensors and emits UDP frames.
- `microelectronics/esp32_display_wifi_bridge/esp32_display_wifi_bridge.ino` — ESP32 relays frames over Wi-Fi and drives a local status display.
- `microelectronics/pc_udp_logger/pc_udp_logger.py` — listens on UDP 5005, writes `sensor_log.csv`, invokes `AI/runtime.py` with a sliding window, and forwards `(reading, predicted_rul)` to `/api/telemetry`.

---

## React Frontend

Single-page dashboard. Current components:

- **GasCards** — H₂S, CO, CO₂, CH₄, O₂ tiles with sparklines, color-coded by severity. Polls `GET /api/readings` every 2 s.
- **EnvironmentCards** — temperature, pressure, humidity, flow rate.
- **DiagnosticsPanel** — AI status badge (Normal / Warning / Critical), RUL, confidence. Polls `GET /api/diagnostics` every 5 s.
- **RULChart** — RUL trend over time.
- **HistoryChart** — multi-series time-series with 1h / 6h / 24h / 7d / 30d range selector. Fetches `GET /api/readings?since=...`.
- **AlertsPanel** — recent alerts, color-coded by severity. Polls `GET /api/alerts`.
- **DevicesPanel** — ESP32 / Mega device list + last-seen status from `GET /api/devices`.
- **SystemStats** — surfaces the `GET /api/stats` S8 evidence (days_of_data, DB size, spec_s8_met).

**Styling**: TailwindCSS, dark theme, monospace font for numerics, status palette (green #22c55e / amber #f59e0b / red #ef4444).

**Polling**: `usePolling(url, intervalMs)` hook under `src/hooks/` handles fetch on mount + interval + cleanup.

---

## Development Commands

```bash
# Backend
pip install -r requirements.txt
cd backend
uvicorn main:app --reload --port 8000

# Seed 90 days of data (S8 proof)
python simulator.py --seed-days 90

# Run live simulator (software-only data path)
python simulator.py --mode normal --interval 1

# Frontend
cd frontend
npm install
npm run dev   # Vite dev server on port 5173

# AI — regenerate the synthetic dataset
python AI/generate_dataset.py

# AI — train + export
cd AI && python model.py --csv corrosion_dataset_real_rul.csv

# Hardware data path
python microelectronics/pc_udp_logger/pc_udp_logger.py
# Listens on UDP 0.0.0.0:5005, appends to sensor_log.csv,
# runs AI/exported/rul_sequence_model.pt, POSTs to /api/telemetry
```

---

## Conventions

- Python: snake_case, type hints on public functions, async where possible.
- React: functional components + hooks only.
- API responses: always JSON, always include a top-level `status` or `data` field.
- Errors: raise FastAPI `HTTPException` with meaningful messages.
- Timestamps: always ISO 8601 UTC (`2026-04-18T12:00:00Z`).
- Modularity: one responsibility per file; self-documenting names over comments.

---

## Important Notes

- `corrosion_monitor.db` is auto-created on first backend start.
- CORS is enabled for `http://localhost:5173` (Vite dev server).
- `simulator.py --seed-days 90` is the fastest path to proving S8.
- If `AI/exported/rul_sequence_model.pt` is missing, the PC UDP logger cannot run inference; use the simulator + `/api/ingest` placeholder for software-only demos.
- `/api/ingest` vs `/api/telemetry`: use `/api/ingest` when the sender has only raw sensors; use `/api/telemetry` when the sender already ran the model (PC logger).
- Specs recap: **C7** RAM ≤ 8 GB · **C8** dataset ≥ 25–30k labeled samples · **S7** MAPE < 20% · **S8** DB ≥ 90 days · **I1** model_acc × sensor_acc ≥ 80%.
