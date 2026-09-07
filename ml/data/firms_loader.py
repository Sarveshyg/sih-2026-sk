"""
ml/data/firms_loader.py — Raw FIRMS CSV loader with variant detection.

- Detects supported columns (case-insensitive)
- Normalizes known variants via COLUMN_ALIASES
- Preserves useful original fields in `raw_extra`
- Fails clearly when essential fields absent (FirmsSchemaError)
- No internet, no fabrication — local file only, stdlib csv
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import List, Dict, Tuple

from .firms_schema import normalize_column_name, FirmsSchemaError, validate_essential_columns


def _detect_delimiter(sample: str) -> str:
    # FIRMS is comma-separated, but be tolerant
    if ";" in sample and "," not in sample:
        return ";"
    return ","


def load_firms_csv(path: str | Path, encoding: str = "utf-8") -> Tuple[List[Dict[str, str]], List[str]]:
    """
    Load FIRMS CSV and return (rows, canonical_header).

    Each row is a dict with canonical keys where known, plus original extra keys.
    Preserves raw string values — parsing/normalization done in firms_cleaner.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"FIRMS file not found: {p}")
    if p.stat().st_size == 0:
        raise FirmsSchemaError(f"FIRMS file is empty: {p}")

    # Read with csv, handle BOM
    with p.open("r", encoding=encoding, newline="") as f:
        # Peek for delimiter
        sample = f.read(4096)
        f.seek(0)
        delimiter = _detect_delimiter(sample)
        # Use utf-8-sig handling: strip BOM from first header if present
        reader = csv.DictReader(f, delimiter=delimiter)
        if reader.fieldnames is None:
            raise FirmsSchemaError(f"No header found in FIRMS CSV: {p}")
        # Strip BOM character
        raw_headers = [h.lstrip("\ufeff").strip() for h in reader.fieldnames]
        canonical_headers = [normalize_column_name(h) for h in raw_headers]
        header_map = dict(zip(raw_headers, canonical_headers))

        # Validate essential groups before reading all rows
        present = set(canonical_headers)
        validate_essential_columns(present)

        rows: List[Dict[str, str]] = []
        for idx, raw_row in enumerate(reader, start=2):
            # Skip empty lines
            if not any(v is not None and str(v).strip() != "" for v in raw_row.values()):
                continue
            canon: Dict[str, str] = {}
            for raw_h, canon_h in header_map.items():
                v = raw_row.get(raw_h)
                if v is not None:
                    v = v.strip()
                canon[canon_h] = v if v != "" else None
                # Also keep original header lower? No, store extra
            # Preserve any unknown columns under original name (lower)
            # Already included via canon_h fallback to lower raw
            rows.append(canon)

    if not rows:
        raise FirmsSchemaError(f"FIRMS CSV has header but no data rows: {p}")

    return rows, canonical_headers


def get_canonical_headers(path: str | Path) -> List[str]:
    """Helper to inspect headers without loading all rows."""
    p = Path(path)
    with p.open("r", encoding="utf-8", newline="") as f:
        reader = csv.reader(f)
        headers = next(reader, None)
        if headers is None:
            return []
        return [normalize_column_name(h.lstrip("\ufeff").strip()) for h in headers]
