import argparse
import math
import random
from dataclasses import dataclass
from typing import Dict, List, Sequence, Tuple

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from torch.nn.utils.rnn import pack_padded_sequence, pad_packed_sequence
from torch.utils.data import DataLoader, Dataset


# -----------------------------------------------------------------------------
# Reproducibility
# -----------------------------------------------------------------------------

def set_seed(seed: int = 42) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)


# -----------------------------------------------------------------------------
# Feature engineering
# -----------------------------------------------------------------------------
@dataclass
class PreparedData:
    train_x: List[np.ndarray]
    train_y: List[np.ndarray]
    test_x: List[np.ndarray]
    test_y: List[np.ndarray]
    feature_columns: List[str]
    train_segment_ids: List[int]
    test_segment_ids: List[int]


def add_derivative_features(df: pd.DataFrame, time_col: str, exclude_cols: List[str]) -> Tuple[pd.DataFrame, List[str]]:
    """
    Add d(feature)/dt for every candidate feature grouped by segment.

    Important note:
    We intentionally do NOT create a derivative of RUL_days, because RUL_days is the
    prediction target and doing so would leak target information into the inputs.
    """
    df = df.sort_values(["segment_id", time_col]).copy()
    candidate_cols = [
        col for col in df.columns
        if col not in set(exclude_cols + ["RUL_days"])
    ]

    dt = df.groupby("segment_id")[time_col].diff().replace(0, np.nan)
    dt = dt.fillna(1.0)

    derivative_cols = []
    for col in candidate_cols:
        deriv_col = f"d_{col}_dt"
        df[deriv_col] = df.groupby("segment_id")[col].diff().fillna(0.0) / dt
        derivative_cols.append(deriv_col)

    return df, derivative_cols


def split_by_segment(df: pd.DataFrame, train_ratio: float = 0.7, seed: int = 42) -> Tuple[List[int], List[int]]:
    segment_ids = sorted(df["segment_id"].unique().tolist())
    rng = np.random.default_rng(seed)
    shuffled = np.array(segment_ids)
    rng.shuffle(shuffled)

    split_idx = int(len(shuffled) * train_ratio)
    train_ids = sorted(shuffled[:split_idx].tolist())
    test_ids = sorted(shuffled[split_idx:].tolist())
    return train_ids, test_ids


def standardize_from_train(train_df: pd.DataFrame, test_df: pd.DataFrame, feature_cols: List[str], ) -> Tuple[pd.DataFrame, pd.DataFrame]:
    means = train_df[feature_cols].mean()
    stds = train_df[feature_cols].std().replace(0, 1.0)

    train_df = train_df.copy()
    test_df = test_df.copy()

    train_df[feature_cols] = (train_df[feature_cols] - means) / stds
    test_df[feature_cols] = (test_df[feature_cols] - means) / stds
    return train_df, test_df


def dataframe_to_segment_tensors(df: pd.DataFrame, feature_cols: List[str], time_col: str,) -> Tuple[List[np.ndarray], List[np.ndarray], List[int]]:
    grouped: List[np.ndarray] = []
    targets: List[np.ndarray] = []
    segment_ids: List[int] = []

    for seg_id, group in df.groupby("segment_id", sort=True):
        group = group.sort_values(time_col)
        x_seg = group[feature_cols].to_numpy(dtype=np.float32)
        y_seg = group["RUL_days"].to_numpy(dtype=np.float32)
        if len(x_seg) == 0:
            continue
        grouped.append(x_seg)
        targets.append(y_seg)
        segment_ids.append(int(seg_id))

    return grouped, targets, segment_ids


