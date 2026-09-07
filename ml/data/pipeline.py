"""
ml/data/pipeline.py — FIRMS preprocessing pipeline orchestration.

Flow:
  CSV file
    → load_firms_csv (variant detection)
    → clean_rows (validation/normalization)
    → deduplicate (deterministic)
    → to ThermalEvent dicts
    → report + output (CSV/Parquet)

No internet, no India hard-box, no fabrication.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

from .firms_loader import load_firms_csv
from .firms_cleaner import clean_rows
from .firms_schema import FirmsSchemaError


@dataclass
class FirmsReport:
    input_rows: int = 0
    valid_rows: int = 0
    invalid_rows: int = 0
    duplicates_removed: int = 0
    missing_frp: int = 0
    missing_confidence: int = 0
    missing_brightness_temperature: int = 0
    unique_satellites: List[str] = field(default_factory=list)
    satellite_counts: Dict[str, int] = field(default_factory=dict)
    date_range: List[str] = field(default_factory=list)  # [min_iso, max_iso]
    latitude_range: List[float] = field(default_factory=list)
    longitude_range: List[float] = field(default_factory=list)
    invalid_reasons: Dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def pretty(self) -> str:
        lines = [
            "FIRMS preprocessing report",
            "--------------------------",
            f"Input rows:                {self.input_rows}",
            f"Valid rows:                {self.valid_rows}",
            f"Invalid rows:              {self.invalid_rows}",
            f"Duplicates removed:        {self.duplicates_removed}",
            f"Missing FRP:               {self.missing_frp}",
            f"Missing confidence:        {self.missing_confidence}",
            f"Missing brightness temp:   {self.missing_brightness_temperature}",
            f"Unique satellites:         {', '.join(self.unique_satellites) if self.unique_satellites else 'none'}",
            f"Satellite counts:          {self.satellite_counts or {}}",
            f"Date range:                {self.date_range if self.date_range else 'n/a'}",
            f"Latitude range:            {self.latitude_range if self.latitude_range else 'n/a'}",
            f"Longitude range:           {self.longitude_range if self.longitude_range else 'n/a'}",
        ]
        if self.invalid_reasons:
            lines.append("Invalid reasons breakdown:")
            for k, v in self.invalid_reasons.items():
                lines.append(f"  {k}: {v}")
        return "\n".join(lines)


def _dedup_key(event: Dict[str, Any]) -> Tuple[str, str, float, float]:
    """
    Deduplication key: (satellite, timestamp_to_minute, lat_rounded_4, lon_rounded_4).

    Rationale:
    - Same satellite overpass at same minute and same ~11m cell is duplicate.
    - Two legitimate separate fires at same location but different minutes/hours
      are NOT deduplicated (timestamp minute differs).
    - Nearby fires within 100m but same overpass with distinct lat/lon at 4dec
      remain distinct (different rounded cell).
    """
    # timestamp is ISO Z: 2026-09-06T10:30:00Z → minute precision for dedup
    ts = event["timestamp"]
    # ts format guaranteed ISO Z from cleaner; slice to minute
    minute_key = ts[:16]  # YYYY-MM-DDTHH:MM
    return (
        event["satellite"],
        minute_key,
        round(float(event["latitude"]), 4),
        round(float(event["longitude"]), 4),
    )


def deduplicate(events: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], int]:
    seen: Dict[Tuple, Dict[str, Any]] = {}
    dup = 0
    for ev in events:
        k = _dedup_key(ev)
        if k in seen:
            dup += 1
            continue
        seen[k] = ev
    return list(seen.values()), dup


def process_firms_file(
    input_path: str | Path,
    output_path: str | Path | None = None,
    dedup: bool = True,
    output_format: str | None = None,
) -> Tuple[List[Dict[str, Any]], FirmsReport]:
    """
    High-level pipeline. Returns (events, report).

    If output_path given, writes CSV (default) or Parquet (if .parquet and pyarrow available).
    output_format: "csv" | "parquet" | None (infer from output_path suffix)
    """
    p = Path(input_path)
    raw_rows, canonical_headers = load_firms_csv(p)
    input_rows = len(raw_rows)

    valid, invalid, missing_counts = clean_rows(raw_rows)

    # Build report pre-dedup
    total_invalid = len(invalid)
    dup_removed = 0
    if dedup:
        valid, dup_removed = deduplicate(valid)

    # Satellite/date/geo stats from valid
    satellites = [e["satellite"] for e in valid]
    unique_sats = sorted(set(satellites))
    sat_counts = dict(Counter(satellites))

    timestamps = sorted(e["timestamp"] for e in valid)
    date_range: List[str] = []
    if timestamps:
        date_range = [timestamps[0], timestamps[-1]]

    lat_range: List[float] = []
    lon_range: List[float] = []
    if valid:
        lats = [float(e["latitude"]) for e in valid]
        lons = [float(e["longitude"]) for e in valid]
        lat_range = [min(lats), max(lats)]
        lon_range = [min(lons), max(lons)]

    # Invalid reason breakdown (top substrings)
    reason_counter: Counter = Counter()
    for inv in invalid:
        reason = inv.get("reason", "unknown") if isinstance(inv, dict) else str(inv)
        # Normalize: first segment before colon
        key = reason.split(":")[0].strip()[:60]
        reason_counter[key] += 1

    report = FirmsReport(
        input_rows=input_rows,
        valid_rows=len(valid),
        invalid_rows=total_invalid,
        duplicates_removed=dup_removed,
        missing_frp=missing_counts.get("missing_frp", 0),
        missing_confidence=missing_counts.get("missing_confidence", 0),
        missing_brightness_temperature=missing_counts.get("missing_bt", 0),
        unique_satellites=unique_sats,
        satellite_counts=sat_counts,
        date_range=date_range,
        latitude_range=lat_range,
        longitude_range=lon_range,
        invalid_reasons=dict(reason_counter),
    )

    # Write output if requested
    if output_path is not None:
        out = Path(output_path)
        fmt = output_format
        if fmt is None:
            if out.suffix.lower() == ".parquet":
                fmt = "parquet"
            else:
                fmt = "csv"
        # Ensure parent exists
        out.parent.mkdir(parents=True, exist_ok=True)
        if fmt == "csv":
            _write_csv(valid, out)
        elif fmt == "parquet":
            _write_parquet(valid, out)
        else:
            raise ValueError(f"Unknown output_format: {fmt}")

    return valid, report


def _write_csv(events: List[Dict[str, Any]], path: Path) -> None:
    if not events:
        # Write header only (ThermalEvent fields)
        fields = ["id", "latitude", "longitude", "frp", "brightness_temperature", "confidence", "timestamp", "satellite"]
        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
        return
    fields = ["id", "latitude", "longitude", "frp", "brightness_temperature", "confidence", "timestamp", "satellite"]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for e in events:
            writer.writerow({k: e[k] for k in fields})


def _write_parquet(events: List[Dict[str, Any]], path: Path) -> None:
    try:
        import pyarrow as pa  # type: ignore
        import pyarrow.parquet as pq  # type: ignore
    except ImportError as exc:
        raise ImportError(
            "Parquet output requires 'pyarrow' (pip install pyarrow). Use CSV output instead."
        ) from exc
    if not events:
        pa_table = pa.table(
            {
                "id": pa.array([], type=pa.string()),
                "latitude": pa.array([], type=pa.float64()),
                "longitude": pa.array([], type=pa.float64()),
                "frp": pa.array([], type=pa.float64()),
                "brightness_temperature": pa.array([], type=pa.float64()),
                "confidence": pa.array([], type=pa.float64()),
                "timestamp": pa.array([], type=pa.string()),
                "satellite": pa.array([], type=pa.string()),
            }
        )
        pq.write_table(pa_table, str(path))
        return
    # Build columns
    table_dict = {
        "id": [e["id"] for e in events],
        "latitude": [float(e["latitude"]) for e in events],
        "longitude": [float(e["longitude"]) for e in events],
        "frp": [float(e["frp"]) for e in events],
        "brightness_temperature": [float(e["brightness_temperature"]) for e in events],
        "confidence": [float(e["confidence"]) for e in events],
        "timestamp": [e["timestamp"] for e in events],
        "satellite": [e["satellite"] for e in events],
    }
    table = pa.table(table_dict)
    pq.write_table(table, str(path))


def to_thermal_events(events: List[Dict[str, Any]]):
    """
    Convert processed dicts to validated ThermalEvent objects (for AI Core).
    Raises Pydantic ValidationError if contract broken (should not happen).
    """
    from ml.schemas import ThermalEvent

    return [ThermalEvent(**{k: v for k, v in e.items() if k in ThermalEvent.model_fields}) for e in events]


# CLI
def main() -> None:
    parser = argparse.ArgumentParser(description="FIRMS CSV preprocessing pipeline (local file, no internet)")
    parser.add_argument("input", help="Input FIRMS CSV file (local)")
    parser.add_argument("output", nargs="?", default=None, help="Output file (.csv or .parquet); if omitted, no file written (report only)")
    parser.add_argument("--no-dedup", action="store_true", help="Disable deduplication")
    parser.add_argument("--format", choices=["csv", "parquet"], default=None, help="Force output format")
    parser.add_argument("--report-json", default=None, help="Write report JSON to this path")
    args = parser.parse_args()

    try:
        events, report = process_firms_file(
            args.input, output_path=args.output, dedup=not args.no_dedup, output_format=args.format
        )
    except FirmsSchemaError as e:
        print(f"Schema error: {e}")
        raise SystemExit(2)
    except FileNotFoundError as e:
        print(str(e))
        raise SystemExit(2)

    print(report.pretty())
    print(f"\nProcessed events: {len(events)}")

    if args.report_json:
        Path(args.report_json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.report_json).write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")
        print(f"Report JSON written to {args.report_json}")

    if args.output:
        print(f"Output written to {args.output}")


if __name__ == "__main__":
    main()
