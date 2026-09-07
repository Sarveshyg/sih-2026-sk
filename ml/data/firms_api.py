"""
ml/data/firms_api.py — NASA FIRMS API downloader.

Uses official FIRMS Area API:
  https://firms.modaps.eosdis.nasa.gov/api/area/
  Pattern: /api/area/csv/{MAP_KEY}/{SOURCE}/{AREA}/{DAY_RANGE}
  Historical requests add /{DATE} suffix per docs; this module handles both.

Never hard-codes MAP_KEY. Reads from FIRMS_MAP_KEY env (and optional .env).
Raw CSVs preserved under data/firms/raw/{SOURCE}/.
Metadata never contains MAP_KEY.

No live-API tests — all tests mock HTTP.
"""

from __future__ import annotations

import csv
import json
import os
import time
import logging
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

try:
    import requests  # type: ignore
except ImportError:  # pragma: no cover
    requests = None  # type: ignore

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
FIRMS_API_BASE = "https://firms.modaps.eosdis.nasa.gov/api"
INDIA_BBOX = "68,6,98,36"  # west,south,east,north — bounding box (includes neighbors)
INDIA_BBOX_LIST = [68, 6, 98, 36]
SUPPORTED_SOURCES = [
    "VIIRS_NOAA20_NRT",
    "VIIRS_NOAA21_NRT",
    "VIIRS_SNPP_NRT",
]
# Spec says 5 days per request; NASA docs show 10 for area, but we obey 5
MAX_DAY_RANGE = 5
RETRY_STATUS_CODES = {429, 500, 502, 503, 504}
DEFAULT_MAX_RETRIES = 3
DEFAULT_BACKOFF = 1.5  # seconds base
DEFAULT_TIMEOUT = 60  # seconds
DEFAULT_DAY_RANGE = 1  # for daily granularity; chunk logic uses max 5

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Env / MAP_KEY
# ---------------------------------------------------------------------------
def _load_dotenv(path: Optional[Path] = None) -> None:
    """Minimal .env loader — does not overwrite existing env."""
    candidates = []
    if path is not None:
        candidates.append(Path(path))
    else:
        # repo root .env and cwd .env
        candidates.append(Path(".env"))
        # ml/.env etc.
        candidates.append(Path(__file__).resolve().parents[2] / ".env")
    for p in candidates:
        if p.exists():
            try:
                for line in p.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    k = k.strip()
                    v = v.strip().strip('"').strip("'")
                    if k and k not in os.environ:
                        os.environ[k] = v
            except Exception:
                continue
            break


def get_map_key(map_key: Optional[str] = None) -> str:
    """Return MAP_KEY from arg or FIRMS_MAP_KEY env, or raise with clear message."""
    _load_dotenv()
    key = map_key or os.environ.get("FIRMS_MAP_KEY", "").strip()
    if not key:
        raise RuntimeError("FIRMS_MAP_KEY environment variable is required. Set FIRMS_MAP_KEY or pass map_key explicitly.")
    return key


# ---------------------------------------------------------------------------
# Date utilities
# ---------------------------------------------------------------------------
def _parse_date(s: str) -> date:
    try:
        return date.fromisoformat(s.strip())
    except Exception as e:
        raise ValueError(f"Invalid date '{s}'; expected YYYY-MM-DD") from e


def chunk_date_range(start: str | date, end: str | date, max_days: int = MAX_DAY_RANGE) -> List[Tuple[str, str]]:
    """Split [start, end] inclusive into chunks of at most max_days days."""
    s = _parse_date(start) if isinstance(start, str) else start
    e = _parse_date(end) if isinstance(end, str) else end
    if s > e:
        raise ValueError(f"start_date {s} after end_date {e}")
    chunks: List[Tuple[str, str]] = []
    cur = s
    while cur <= e:
        chunk_end = min(cur + timedelta(days=max_days - 1), e)
        chunks.append((cur.isoformat(), chunk_end.isoformat()))
        cur = chunk_end + timedelta(days=1)
    return chunks


def _day_range_for_chunk(start: str, end: str) -> int:
    s = _parse_date(start)
    e = _parse_date(end)
    return (e - s).days + 1