def prepare_data(csv_path: str, seed: int = 42) -> PreparedData:
    df = pd.read_csv(csv_path)

    time_col = "timestep_month" if "timestep_month" in df.columns else "timestep"
    exclude_for_derivative = ["segment_id", time_col, "Corrosion_Rate_mm_per_year", "Corrosion_Rate_mm_per_day"]
    df, derivative_cols = add_derivative_features(df, time_col, exclude_for_derivative)

    base_feature_cols = [
        col for col in df.columns
        if col not in {"segment_id", time_col, "RUL_days"}
    ]
    feature_cols = [col for col in base_feature_cols if col != "RUL_days"]

    train_ids, test_ids = split_by_segment(df, train_ratio=0.7, seed=seed)
    train_df = df[df["segment_id"].isin(train_ids)].copy()
    test_df = df[df["segment_id"].isin(test_ids)].copy()

    train_df, test_df = standardize_from_train(train_df, test_df, feature_cols)

    train_x, train_y, train_segments = dataframe_to_segment_tensors(train_df, feature_cols, time_col)
    test_x, test_y, test_segments = dataframe_to_segment_tensors(test_df, feature_cols, time_col)

    train_lengths = [len(x) for x in train_x]
    test_lengths = [len(x) for x in test_x]

    print(f"Loaded data from: {csv_path}")
    print(f"Total rows: {len(df):,}")
    print(f"Total segments: {df['segment_id'].nunique()}")
    print(f"Train segments: {len(train_ids)} | Test segments: {len(test_ids)}")
    print(f"Original feature count (excluding target/time/id): {len(base_feature_cols) - len(derivative_cols)}")
    print(f"Derivative features added: {len(derivative_cols)}")
    print(f"Final feature count: {len(feature_cols)}")
    print(
        "Train length range: "
        f"min={min(train_lengths) if train_lengths else 0}, "
        f"max={max(train_lengths) if train_lengths else 0}"
    )
    print(
        "Test length range: "
        f"min={min(test_lengths) if test_lengths else 0}, "
        f"max={max(test_lengths) if test_lengths else 0}"
    )

    return PreparedData(
        train_x=train_x,
        train_y=train_y,
        test_x=test_x,
        test_y=test_y,
        feature_columns=feature_cols,
        train_segment_ids=train_segments,
        test_segment_ids=test_segments,
    )


# -----------------------------------------------------------------------------
# Datasets
# -----------------------------------------------------------------------------
class SegmentSequenceDataset(Dataset):
    def __init__(self, x: Sequence[np.ndarray], y: Sequence[np.ndarray]):
        self.x = list(x)
        self.y = list(y)

    def __len__(self) -> int:
        return len(self.x)

    def __getitem__(self, idx: int):
        return self.x[idx], self.y[idx]


def collate_variable_length_batch(batch):
    xs, ys = zip(*batch)
    batch_size = len(xs)
    lengths = torch.tensor([len(x) for x in xs], dtype=torch.long)
    max_len = int(lengths.max().item())
    feature_dim = xs[0].shape[1]

    padded_x = torch.zeros(batch_size, max_len, feature_dim, dtype=torch.float32)
    padded_y = torch.zeros(batch_size, max_len, dtype=torch.float32)
    valid_mask = torch.zeros(batch_size, max_len, dtype=torch.bool)

    for i, (x, y) in enumerate(zip(xs, ys)):
        seq_len = len(x)
        padded_x[i, :seq_len] = torch.from_numpy(x)
        padded_y[i, :seq_len] = torch.from_numpy(y)
        valid_mask[i, :seq_len] = True

    return padded_x, padded_y, lengths, valid_mask


# -----------------------------------------------------------------------------
# Models
# -----------------------------------------------------------------------------
class PositionalEncoding(nn.Module):
    def __init__(self, d_model: int, max_len: int = 1000):
        super().__init__()
        pe = torch.zeros(max_len, d_model)
        position = torch.arange(0, max_len, dtype=torch.float).unsqueeze(1)
        div_term = torch.exp(torch.arange(0, d_model, 2).float() * (-math.log(10000.0) / d_model))
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


# -----------------------------------------------------------------------------
# Training / evaluation
# -----------------------------------------------------------------------------

def masked_mae_loss(preds: torch.Tensor, targets: torch.Tensor, valid_mask: torch.Tensor) -> torch.Tensor:
    abs_err = torch.abs(preds - targets)
    masked_err = abs_err[valid_mask]
    return masked_err.mean()


def compute_metrics(preds: np.ndarray, targets: np.ndarray, threshold_days: float = 180.0) -> Dict[str, float]:
    abs_err = np.abs(preds - targets)
    mae = float(abs_err.mean())

    correct = int((abs_err <= threshold_days).sum())
    incorrect = int((abs_err > threshold_days).sum())
    accuracy = correct / (correct + incorrect + 1e-8)
    return {
        "mae": mae,
        "accuracy": accuracy,
        "correct_predictions": correct,
        "incorrect_predictions": incorrect,
    }


def model_predict(model: nn.Module, xb: torch.Tensor, lengths: torch.Tensor, valid_mask: torch.Tensor) -> torch.Tensor:
    if isinstance(model, TransformerRULModel):
        return model(xb, valid_mask=valid_mask)
    return model(xb, lengths=lengths)


