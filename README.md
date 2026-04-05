# Corrosion Gas Monitor

Real-time dashboard for monitoring corrosion-related gases (H₂S, CO, CO₂ CH₄, O₂) in refinery piping systems. Uses an time-series AI models for pipeline condition classification and Remaining Useful Life (RUL) estimation.

**KFUPM Senior Design Project — Team M056, Term 252**

## Quick Start

### Backend
```bash
cd backend
pip install -r ../requirements.txt
uvicorn main:app --reload --port 8000
```

### Seed Data (for S8 compliance proof)
```bash
python backend/simulator.py --seed-days 10
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

Dashboard runs at `http://localhost:5173`, API at `http://localhost:8000`.

## Architecture

- **Backend**: FastAPI + SQLite (async) + XGBoost inference
- **Frontend**: React + Vite + Recharts + TailwindCSS
- **Simulator**: Generates realistic sensor data for testing/demo