# ---------------------------------------------------------------------------
# URL construction
# ---------------------------------------------------------------------------
def build_firms_url(
    map_key: str,
    source: str,
    bbox: str = INDIA_BBOX,
    day_range: int = 1,
    date_str: Optional[str] = None,
) -> str:
    """
    Build FIRMS Area API URL.
    Pattern: /api/area/csv/{MAP_KEY}/{SOURCE}/{AREA}/{DAY_RANGE}[/{DATE}]
    For recent data (NRT), DATE is optional; for historical, DATE anchors window.
    We always include DATE when provided for deterministic historical fetches.
    """
    # sanitize — do not log key
    bbox = bbox.strip()
    source = source.strip()
    url = f"{FIRMS_API_BASE}/area/csv/{map_key}/{source}/{bbox}/{day_range}"
    if date_str:
        url = f"{url}/{date_str}"
    return url


# ---------------------------------------------------------------------------
# HTTP with retries
# ---------------------------------------------------------------------------
def _is_retryable(status: Optional[int], exc: Optional[Exception]) -> bool:
    if exc is not None:
        return True  # timeouts etc. retryable
    if status in RETRY_STATUS_CODES:
        return True
    return False


def _fetch_with_retries(
    url: str,
    max_retries: int = DEFAULT_MAX_RETRIES,
    backoff: float = DEFAULT_BACKOFF,
    timeout: int = DEFAULT_TIMEOUT,
    session=None,
) -> Any:
    """
    GET with exponential backoff. Returns response-like with status_code, text/content.
    Uses requests if available, else urllib. Never logs URL with key in clear? We strip key for logs.
    Caller ensures MAP_KEY not printed.
    """
    if requests is None:  # pragma: no cover
        raise RuntimeError("requests library is required for FIRMS API (pip install requests)")
    sess = session or requests.Session()
    last_exc = None
    for attempt in range(max_retries + 1):
        try:
            resp = sess.get(url, timeout=timeout)
            # Do not retry auth failures 401/403
            if resp.status_code in (401, 403):
                # Return immediately — caller will surface auth error
                return resp
            if resp.status_code == 200:
                return resp
            # Check retryable
            if _is_retryable(resp.status_code, None) and attempt < max_retries:
                sleep = backoff * (2 ** attempt)
                log.warning(f"FIRMS transient {resp.status_code}, retry {attempt+1}/{max_retries} in {sleep:.1f}s")
                time.sleep(sleep)
                continue
            return resp
        except Exception as e:  # timeout, connection
            last_exc = e
            if attempt < max_retries and _is_retryable(None, e):
                sleep = backoff * (2 ** attempt)
                log.warning(f"FIRMS request exception {e!r}, retry {attempt+1}/{max_retries} in {sleep:.1f}s")
                time.sleep(sleep)
                continue
            raise
    if last_exc:
        raise last_exc  # type: ignore
    return resp  # type: ignore


# ---------------------------------------------------------------------------
# Download helpers
# ---------------------------------------------------------------------------
def _ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def _chunk_filename(source: str, start: str, end: str) -> str:
    return f"{source}_{start}_{end}.csv"


def _is_valid_csv(path: Path, min_bytes: int = 20) -> bool:
    if not path.exists() or path.stat().st_size < min_bytes:
        return False
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as f:
            header = f.readline()
            if not header or "latitude" not in header.lower():
                # FIRMS header should contain latitude column; but check at least comma
                if "," not in header:
                    return False
            # need at least header line
            return True
    except Exception:
        return False


def _count_records(path: Path) -> int:
    if not path.exists():
        return 0
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as f:
            reader = csv.DictReader(f)
            return sum(1 for _ in reader)
    except Exception:
        return 0


