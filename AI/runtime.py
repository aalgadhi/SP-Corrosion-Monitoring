from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from torch.nn.utils.rnn import pack_padded_sequence, pad_packed_sequence


DEFAULT_EXPORT_PATH = Path(__file__).resolve().parent / "exported" / "rul_sequence_model.pt"


@dataclass(frozen=True)
class RawFeatureSpec:
    model_field: str
    csv_field: str
    logger_field: str
    default: float = 0.0


RAW_FEATURE_SPECS: List[RawFeatureSpec] = [
    RawFeatureSpec("H2S_ppm", "H2S_ppm", "h2s_ppm", 0.0),
    RawFeatureSpec("CO_ppm", "CO_ppm", "co_ppm", 0.0),
    RawFeatureSpec("CO2_ppm", "CO2_ppm", "co2_ppm", 400.0),
    RawFeatureSpec("CH4_LEL_pct", "CH4_LEL_pct", "ch4_pctlel", 0.0),
    RawFeatureSpec("O2_vol_pct", "O2_vol_pct", "o2_pctvol", 20.9),
    RawFeatureSpec("temperature_C", "temperature_C", "temperature_c", 25.0),
]

RAW_FEATURE_COLUMNS = [spec.model_field for spec in RAW_FEATURE_SPECS]
LOGGER_TO_MODEL_FIELD = {spec.logger_field: spec.model_field for spec in RAW_FEATURE_SPECS}
MODEL_TO_LOGGER_FIELD = {spec.model_field: spec.logger_field for spec in RAW_FEATURE_SPECS}


def feature_columns_from_raw(raw_feature_columns: Sequence[str]) -> List[str]:
    raw_cols = list(raw_feature_columns)
    derivative_cols = [f"d_{col}_dt" for col in raw_cols]
    return raw_cols + derivative_cols


def add_derivative_features(
    df: pd.DataFrame,
    time_col: str,
    raw_feature_columns: Sequence[str],
) -> pd.DataFrame:
    df = df.sort_values(time_col).copy()
    dt = df[time_col].diff().replace(0, np.nan).fillna(1.0)
    for col in raw_feature_columns:
        df[f"d_{col}_dt"] = df[col].diff().fillna(0.0) / dt
    return df


class PositionalEncoding(nn.Module):
    def __init__(self, d_model: int, max_len: int = 1000):
        super().__init__()
        pe = torch.zeros(max_len, d_model)
        position = torch.arange(0, max_len, dtype=torch.float).unsqueeze(1)
        div_term = torch.exp(torch.arange(0, d_model, 2).float() * (-np.log(10000.0) / d_model))
        pe[:, 0::2] = torch.sin(position * div_term)
        pe[:, 1::2] = torch.cos(position * div_term)
        self.register_buffer("pe", pe.unsqueeze(0))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return x + self.pe[:, : x.size(1)]


