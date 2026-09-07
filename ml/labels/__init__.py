"""ml.labels — Weak supervision for FIRMS classification (prototype, not ground truth)"""
from .weak_labels import WeakLabeler, WeakLabelResult
from .label_rules import RULES

__all__ = ["WeakLabeler", "WeakLabelResult", "RULES"]