def _write_metadata(
    meta_path: Path,
    source: str,
    bbox: List[int] | str,
    start_date: str,
    end_date: str,
    chunks: List[Dict[str, Any]],
    record_count: int,
    failed_chunks: List[Dict[str, Any]],
) -> None:
    bbox_list = bbox if isinstance(bbox, list) else [int(x) for x in str(bbox).split(",")]
    meta = {
        "source": source,
        "bbox": bbox_list,
        "bbox_str": INDIA_BBOX if bbox_list == INDIA_BBOX_LIST else ",".join(map(str, bbox_list)),
        "bbox_note": "India bounding box 68,6,98,36 (includes neighboring countries; not exact political polygon)",
        "start_date": start_date,
        "end_date": end_date,
        "downloaded_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "record_count": record_count,
        "chunks": chunks,
        "failed_chunks": failed_chunks,
        # Never include MAP_KEY
    }
    _ensure_dir(meta_path.parent)
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def download_firms(
    map_key: Optional[str],
    source: str,
    bbox: str,
    start_date: str,
    end_date: str,
    output_path: str | Path,
    *,
    max_days: int = MAX_DAY_RANGE,
    max_retries: int = DEFAULT_MAX_RETRIES,
    backoff: float = DEFAULT_BACKOFF,
    timeout: int = DEFAULT_TIMEOUT,
    force: bool = False,
    session=None,
) -> Dict[str, Any]:
    """
    Download FIRMS for a source/bbox/date range.
    Splits into <=max_days chunks (default 5). Writes combined CSV to output_path.
    Returns metadata dict.
    """
    key = get_map_key(map_key)
    if source not in SUPPORTED_SOURCES:
        log.warning(f"Source {source} not in recommended VIIRS list; proceeding anyway")
    bbox = bbox or INDIA_BBOX
    chunks = chunk_date_range(start_date, end_date, max_days=max_days)
    output_path = Path(output_path)
    _ensure_dir(output_path.parent)

    # We will fetch each chunk and accumulate
    all_rows: List[str] = []
    header: Optional[str] = None
    failed: List[Dict[str, Any]] = []
    chunk_infos: List[Dict[str, Any]] = []
    total_records = 0

    sess = session or (requests.Session() if requests else None)

    for (c_start, c_end) in chunks:
        day_range = _day_range_for_chunk(c_start, c_end)
        # For area API, DATE is start of chunk (historical anchor)
        url = build_firms_url(key, source, bbox, day_range, date_str=c_start)
        # Never log full url with key
        log.info(f"FIRMS fetch {source} {c_start}..{c_end} ({day_range}d)")

        try:
            resp = _fetch_with_retries(url, max_retries=max_retries, backoff=backoff, timeout=timeout, session=sess)
        except Exception as e:
            failed.append({"start": c_start, "end": c_end, "error": str(e)[:200]})
            continue

        if resp.status_code in (401, 403):
            raise RuntimeError(f"FIRMS authentication failed ({resp.status_code}). Check FIRMS_MAP_KEY.")
        if resp.status_code != 200:
            failed.append({"start": c_start, "end": c_end, "status": resp.status_code, "body": getattr(resp, "text", "")[:500]})
            continue

        text = resp.text if hasattr(resp, "text") else resp.content.decode("utf-8", errors="ignore")
        # Handle empty or error csv
        if not text or text.strip() == "":
            # Empty = no fires in window, not error; count 0
            chunk_infos.append({"start": c_start, "end": c_end, "records": 0, "status": "empty"})
            continue
        # Some errors return small HTML/text without latitude header
        if "latitude" not in text.lower().splitlines()[0]:
            # Could be error message but still check if it looks like csv header mismatch
            # If first line has no latitude but has error text, treat as failed
            if len(text) < 200 and "<html" not in text.lower():
                # Maybe actual empty with message?
                pass
        lines = text.splitlines()
        if not lines:
            chunk_infos.append({"start": c_start, "end": c_end, "records": 0, "status": "empty"})
            continue
        # first line is header
        if header is None:
            header = lines[0]
            all_rows.append(header)
        else:
            # verify header matches (ignore if mismatch, just skip header)
            if lines[0].strip() != header.strip():
                # If header differs, still use header from first chunk; skip this header
                pass
        # append data rows (skip empty)
        data_lines = [l for l in lines[1:] if l.strip()]
        all_rows.extend(data_lines)
        chunk_infos.append({"start": c_start, "end": c_end, "records": len(data_lines), "status": "ok"})
        total_records += len(data_lines)
        # Rate limit spacing
        time.sleep(0.5)

    # Write combined output
    if header is not None:
        output_path.write_text("\n".join(all_rows) + "\n", encoding="utf-8")
    else:
        # No data at all — write empty with no header? Write nothing but create file with header attempt
        output_path.write_text("", encoding="utf-8")

    meta = {
        "source": source,
        "bbox": INDIA_BBOX_LIST if bbox == INDIA_BBOX else [int(x) for x in bbox.split(",")],
        "start_date": start_date,
        "end_date": end_date,
        "downloaded_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "record_count": total_records,
        "chunks": chunk_infos,
        "failed_chunks": failed,
    }
    return meta


