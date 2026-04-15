from __future__ import annotations

import argparse
import json
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, Dataset

from runtime import (
    DEFAULT_EXPORT_PATH,
    RAW_FEATURE_COLUMNS,
    RNNRULModel,
    TransformerRULModel,
    add_derivative_features,
    build_artifact_payload,
    feature_columns_from_raw,
)


def set_seed(seed: int = 42) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)


@dataclass
class PreparedData:
    train_x: List[np.ndarray]
    train_y: List[np.ndarray]
    test_x: List[np.ndarray]
    test_y: List[np.ndarray]
    feature_columns: List[str]
    train_segment_ids: List[int]
    test_segment_ids: List[int]
    feature_means: Dict[str, float]
    feature_stds: Dict[str, float]
    raw_feature_bounds: Dict[str, Tuple[float, float]]


def split_by_segment(df: pd.DataFrame, train_ratio: float = 0.7, seed: int = 42) -> Tuple[List[int], List[int]]:
    segment_ids = sorted(df["segment_id"].unique().tolist())
    rng = np.random.default_rng(seed)
    shuffled = np.array(segment_ids)
    rng.shuffle(shuffled)

    split_idx = int(len(shuffled) * train_ratio)
    train_ids = sorted(shuffled[:split_idx].tolist())
    test_ids = sorted(shuffled[split_idx:].tolist())
    return train_ids, test_ids


def standardize_from_train(
    train_df: pd.DataFrame,
    test_df: pd.DataFrame,
    feature_cols: List[str],
) -> Tuple[pd.DataFrame, pd.DataFrame, Dict[str, float], Dict[str, float]]:
    means = train_df[feature_cols].mean()
    stds = train_df[feature_cols].std().replace(0, 1.0).fillna(1.0)

    train_df = train_df.copy()
    test_df = test_df.copy()

    train_df[feature_cols] = (train_df[feature_cols] - means) / stds
    test_df[feature_cols] = (test_df[feature_cols] - means) / stds
    return train_df, test_df, means.to_dict(), stds.to_dict()


def dataframe_to_segment_tensors(
    df: pd.DataFrame,
    feature_cols: List[str],
    time_col: str,
) -> Tuple[List[np.ndarray], List[np.ndarray], List[int]]:
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

    required_cols = {"segment_id", time_col, "RUL_days", *RAW_FEATURE_COLUMNS}
    missing = sorted(required_cols.difference(df.columns))
    if missing:
        raise ValueError(f"Dataset is missing required columns for exportable live inference: {missing}")

    df = df[["segment_id", time_col, *RAW_FEATURE_COLUMNS, "RUL_days"]].copy()
    df = df.sort_values(["segment_id", time_col]).copy()

    grouped_frames = []
    for _, group in df.groupby("segment_id", sort=True):
        group = add_derivative_features(group, time_col=time_col, raw_feature_columns=RAW_FEATURE_COLUMNS)
        grouped_frames.append(group)
    df = pd.concat(grouped_frames, ignore_index=True)

    feature_cols = feature_columns_from_raw(RAW_FEATURE_COLUMNS)

    train_ids, test_ids = split_by_segment(df, train_ratio=0.7, seed=seed)
    train_df = df[df["segment_id"].isin(train_ids)].copy()
    test_df = df[df["segment_id"].isin(test_ids)].copy()

    raw_feature_bounds = {
        col: (float(train_df[col].min()), float(train_df[col].max())) for col in RAW_FEATURE_COLUMNS
    }

    train_df, test_df, feature_means, feature_stds = standardize_from_train(train_df, test_df, feature_cols)

    train_x, train_y, train_segments = dataframe_to_segment_tensors(train_df, feature_cols, time_col)
    test_x, test_y, test_segments = dataframe_to_segment_tensors(test_df, feature_cols, time_col)

    train_lengths = [len(x) for x in train_x]
    test_lengths = [len(x) for x in test_x]

    print(f"Loaded data from: {csv_path}")
    print(f"Total rows: {len(df):,}")
    print(f"Total segments: {df['segment_id'].nunique()}")
    print(f"Train segments: {len(train_ids)} | Test segments: {len(test_ids)}")
    print(f"Live raw feature count: {len(RAW_FEATURE_COLUMNS)}")
    print(f"Derivative features added: {len(feature_cols) - len(RAW_FEATURE_COLUMNS)}")
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
        feature_means=feature_means,
        feature_stds=feature_stds,
        raw_feature_bounds=raw_feature_bounds,
    )


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


