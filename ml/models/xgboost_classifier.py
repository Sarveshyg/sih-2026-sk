"""
ml/models/xgboost_classifier.py — XGBoost multiclass classifier for FIRMS.

Supports:
- training
- prediction / predict_proba
- model persistence (json)
- feature importance
- deterministic seed
- integrates with existing feature engineering

Does NOT use BaselineClassifier; kept as separate baseline.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import numpy as np
import pandas as pd

try:
    import xgboost as xgb
except ImportError:
    xgb = None

from ml.schemas import ClassificationLabel

# Class order for consistent encoding
CLASSES = [
    "agricultural_fire",
    "gas_flare",
    "industrial_fire",
    "persistent_industrial_thermal_source",
    "wildfire",
    "unknown",
]
CLASS_TO_IDX = {c: i for i, c in enumerate(CLASSES)}
IDX_TO_CLASS = {i: c for c, i in CLASS_TO_IDX.items()}

# For compatibility, map persistent_industrial_source alias
ALIAS_MAP = {
    "persistent_industrial_source": "persistent_industrial_thermal_source",
}

def _encode_label(label: str) -> int:
    label = ALIAS_MAP.get(label, label)
    return CLASS_TO_IDX.get(label, CLASS_TO_IDX["unknown"])

def _decode_label(idx: int) -> str:
    return IDX_TO_CLASS.get(idx, "unknown")

# Feature set for XGBoost (numeric + encoded categorical)
# Keep consistent with dataset.py feature_cols
DEFAULT_FEATURES = [
    "latitude","longitude","frp","brightness_temperature","confidence",
    "hour_utc","day_of_week","month",
    "detections_24h","detections_7d","detections_30d","persistence","hotspot_cluster_size",
    "facility_baseline","facility_current_activity","facility_anomaly",
    "_cluster_size_500","_distinct_dates","_span_days",
]
CATEGORICAL_FEATURES = ["satellite","daynight"]

class XGBoostClassifier:
    def __init__(
        self,
        n_estimators: int = 200,
        max_depth: int = 6,
        learning_rate: float = 0.1,
        subsample: float = 0.8,
        colsample_bytree: float = 0.8,
        random_state: int = 42,
        n_jobs: int = 4,
        class_weight: Optional[str] = None,  # 'balanced' or None
    ):
        if xgb is None:
            raise ImportError("xgboost not installed (pip install xgboost)")
        self.n_estimators = n_estimators
        self.max_depth = max_depth
        self.learning_rate = learning_rate
        self.subsample = subsample
        self.colsample_bytree = colsample_bytree
        self.random_state = random_state
        self.n_jobs = n_jobs
        self.class_weight = class_weight
        self.model: Optional[xgb.XGBClassifier] = None
        self.feature_names: List[str] = []
        self.label_encoder: Dict[str, int] = CLASS_TO_IDX
        self.is_fitted = False

    def _prepare_features(self, df: pd.DataFrame, fit: bool = False) -> pd.DataFrame:
        # Select numeric features
        feature_cols = [c for c in DEFAULT_FEATURES if c in df.columns]
        X = df[feature_cols].copy()
        # Fill missing with median (for prototype)
        for col in X.columns:
            if X[col].isna().any():
                median = X[col].median() if fit else 0
                X[col] = X[col].fillna(median)
        # Encode categorical
        for cat in CATEGORICAL_FEATURES:
            if cat in df.columns:
                # Simple label encoding
                vals = df[cat].astype(str).fillna("unknown")
                # Use pandas factorize for deterministic mapping
                # For prototype, use one-hot via get_dummies but keep simple: label encode
                # Create mapping based on sorted unique
                uniq = sorted(vals.unique())
                mapping = {v: i for i, v in enumerate(uniq)}
                X[cat] = vals.map(mapping)
        # Ensure feature order
        self.feature_names = X.columns.tolist() if fit or not self.feature_names else self.feature_names
        # Align columns if needed
        if not fit and self.feature_names:
            for col in self.feature_names:
                if col not in X.columns:
                    X[col] = 0
            X = X[self.feature_names]
        return X

    def fit(self, df: pd.DataFrame, label_col: str = "weak_label") -> Dict[str, Any]:
        df_train = df.copy()
        # Encode labels
        y_raw = df_train[label_col].apply(lambda x: _encode_label(str(x))).values
        X = self._prepare_features(df_train, fit=True)

        # Handle case where not all 6 classes are present in training data
        # Map present labels to contiguous 0..n_classes-1 for XGBoost, then remap at predict
        unique_labels = np.unique(y_raw)
        # Create mapping from original encoded label to contiguous index
        # e.g., if present are {0,3} -> map 0->0, 3->1
        self._label_mapping = {orig: idx for idx, orig in enumerate(sorted(unique_labels))}
        self._inverse_mapping = {idx: orig for orig, idx in self._label_mapping.items()}
        self._present_classes = sorted(unique_labels)
        self._n_present = len(unique_labels)
        y = np.array([self._label_mapping[v] for v in y_raw])

        # Handle class imbalance via sample_weight if requested
        sample_weight = None
        if self.class_weight == "balanced":
            from sklearn.utils.class_weight import compute_sample_weight
            sample_weight = compute_sample_weight(class_weight="balanced", y=y)

        self.model = xgb.XGBClassifier(
            n_estimators=self.n_estimators,
            max_depth=self.max_depth,
            learning_rate=self.learning_rate,
            subsample=self.subsample,
            colsample_bytree=self.colsample_bytree,
            random_state=self.random_state,
            n_jobs=self.n_jobs,
            objective="multi:softprob",
            eval_metric="mlogloss",
            num_class=self._n_present,
            use_label_encoder=False,
        )
        self.model.fit(X, y, sample_weight=sample_weight, verbose=False)
        self.is_fitted = True
        # Compute feature importance
        importance = dict(zip(self.feature_names, self.model.feature_importances_.tolist()))
        # Sort
        sorted_imp = dict(sorted(importance.items(), key=lambda x: x[1], reverse=True))
        return {"feature_importance": sorted_imp, "n_samples": len(df_train), "feature_names": self.feature_names}

    def predict(self, df: pd.DataFrame) -> List[str]:
        if not self.is_fitted or self.model is None:
            raise RuntimeError("Model not fitted")
        X = self._prepare_features(df, fit=False)
        # Use predict_proba and argmax to get class labels (handles multi:softprob)
        proba = self.model.predict_proba(X)
        # proba is (n, n_present)
        preds_contiguous = np.argmax(proba, axis=1)
        preds_original = [self._inverse_mapping[int(p)] for p in preds_contiguous]
        return [_decode_label(int(p)) for p in preds_original]

    def predict_proba(self, df: pd.DataFrame) -> np.ndarray:
        if not self.is_fitted or self.model is None:
            raise RuntimeError("Model not fitted")
        X = self._prepare_features(df, fit=False)
        proba_contiguous = self.model.predict_proba(X)
        # Expand to 6 classes (fill missing with 0)
        n = proba_contiguous.shape[0]
        proba_full = np.zeros((n, len(CLASSES)))
        for cont_idx, orig_idx in self._inverse_mapping.items():
            proba_full[:, orig_idx] = proba_contiguous[:, cont_idx]
        # Normalize rows to sum to 1 (in case of missing classes, they get 0)
        # For rows where some classes missing, the sum of present probas is 1, so full sum is 1
        return proba_full

    def predict_with_proba(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        proba = self.predict_proba(df)
        preds = self.predict(df)
        results = []
        for i, pred in enumerate(preds):
            probs = {CLASSES[j]: float(proba[i, j]) for j in range(len(CLASSES))}
            results.append({"predicted_class": pred, "probabilities": probs, "max_prob": float(np.max(proba[i]))})
        return results

    def save(self, path: Path | str):
        if not self.is_fitted or self.model is None:
            raise RuntimeError("Model not fitted, cannot save")
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.model.save_model(str(path))
        # Also save metadata — ensure JSON serializable (convert numpy ints)
        def _to_py(v):
            if isinstance(v, (np.integer,)):
                return int(v)
            if isinstance(v, dict):
                return {str(k): _to_py(val) for k, val in v.items()}
            if isinstance(v, list):
                return [_to_py(x) for x in v]
            return v
        meta = {
            "feature_names": self.feature_names,
            "classes": CLASSES,
            "present_classes": _to_py(getattr(self, "_present_classes", [])),
            "label_mapping": _to_py(getattr(self, "_label_mapping", {})),
            "inverse_mapping": _to_py(getattr(self, "_inverse_mapping", {})),
            "params": {
                "n_estimators": self.n_estimators,
                "max_depth": self.max_depth,
                "learning_rate": self.learning_rate,
                "random_state": self.random_state,
            }
        }
        meta_path = path.with_suffix(".meta.json")
        meta_path.write_text(json.dumps(meta, indent=2))

    def load(self, path: Path | str):
        if xgb is None:
            raise ImportError("xgboost not installed")
        path = Path(path)
        self.model = xgb.XGBClassifier()
        self.model.load_model(str(path))
        # Load meta if exists
        meta_path = path.with_suffix(".meta.json")
        if meta_path.exists():
            meta = json.loads(meta_path.read_text())
            self.feature_names = meta.get("feature_names", [])
            self._present_classes = meta.get("present_classes", [])
            # Keys are strings in JSON, convert back to int
            self._label_mapping = {int(k): int(v) for k, v in meta.get("label_mapping", {}).items()}
            self._inverse_mapping = {int(k): int(v) for k, v in meta.get("inverse_mapping", {}).items()}
            self._n_present = len(self._present_classes)
        else:
            # Fallback: assume all classes
            self._present_classes = list(range(len(CLASSES)))
            self._label_mapping = {i: i for i in range(len(CLASSES))}
            self._inverse_mapping = {i: i for i in range(len(CLASSES))}
            self._n_present = len(CLASSES)
        self.is_fitted = True
        return self

    def feature_importance(self) -> Dict[str, float]:
        if not self.is_fitted or self.model is None:
            return {}
        return dict(zip(self.feature_names, self.model.feature_importances_.tolist()))