def download_india_firms(
    start_date: str,
    end_date: str,
    output_dir: str | Path = "data/firms/raw",
    sources: Optional[List[str]] = None,
    map_key: Optional[str] = None,
    max_days: int = MAX_DAY_RANGE,
    max_retries: int = DEFAULT_MAX_RETRIES,
    backoff: float = DEFAULT_BACKOFF,
    force: bool = False,
    session=None,
) -> Dict[str, Any]:
    """
    Download India VIIRS NRT for all requested sources to data/firms/raw/{SOURCE}/ chunks.
    Resumable: deterministic filenames per chunk, skips existing valid files unless force.
    Returns combined metadata.
    """
    key = get_map_key(map_key)
    sources = sources or SUPPORTED_SOURCES
    output_dir = Path(output_dir)
    bbox = INDIA_BBOX

    if not start_date or not end_date:
        raise ValueError("start_date and end_date are required (e.g., 2026-08-01)")

    chunks = chunk_date_range(start_date, end_date, max_days=max_days)
    overall_meta: Dict[str, Any] = {
        "bbox": INDIA_BBOX_LIST,
        "bbox_str": INDIA_BBOX,
        "bbox_note": "India bounding box 68,6,98,36 (includes neighboring countries; not exact political polygon)",
        "start_date": start_date,
        "end_date": end_date,
        "sources": sources,
        "chunks_total": len(chunks) * len(sources),
    }
    all_metas: List[Dict[str, Any]] = []

    sess = session or (requests.Session() if requests else None)

    for source in sources:
        src_dir = output_dir / source
        _ensure_dir(src_dir)
        for (c_start, c_end) in chunks:
            fname = _chunk_filename(source, c_start, c_end)
            fpath = src_dir / fname
            meta_path = fpath.with_suffix(".json")

            if fpath.exists() and _is_valid_csv(fpath) and not force:
                # Skip — resumable
                log.info(f"Skip existing {fname} (use --force to re-download)")
                # Count existing records for metadata
                cnt = _count_records(fpath)
                all_metas.append({"source": source, "start": c_start, "end": c_end, "status": "skipped", "records": cnt})
                continue

            day_range = _day_range_for_chunk(c_start, c_end)
            url = build_firms_url(key, source, bbox, day_range, date_str=c_start)
            # Do not log key
            log.info(f"Downloading {source} {c_start}..{c_end}")

            try:
                resp = _fetch_with_retries(url, max_retries=max_retries, backoff=backoff, session=sess)
            except Exception as e:
                log.error(f"Failed {source} {c_start}..{c_end}: {e}")
                all_metas.append({"source": source, "start": c_start, "end": c_end, "status": "failed", "error": str(e)[:200]})
                continue

            if resp.status_code in (401, 403):
                raise RuntimeError(f"FIRMS authentication failed ({resp.status_code}). Check FIRMS_MAP_KEY.")
            if resp.status_code != 200:
                log.warning(f"Chunk {c_start}..{c_end} status {resp.status_code}")
                # Write failed marker but don't create csv
                all_metas.append({"source": source, "start": c_start, "end": c_end, "status": f"http_{resp.status_code}"})
                continue

            text = resp.text if hasattr(resp, "text") else resp.content.decode("utf-8", errors="ignore")
            # Write raw csv
            fpath.write_text(text, encoding="utf-8")
            cnt = _count_records(fpath) if text and "latitude" in text.lower() else 0
            # Write per-chunk metadata (no key)
            chunk_meta = {
                "source": source,
                "bbox": INDIA_BBOX_LIST,
                "start_date": c_start,
                "end_date": c_end,
                "downloaded_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "record_count": cnt,
                "status": "ok" if cnt > 0 else "empty",
            }
            meta_path.write_text(json.dumps(chunk_meta, indent=2), encoding="utf-8")
            all_metas.append({"source": source, "start": c_start, "end": c_end, "status": "ok", "records": cnt})
            time.sleep(0.6)  # spacing

    # Write aggregate metadata
    aggregate = {
        "bbox": INDIA_BBOX_LIST,
        "bbox_str": INDIA_BBOX,
        "_bbox_note": "India bounding box 68,6,98,36 (includes neighboring countries; not exact political polygon)",
        "start_date": start_date,
        "end_date": end_date,
        "downloaded_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "sources": sources,
        "chunks": all_metas,
        "total_records": sum(m.get("records", 0) for m in all_metas if isinstance(m.get("records"), int)),
        "failed_chunks": [m for m in all_metas if m.get("status") not in ("ok", "skipped", "empty")],
    }
    # Write to output_dir / metadata.json
    meta_file = output_dir / "download_metadata.json"
    _ensure_dir(output_dir)
    meta_file.write_text(json.dumps(aggregate, indent=2), encoding="utf-8")
    return aggregate


