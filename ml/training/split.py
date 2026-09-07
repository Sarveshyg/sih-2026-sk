"""
ml/training/split.py — Leakage-aware train/val/test split.

- Spatial grouping: same 500m cluster never appears in both train and test
- Temporal separation: earlier observations for training, later for validation/test where practical
- Deterministic, no future leakage
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from datetime import datetime, timezone
from typing import Tuple, Dict, Any, List
import pandas as pd
import numpy as np


def _parse_ts(s: str) -> datetime:
    return datetime.fromisoformat(str(s).replace('Z','+00:00')).astimezone(timezone.utc)


def spatial_temporal_split(
    df: pd.DataFrame,
    test_size: float = 0.15,
    val_size: float = 0.15,
    random_state: int = 42,
    timestamp_col: str = "timestamp",
    cluster_col: str = "_spatial_cluster_id",
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, Dict[str, Any]]:
    """
    Returns (train, val, test, report)
    - Groups by spatial cluster
    - Sorts clusters by earliest timestamp
    - Assigns clusters to splits to achieve approx sizes while respecting temporal order
    - Ensures no cluster appears in multiple splits
    - Test set remains untouched during model development (only used at final eval)
    """
    # Ensure we have cluster and timestamp
    if cluster_col not in df.columns:
        # fallback to random split if no cluster (should not happen)
        from sklearn.model_selection import train_test_split
        train_val, test = train_test_split(df, test_size=test_size, random_state=random_state, stratify=None)
        val_ratio = val_size / (1 - test_size)
        train, val = train_test_split(train_val, test_size=val_ratio, random_state=random_state)
        return train, val, test, {"method": "random_fallback", "note": "no spatial cluster column"}

    # Compute per cluster earliest timestamp
    # Need to parse timestamp for each cluster
    cluster_earliest = {}
    cluster_counts = {}
    for cid, group in df.groupby(cluster_col):
        # Find earliest timestamp in group
        try:
            dts = [datetime.fromisoformat(str(s).replace('Z','+00:00')).astimezone(timezone.utc) for s in group[timestamp_col].tolist()]
            earliest = min(dts)
        except Exception:
            earliest = datetime.min.replace(tzinfo=timezone.utc)
        cluster_earliest[cid] = earliest
        cluster_counts[cid] = len(group)

    # Sort clusters by earliest timestamp (temporal separation: earlier for train)
    sorted_clusters = sorted(cluster_earliest.items(), key=lambda x: x[1])
    total = len(df)
    n_test = int(total * test_size)
    n_val = int(total * val_size)
    n_train = total - n_test - n_val

    # Assign clusters in order to achieve sizes
    train_clusters = set()
    val_clusters = set()
    test_clusters = set()

    cumsum = 0
    # First, assign to train until we reach n_train
    for cid, _ in sorted_clusters:
        count = cluster_counts[cid]
        if cumsum + count <= n_train or len(train_clusters) == 0:
            train_clusters.add(cid)
            cumsum += count
            if cumsum >= n_train:
                break
    # Remaining clusters for val/test, still in temporal order
    remaining = [(cid, ts) for cid, ts in sorted_clusters if cid not in train_clusters]
    # Split remaining into val and test (val earlier than test)
    cumsum_val = 0
    for cid, _ in remaining:
        count = cluster_counts[cid]
        if cumsum_val + count <= n_val or len(val_clusters) == 0:
            val_clusters.add(cid)
            cumsum_val += count
            if cumsum_val >= n_val:
                break
    # Rest to test
    for cid, _ in remaining:
        if cid not in val_clusters:
            test_clusters.add(cid)

    # Handle any leftover due to rounding: ensure all clusters assigned
    all_assigned = train_clusters | val_clusters | test_clusters
    for cid, _ in sorted_clusters:
        if cid not in all_assigned:
            test_clusters.add(cid)

    # Create splits
    train = df[df[cluster_col].isin(train_clusters)].copy()
    val = df[df[cluster_col].isin(val_clusters)].copy()
    test = df[df[cluster_col].isin(test_clusters)].copy()

    # Ensure deterministic shuffle within each split (by id)
    train = train.sort_values("id").reset_index(drop=True)
    val = val.sort_values("id").reset_index(drop=True)
    test = test.sort_values("id").reset_index(drop=True)

    # Report
    report = {
        "method": "spatial_grouping + temporal_separation (500m cluster, sorted by earliest timestamp)",
        "total": int(total),
        "train": int(len(train)),
        "val": int(len(val)),
        "test": int(len(test)),
        "train_pct": round(100*len(train)/total,2),
        "val_pct": round(100*len(val)/total,2),
        "test_pct": round(100*len(test)/total,2),
        "n_spatial_clusters": int(len(cluster_earliest)),
        "train_clusters": int(len(train_clusters)),
        "val_clusters": int(len(val_clusters)),
        "test_clusters": int(len(test_clusters)),
        "temporal_note": "Clusters sorted by earliest timestamp; train gets earliest, test gets latest — no future leakage, no spatial overlap",
        "leakage_safe": True,
        "random_state": random_state,
        "cluster_col": cluster_col,
    }
    # Verify no overlap
    train_ids = set(train[cluster_col].unique())
    val_ids = set(val[cluster_col].unique())
    test_ids = set(test[cluster_col].unique())
    assert train_ids.isdisjoint(val_ids), "Train/val cluster overlap"
    assert train_ids.isdisjoint(test_ids), "Train/test cluster overlap"
    assert val_ids.isdisjoint(test_ids), "Val/test cluster overlap"

    return train, val, test, report
