from __future__ import annotations

import argparse
import csv
import json
import os
import socket
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

LISTEN_IP = "0.0.0.0"
LISTEN_PORT = 5005
CSV_FILE = "sensor_log.csv"
DEFAULT_BACKEND_URL = "http://localhost:8000/api/telemetry"
DEFAULT_MODEL_PATH = Path(__file__).resolve().parents[2] / "AI" / "exported" / "rul_sequence_model.pt"

HEADER = [
    "pc_timestamp",
    "packet_type",
    "mega_millis",
    "scd30_ready",
    "scd30_valid",
    "temperature_c",
    "humidity_pct",
    "co2_ppm",
    "gas_valid",
    "o2_pctvol",
    "co_ppm",
    "h2s_ppm",
    "ch4_pctlel",
]


def ensure_repo_root_on_path() -> Path:
    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    return repo_root


def ensure_csv_exists(path: str) -> None:
    if os.path.exists(path):
        return

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(HEADER)


def parse_packet(packet: str) -> Dict[str, Any] | None:
    parts = packet.strip().split(",")
    if len(parts) != 12 or parts[0] != "DATA":
        print(f"Skipping malformed packet: {packet}")
        return None

    row = dict(zip(HEADER[1:], parts))
    parsed = {
        "pc_timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "packet_type": row["packet_type"],
        "mega_millis": int(row["mega_millis"]),
        "scd30_ready": int(row["scd30_ready"]),
        "scd30_valid": int(row["scd30_valid"]),
        "temperature_c": float(row["temperature_c"]),
        "humidity_pct": float(row["humidity_pct"]),
        "co2_ppm": float(row["co2_ppm"]),
        "gas_valid": int(row["gas_valid"]),
        "o2_pctvol": float(row["o2_pctvol"]),
        "co_ppm": float(row["co_ppm"]),
        "h2s_ppm": float(row["h2s_ppm"]),
        "ch4_pctlel": float(row["ch4_pctlel"]),
    }
    return parsed


def append_packet(path: str, parsed_packet: Dict[str, Any]) -> None:
    row = [parsed_packet[h] for h in HEADER]
    with open(path, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(row)
    print("Saved:", row)


def build_backend_payload(
    packet: Dict[str, Any],
    predicted_rul: float,
    model_version: str,
    model_confidence: float,
) -> Dict[str, Any]:
    return {
        "reading": {
            "timestamp": packet["pc_timestamp"],
            "h2s": packet["h2s_ppm"],
            "co": packet["co_ppm"],
            "ch4": packet["ch4_pctlel"],
            "o2": packet["o2_pctvol"],
            "co2": packet["co2_ppm"],
            "temperature": packet["temperature_c"],
            "humidity": packet["humidity_pct"],
            "flow_rate": None,
            "pressure": None,
        },
        "predicted_rul": round(max(0.0, predicted_rul), 1),
        "model_confidence": round(model_confidence, 2),
        "model_version": model_version,
    }


def post_json(url: str, payload: Dict[str, Any]) -> None:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=5) as response:
        body = response.read().decode("utf-8", errors="replace")
        print(f"Backend -> {response.status}: {body}")


def confidence_from_history_length(history_length: int) -> float:
    return min(0.95, 0.55 + min(history_length, 20) * 0.02)


def main() -> None:
    parser = argparse.ArgumentParser(description="Listen for UDP packets, predict RUL, and forward telemetry to backend.")
    parser.add_argument("--listen-ip", default=LISTEN_IP)
    parser.add_argument("--listen-port", type=int, default=LISTEN_PORT)
    parser.add_argument("--csv", default=CSV_FILE)
    parser.add_argument("--backend-url", default=DEFAULT_BACKEND_URL)
    parser.add_argument("--model-path", default=str(DEFAULT_MODEL_PATH))
    args = parser.parse_args()

    repo_root = ensure_repo_root_on_path()
    from AI.runtime import SequenceRULPredictor

    ensure_csv_exists(args.csv)
    predictor = SequenceRULPredictor(args.model_path)
    history: List[Dict[str, Any]] = []

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((args.listen_ip, args.listen_port))

    print(f"Listening on UDP {args.listen_ip}:{args.listen_port}")
    print(f"Writing to {args.csv}")
    print(f"Using exported model: {args.model_path}")
    print(f"Repo root: {repo_root}")
    print(f"Forwarding live tuples to: {args.backend_url}")

    while True:
        data, addr = sock.recvfrom(2048)
        packet = data.decode("utf-8", errors="replace").strip()
        print(f"From {addr[0]}:{addr[1]} -> {packet}")

        parsed = parse_packet(packet)
        if parsed is None:
            continue

        append_packet(args.csv, parsed)
        history.append(parsed)

        try:
            predicted_rul = predictor.predict_remaining_rul(history)
            confidence = confidence_from_history_length(len(history))
            payload = build_backend_payload(
                parsed,
                predicted_rul=predicted_rul,
                model_version=predictor.model_version,
                model_confidence=confidence,
            )
            print(
                "Predicted RUL:",
                payload["predicted_rul"],
                "days | tuple ->",
                (payload["reading"], payload["predicted_rul"]),
            )
            post_json(args.backend_url, payload)
        except FileNotFoundError as exc:
            print(f"Model artifact missing: {exc}")
        except urllib.error.URLError as exc:
            print(f"Backend post failed: {exc}")
        except Exception as exc:
            print(f"Prediction/forwarding failed: {exc}")


if __name__ == "__main__":
    main()