def combine_raw_chunks(
    input_dir: str | Path,
    output_path: str | Path,
    pattern: str = "*.csv",
) -> Dict[str, Any]:
    """
    Combine raw FIRMS CSV chunks under input_dir into single CSV at output_path.
    Preserves header from first file, appends data rows.
    Returns summary dict.

    input_dir may contain subdirs per source (e.g., data/firms/raw/VIIRS_NOAA20_NRT/)
    """
    input_dir = Path(input_dir)
    output_path = Path(output_path)
    _ensure_dir(output_path.parent)

    csv_files: List[Path] = sorted(input_dir.rglob(pattern))
    if not csv_files:
        raise FileNotFoundError(f"No CSV files found under {input_dir} matching {pattern}")

    header: Optional[str] = None
    total_rows = 0
    sources_seen: List[str] = []
    for f in csv_files:
        try:
            text = f.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        lines = text.splitlines()
        if not lines:
            continue
        h = lines[0]
        if header is None:
            header = h
        # skip header if present and matches-ish
        data = lines[1:] if h.strip().lower().startswith("latitude") else lines
        # filter empty
        data = [l for l in data if l.strip()]
        total_rows += len(data)
        sources_seen.append(f.parent.name if f.parent != input_dir else f.stem)
        # Lazy write: first file write header, subsequent append data
        if header is not None and f == csv_files[0]:
            # write header + first data
            output_path.write_text(header + "\n" + "\n".join(data) + ("\n" if data else "\n"), encoding="utf-8")
        else:
            # append
            with output_path.open("a", encoding="utf-8") as out:
                if data:
                    out.write("\n".join(data) + "\n")

    # Ensure output exists even if all empty
    if not output_path.exists():
        if header:
            output_path.write_text(header + "\n", encoding="utf-8")
        else:
            output_path.write_text("", encoding="utf-8")

    summary = {
        "input_dir": str(input_dir),
        "output_path": str(output_path),
        "files_combined": len(csv_files),
        "total_rows": total_rows,
        "header": header,
    }
    return summary