class TransformerRULModel(nn.Module):
    def __init__(
        self,
        input_dim: int,
        d_model: int = 128,
        nhead: int = 8,
        num_layers: int = 3,
        dim_feedforward: int = 256,
        dropout: float = 0.1,
        max_len: int = 1000,
    ):
        super().__init__()
        self.input_projection = nn.Linear(input_dim, d_model)
        self.positional_encoding = PositionalEncoding(d_model=d_model, max_len=max_len)
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=d_model,
            nhead=nhead,
            dim_feedforward=dim_feedforward,
            dropout=dropout,
            batch_first=True,
            activation="gelu",
        )
        self.encoder = nn.TransformerEncoder(encoder_layer, num_layers=num_layers)
        self.regressor = nn.Sequential(
            nn.LayerNorm(d_model),
            nn.Linear(d_model, d_model // 2),
            nn.GELU(),
            nn.Linear(d_model // 2, 1),
        )

    def forward(self, x: torch.Tensor, valid_mask: torch.Tensor | None = None) -> torch.Tensor:
        seq_len = x.size(1)
        causal_mask = torch.triu(
            torch.ones(seq_len, seq_len, device=x.device, dtype=torch.bool), diagonal=1
        )
        key_padding_mask = None
        if valid_mask is not None:
            key_padding_mask = ~valid_mask

        x = self.input_projection(x)
        x = self.positional_encoding(x)
        encoded = self.encoder(x, mask=causal_mask, src_key_padding_mask=key_padding_mask)
        return self.regressor(encoded).squeeze(-1)


class RNNRULModel(nn.Module):
    def __init__(
        self,
        input_dim: int,
        hidden_dim: int = 128,
        num_layers: int = 2,
        dropout: float = 0.1,
    ):
        super().__init__()
        self.rnn = nn.GRU(
            input_size=input_dim,
            hidden_size=hidden_dim,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0.0,
        )
        self.regressor = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.ReLU(),
            nn.Linear(hidden_dim // 2, 1),
        )

    def forward(self, x: torch.Tensor, lengths: torch.Tensor) -> torch.Tensor:
        packed = pack_padded_sequence(x, lengths.cpu(), batch_first=True, enforce_sorted=False)
        packed_output, _ = self.rnn(packed)
        output, _ = pad_packed_sequence(packed_output, batch_first=True, total_length=x.size(1))
        return self.regressor(output).squeeze(-1)


MODEL_REGISTRY = {
    "transformer": TransformerRULModel,
    "rnn": RNNRULModel,
}


def build_model(model_type: str, model_kwargs: Dict[str, Any]) -> nn.Module:
    model_cls = MODEL_REGISTRY[model_type]
    return model_cls(**model_kwargs)


class SequenceRULPredictor:
    def __init__(self, artifact_path: str | Path = DEFAULT_EXPORT_PATH, device: str = "cpu"):
        artifact_path = Path(artifact_path)
        if not artifact_path.exists():
            raise FileNotFoundError(f"Exported model not found: {artifact_path}")

        self.artifact_path = artifact_path
        self.device = torch.device(device)
        self.artifact = torch.load(str(artifact_path), map_location=self.device)
        self.raw_feature_specs = self.artifact["raw_feature_specs"]
        self.raw_feature_columns = self.artifact["raw_feature_columns"]
        self.feature_columns = self.artifact["feature_columns"]
        self.feature_means = self.artifact["feature_means"]
        self.feature_stds = self.artifact["feature_stds"]
        self.raw_feature_bounds = self.artifact["raw_feature_bounds"]
        self.model_type = self.artifact["model_type"]
        self.model_version = self.artifact.get("model_version", self.model_type)

        self.model = build_model(self.model_type, self.artifact["model_kwargs"])
        self.model.load_state_dict(self.artifact["state_dict"])
        self.model.to(self.device)
        self.model.eval()

    def _extract_value(self, row: Dict[str, Any], spec: Dict[str, Any]) -> float:
        logger_key = spec["logger_field"]
        model_key = spec["model_field"]
        default = float(spec.get("default", 0.0))
        raw_value = row.get(logger_key, row.get(model_key, default))
        try:
            value = float(raw_value)
        except (TypeError, ValueError):
            value = default

        bounds = self.raw_feature_bounds.get(model_key)
        if bounds is not None:
            lo, hi = bounds
            value = float(np.clip(value, lo, hi))
        return value

    def _history_to_dataframe(self, history_rows: Sequence[Dict[str, Any]]) -> pd.DataFrame:
        if not history_rows:
            raise ValueError("history_rows must not be empty")

        records: List[Dict[str, float]] = []
        for idx, row in enumerate(history_rows):
            record = {spec["model_field"]: self._extract_value(row, spec) for spec in self.raw_feature_specs}
            record["timestep"] = idx
            records.append(record)

        df = pd.DataFrame.from_records(records)
        df = add_derivative_features(df, time_col="timestep", raw_feature_columns=self.raw_feature_columns)
        return df

    def _build_input_tensor(self, history_rows: Sequence[Dict[str, Any]]) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        df = self._history_to_dataframe(history_rows)
        for col in self.feature_columns:
            mean = float(self.feature_means[col])
            std = float(self.feature_stds[col])
            df[col] = (df[col] - mean) / std

        x_np = df[self.feature_columns].to_numpy(dtype=np.float32)
        xb = torch.from_numpy(x_np).unsqueeze(0).to(self.device)
        lengths = torch.tensor([len(df)], dtype=torch.long, device=self.device)
        valid_mask = torch.ones((1, len(df)), dtype=torch.bool, device=self.device)
        return xb, lengths, valid_mask

    def predict_remaining_rul(self, history_rows: Sequence[Dict[str, Any]]) -> float:
        xb, lengths, valid_mask = self._build_input_tensor(history_rows)
        with torch.no_grad():
            if self.model_type == "transformer":
                preds = self.model(xb, valid_mask=valid_mask)
            else:
                preds = self.model(xb, lengths=lengths)
        latest_pred = float(preds[0, lengths.item() - 1].item())
        return max(0.0, latest_pred)


def build_artifact_payload(
    *,
    model: nn.Module,
    model_type: str,
    model_kwargs: Dict[str, Any],
    feature_columns: Sequence[str],
    feature_means: Dict[str, float],
    feature_stds: Dict[str, float],
    raw_feature_bounds: Dict[str, Sequence[float]],
    metrics: Dict[str, float],
    model_version: str,
) -> Dict[str, Any]:
    return {
        "model_type": model_type,
        "model_kwargs": model_kwargs,
        "state_dict": model.state_dict(),
        "feature_columns": list(feature_columns),
        "feature_means": dict(feature_means),
        "feature_stds": dict(feature_stds),
        "raw_feature_columns": list(RAW_FEATURE_COLUMNS),
        "raw_feature_specs": [asdict(spec) for spec in RAW_FEATURE_SPECS],
        "raw_feature_bounds": {k: [float(v[0]), float(v[1])] for k, v in raw_feature_bounds.items()},
        "metrics": dict(metrics),
        "model_version": model_version,
    }