def train_one_model(
    model: nn.Module,
    train_loader: DataLoader,
    test_loader: DataLoader,
    device: torch.device,
    epochs: int,
    lr: float,
    accuracy_threshold: float,
    model_name: str,
) -> Dict[str, float]:
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)

    model.to(device)

    for epoch in range(1, epochs + 1):
        model.train()
        train_loss = 0.0
        total_valid_steps = 0

        for xb, yb, lengths, valid_mask in train_loader:
            xb = xb.to(device)
            yb = yb.to(device)
            lengths = lengths.to(device)
            valid_mask = valid_mask.to(device)

            optimizer.zero_grad()
            preds = model_predict(model, xb, lengths, valid_mask)
            loss = masked_mae_loss(preds, yb, valid_mask)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            optimizer.step()

            valid_items = int(valid_mask.sum().item())
            train_loss += loss.item() * valid_items
            total_valid_steps += valid_items

        avg_train_loss = train_loss / max(total_valid_steps, 1)
        print(f"[{model_name}] Epoch {epoch:02d}/{epochs} | Train MAE Loss: {avg_train_loss:.4f}")

    model.eval()
    all_preds = []
    all_targets = []

    with torch.no_grad():
        for xb, yb, lengths, valid_mask in test_loader:
            xb = xb.to(device)
            lengths = lengths.to(device)
            valid_mask = valid_mask.to(device)
            preds = model_predict(model, xb, lengths, valid_mask).cpu()

            all_preds.append(preds[valid_mask.cpu()].numpy())
            all_targets.append(yb[valid_mask.cpu()].numpy())

    preds = np.concatenate(all_preds, axis=0).reshape(-1)
    targets = np.concatenate(all_targets, axis=0).reshape(-1)
    metrics = compute_metrics(preds, targets, threshold_days=accuracy_threshold)

    print(
        f"[{model_name}] Test MAE: {metrics['mae']:.4f} | "
        f"Accuracy@{accuracy_threshold:.0f}d: {metrics['accuracy']:.4f} | "
        f"Correct: {metrics['correct_predictions']} | Incorrect: {metrics['incorrect_predictions']}"
    )
    return metrics


# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Train Transformer and RNN models for corrosion RUL prediction.")
    parser.add_argument("--csv", type=str, default="corrosion_dataset_real_rul.csv", help="Path to dataset CSV")
    parser.add_argument("--epochs", type=int, default=8, help="Number of training epochs per model")
    parser.add_argument("--batch-size", type=int, default=32, help="Batch size (segments per batch)")
    parser.add_argument("--lr", type=float, default=1e-3, help="Learning rate")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--accuracy-threshold", type=float, default=180.0, help="Threshold in days for custom accuracy")
    parser.add_argument("--device", type=str, default="cuda" if torch.cuda.is_available() else "cpu")
    args = parser.parse_args()

    set_seed(args.seed)
    device = torch.device(args.device)
    print(f"Using device: {device}")

    prepared = prepare_data(args.csv, seed=args.seed)

    train_dataset = SegmentSequenceDataset(prepared.train_x, prepared.train_y)
    test_dataset = SegmentSequenceDataset(prepared.test_x, prepared.test_y)

    train_loader = DataLoader(
        train_dataset,
        batch_size=args.batch_size,
        shuffle=True,
        collate_fn=collate_variable_length_batch,
    )
    test_loader = DataLoader(
        test_dataset,
        batch_size=args.batch_size,
        shuffle=False,
        collate_fn=collate_variable_length_batch,
    )

    input_dim = prepared.train_x[0].shape[-1]
    max_seq_len = max(max(len(x) for x in prepared.train_x), max(len(x) for x in prepared.test_x))

    transformer = TransformerRULModel(input_dim=input_dim, max_len=max_seq_len)
    rnn = RNNRULModel(input_dim=input_dim)

    print("\nTraining Transformer model...")
    transformer_metrics = train_one_model(
        model=transformer,
        train_loader=train_loader,
        test_loader=test_loader,
        device=device,
        epochs=args.epochs,
        lr=args.lr,
        accuracy_threshold=args.accuracy_threshold,
        model_name="Transformer",
    )

    print("\nTraining RNN model...")
    rnn_metrics = train_one_model(
        model=rnn,
        train_loader=train_loader,
        test_loader=test_loader,
        device=device,
        epochs=args.epochs,
        lr=args.lr,
        accuracy_threshold=args.accuracy_threshold,
        model_name="RNN-GRU",
    )

    print("\n" + "=" * 72)
    print("Final Test Results")
    print("=" * 72)
    print(
        f"Transformer | MAE: {transformer_metrics['mae']:.4f} | "
        f"Accuracy@{args.accuracy_threshold:.0f}d: {transformer_metrics['accuracy']:.4f}"
    )
    print(
        f"RNN-GRU     | MAE: {rnn_metrics['mae']:.4f} | "
        f"Accuracy@{args.accuracy_threshold:.0f}d: {rnn_metrics['accuracy']:.4f}"
    )


if __name__ == "__main__":
    main()