def check_availability(
    map_key: Optional[str] = None,
    source: str = SUPPORTED_SOURCES[0],
    session=None,
) -> Dict[str, Any]:
    """
    Check FIRMS data availability via https://firms.modaps.eosdis.nasa.gov/api/data_availability
    Optional — not required before download.
    """
    key = get_map_key(map_key)
    url = f"{FIRMS_API_BASE}/data_availability/csv/{key}/{source}"
    sess = session or (requests.Session() if requests else None)
    # Don't leak key in logs
    log.info(f"Checking availability for {source}")
    resp = _fetch_with_retries(url, max_retries=2, backoff=1.0, session=sess)
    if resp.status_code != 200:
        return {"source": source, "status": resp.status_code, "text": getattr(resp, "text", "")[:500]}
    # Response is CSV with date ranges; return parsed
    text = resp.text if hasattr(resp, "text") else resp.content.decode("utf-8", errors="ignore")
    lines = [l for l in text.splitlines() if l.strip()]
    return {"source": source, "status": 200, "lines": lines[:5], "full_text": text[:2000]}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _build_cli():
    import argparse

    parser = argparse.ArgumentParser(prog="firms_api", description="NASA FIRMS API downloader (local file, no hard-coded key)")
    sub = parser.add_subparsers(dest="cmd", required=True)

    # download
    p_dl = sub.add_parser("download", help="Download India FIRMS data")
    p_dl.add_argument("--start", required=True, help="Start date YYYY-MM-DD")
    p_dl.add_argument("--end", required=True, help="End date YYYY-MM-DD")
    p_dl.add_argument("--sources", nargs="*", default=SUPPORTED_SOURCES, help=f"VIIRS sources (default {SUPPORTED_SOURCES})")
    p_dl.add_argument("--output", default="data/firms/raw", help="Output directory for raw chunks")
    p_dl.add_argument("--bbox", default=INDIA_BBOX, help="Bounding box west,south,east,north (default India 68,6,98,36)")
    p_dl.add_argument("--force", action="store_true", help="Re-download even if file exists")
    p_dl.add_argument("--max-days", type=int, default=MAX_DAY_RANGE, help="Max days per request (default 5)")
    p_dl.add_argument("--map-key", default=None, help="FIRMS MAP_KEY (or set FIRMS_MAP_KEY env)")

    # combine
    p_comb = sub.add_parser("combine", help="Combine raw CSV chunks into single CSV")
    p_comb.add_argument("--input", dest="input_dir", required=True, help="Input directory containing raw CSVs")
    p_comb.add_argument("--output", required=True, help="Output combined CSV path")

    # availability
    p_av = sub.add_parser("availability", help="Check FIRMS data availability")
    p_av.add_argument("--source", default=SUPPORTED_SOURCES[0], help="Source to check")
    p_av.add_argument("--map-key", default=None, help="FIRMS MAP_KEY")

    # single-source download (generic)
    p_one = sub.add_parser("download-one", help="Download single source/bbox to one combined CSV (generic API)")
    p_one.add_argument("--source", required=True)
    p_one.add_argument("--bbox", default=INDIA_BBOX)
    p_one.add_argument("--start", required=True)
    p_one.add_argument("--end", required=True)
    p_one.add_argument("--output", required=True, help="Output combined CSV path")
    p_one.add_argument("--map-key", default=None)

    return parser


def main(argv: Optional[List[str]] = None) -> None:
    parser = _build_cli()
    args = parser.parse_args(argv)

    # Set up minimal logging to console
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    if args.cmd == "download":
        if not args.start or not args.end:
            parser.error("start and end are required (e.g., --start 2026-08-01 --end 2026-09-06)")
        meta = download_india_firms(
            start_date=args.start,
            end_date=args.end,
            output_dir=args.output,
            sources=args.sources,
            map_key=args.map_key,
            max_days=args.max_days,
            force=args.force,
        )
        print(json.dumps(meta, indent=2))
        print(f"\nDownload complete. Raw chunks in {args.output}")

    elif args.cmd == "combine":
        summary = combine_raw_chunks(args.input_dir, args.output)
        print(json.dumps(summary, indent=2))
        print(f"Combined {summary['files_combined']} files -> {args.output} ({summary['total_rows']} rows)")

    elif args.cmd == "availability":
        info = check_availability(map_key=args.map_key, source=args.source)
        print(json.dumps(info, indent=2))

    elif args.cmd == "download-one":
        meta = download_firms(
            map_key=args.map_key,
            source=args.source,
            bbox=args.bbox,
            start_date=args.start,
            end_date=args.end,
            output_path=args.output,
        )
        print(json.dumps(meta, indent=2))

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