def export_model_artifact(
    export_path: str | Path,
    *,
    model: nn.Module,
    model_type: str,
    model_kwargs: Dict[str, int | float],
    prepared: PreparedData,
    metrics: Dict[str, float],
) -> Path:
    export_path = Path(export_path)
    export_path.parent.mkdir(parents=True, exist_ok=True)
    model_cpu = model.to("cpu")
    artifact = build_artifact_payload(
        model=model_cpu,
        model_type=model_type,
        model_kwargs=model_kwargs,
        feature_columns=prepared.feature_columns,
        feature_means=prepared.feature_means,
        feature_stds=prepared.feature_stds,
        raw_feature_bounds=prepared.raw_feature_bounds,
        metrics=metrics,
        model_version=f"{model_type}-rul-seq-v1",
    )
    torch.save(artifact, str(export_path))

    metadata_path = export_path.with_suffix(".json")
    human_metadata = {
        "model_type": artifact["model_type"],
        "model_kwargs": artifact["model_kwargs"],
        "feature_columns": artifact["feature_columns"],
        "raw_feature_columns": artifact["raw_feature_columns"],
        "raw_feature_specs": artifact["raw_feature_specs"],
        "raw_feature_bounds": artifact["raw_feature_bounds"],
        "metrics": artifact["metrics"],
        "model_version": artifact["model_version"],
    }
    metadata_path.write_text(json.dumps(human_metadata, indent=2), encoding="utf-8")
    print(f"Exported model artifact: {export_path}")
    print(f"Exported metadata: {metadata_path}")
    return export_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Train and export sequence models for corrosion RUL prediction.")
    parser.add_argument("--csv", type=str, default="corrosion_dataset_real_rul.csv", help="Path to dataset CSV")
    parser.add_argument("--epochs", type=int, default=32, help="Number of training epochs per model")
    parser.add_argument("--batch-size", type=int, default=16, help="Batch size (segments per batch)")
    parser.add_argument("--lr", type=float, default=1e-3, help="Learning rate")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--accuracy-threshold", type=float, default=365.25, help="Threshold in days for custom accuracy")
    parser.add_argument("--device", type=str, default="cuda" if torch.cuda.is_available() else "cpu")
    parser.add_argument("--export-path", type=str, default=str(DEFAULT_EXPORT_PATH), help="Where to save the exported model artifact")
    parser.add_argument("--export-model", choices=["best", "transformer", "rnn"], default="best", help="Which trained model to export")
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

    transformer_kwargs = {
        "input_dim": input_dim,
        "d_model": 64,
        "nhead": 4,
        "num_layers": 3,
        "dim_feedforward": 128,
        "dropout": 0.2,
        "max_len": max_seq_len,
    }
    rnn_kwargs = {
        "input_dim": input_dim,
        "hidden_dim": 128,
        "num_layers": 3,
        "dropout": 0.1,
    }

    transformer = TransformerRULModel(**transformer_kwargs)
    rnn = RNNRULModel(**rnn_kwargs)

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

    candidates = {
        "transformer": (transformer, transformer_kwargs, transformer_metrics),
        "rnn": (rnn, rnn_kwargs, rnn_metrics),
    }
    if args.export_model == "best":
        selected_name = min(candidates, key=lambda name: candidates[name][2]["mae"])
    else:
        selected_name = args.export_model

    selected_model, selected_kwargs, selected_metrics = candidates[selected_name]
    export_model_artifact(
        args.export_path,
        model=selected_model,
        model_type=selected_name,
        model_kwargs=selected_kwargs,
        prepared=prepared,
        metrics=selected_metrics,
    )


if __name__ == "__main__":
    main()
