"""
Tests for ml/data/firms_api.py — NASA FIRMS downloader.
All HTTP mocked; no real NASA calls.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch

import pytest

from ml.data.firms_api import (
    chunk_date_range,
    build_firms_url,
    get_map_key,
    download_firms,
    download_india_firms,
    combine_raw_chunks,
    INDIA_BBOX,
    SUPPORTED_SOURCES,
    MAX_DAY_RANGE,
)


SYNTHETIC_CSV = "latitude,longitude,bright_ti4,acq_date,acq_time,satellite,confidence,frp\n" \
                "19.076,72.877,341.2,2026-09-06,1030,VIIRS,n,124.5\n"


def _mock_response(status=200, text=SYNTHETIC_CSV):
    m = Mock()
    m.status_code = status
    m.text = text
    m.content = text.encode()
    return m


# --- MAP_KEY missing ---
def test_map_key_missing_raises(monkeypatch):
    monkeypatch.delenv("FIRMS_MAP_KEY", raising=False)
    # Ensure _load_dotenv does not re-populate from .env file during test
    with patch("ml.data.firms_api._load_dotenv"):
        with pytest.raises(RuntimeError, match="FIRMS_MAP_KEY"):
            get_map_key(None)
        with pytest.raises(RuntimeError, match="FIRMS_MAP_KEY"):
            download_india_firms("2026-08-01", "2026-08-05", output_dir=Path(tempfile.mkdtemp()), map_key="")


# --- URL construction ---
def test_url_construction():
    url = build_firms_url("MYKEY", "VIIRS_NOAA20_NRT", INDIA_BBOX, 5, date_str="2026-08-01")
    assert "MYKEY" in url
    assert "VIIRS_NOAA20_NRT" in url
    assert INDIA_BBOX in url
    assert "2026-08-01" in url
    assert url.startswith("https://")
    # without date
    url2 = build_firms_url("MYKEY", "VIIRS_NOAA20_NRT", INDIA_BBOX, 5)
    assert url2.count("/") >= 5


def test_bbox_construction_india():
    assert INDIA_BBOX == "68,6,98,36"
    # download_india should use it
    assert len(INDIA_BBOX.split(",")) == 4


# --- date chunking ---
def test_date_chunking():
    chunks = chunk_date_range("2026-08-01", "2026-08-10", max_days=5)
    assert chunks == [("2026-08-01", "2026-08-05"), ("2026-08-06", "2026-08-10")]

    # single day
    assert chunk_date_range("2026-08-01", "2026-08-01") == [("2026-08-01", "2026-08-01")]

    # 6 days → 2 chunks
    assert len(chunk_date_range("2026-08-01", "2026-08-06", max_days=5)) == 2
    assert len(chunk_date_range("2026-08-01", "2026-09-06", max_days=5)) == 8  # ~37 days


def test_max_5_day_chunks():
    chunks = chunk_date_range("2026-08-01", "2026-09-06", max_days=MAX_DAY_RANGE)
    for s, e in chunks:
        from datetime import date
        days = (date.fromisoformat(e) - date.fromisoformat(s)).days + 1
        assert days <= MAX_DAY_RANGE


def test_multiple_satellites_download(monkeypatch):
    tmp = Path(tempfile.mkdtemp())
    sess = Mock()
    sess.get.return_value = _mock_response(200, SYNTHETIC_CSV)
    # patch sleep to speed up
    with patch("ml.data.firms_api.time.sleep"):
        meta = download_india_firms("2026-08-01", "2026-08-05", output_dir=tmp, sources=SUPPORTED_SOURCES, map_key="DUMMYKEY", session=sess)
    # should have tried each source once
    assert sess.get.call_count == len(SUPPORTED_SOURCES)
    combined_meta = tmp / "download_metadata.json"
    assert combined_meta.exists()
    data = json.loads(combined_meta.read_text())
    assert set(data["sources"]) == set(SUPPORTED_SOURCES)
    # each source dir exists
    for src in SUPPORTED_SOURCES:
        assert (tmp / src).exists()


# --- retry behavior ---
def test_retry_on_429_then_success(monkeypatch, tmp_path):
    sess = Mock()
    # first 429, then 200
    sess.get.side_effect = [_mock_response(429, ""), _mock_response(200, SYNTHETIC_CSV)]
    out = tmp_path / "out.csv"
    with patch("ml.data.firms_api.time.sleep"):
        meta = download_firms("DUMMYKEY", "VIIRS_NOAA20_NRT", INDIA_BBOX, "2026-08-01", "2026-08-01", output_path=out, session=sess)
    assert sess.get.call_count == 2
    assert out.exists()
    assert "latitude" in out.read_text()


def test_retry_on_500_then_success(monkeypatch, tmp_path):
    sess = Mock()
    sess.get.side_effect = [_mock_response(500, ""), _mock_response(500, ""), _mock_response(200, SYNTHETIC_CSV)]
    out = tmp_path / "out2.csv"
    with patch("ml.data.firms_api.time.sleep"):
        meta = download_firms("DUMMYKEY", "VIIRS_NOAA20_NRT", INDIA_BBOX, "2026-08-01", "2026-08-01", output_path=out, session=sess)
    assert sess.get.call_count == 3
    assert meta["record_count"] == 1


def test_no_retry_on_auth_failure(monkeypatch, tmp_path):
    sess = Mock()
    sess.get.return_value = _mock_response(401, "Invalid key")
    out = tmp_path / "auth.csv"
    with pytest.raises(RuntimeError, match="authentication"):
        download_firms("BADKEY", "VIIRS_NOAA20_NRT", INDIA_BBOX, "2026-08-01", "2026-08-01", output_path=out, session=sess)
    # only one attempt (no retries on 401)
    assert sess.get.call_count == 1


# --- malformed / empty response ---
def test_malformed_response_handled(tmp_path):
    sess = Mock()
    sess.get.return_value = _mock_response(200, "not a csv at all")
    out = tmp_path / "mal.csv"
    with patch("ml.data.firms_api.time.sleep"):
        meta = download_firms("DUMMYKEY", "VIIRS_NOAA20_NRT", INDIA_BBOX, "2026-08-01", "2026-08-01", output_path=out, session=sess)
    # Should still write raw, but record_count reflects data rows parsing (0 if header missing logic)
    assert out.exists()


def test_empty_response(tmp_path):
    sess = Mock()
    sess.get.return_value = _mock_response(200, "")
    out = tmp_path / "empty.csv"
    with patch("ml.data.firms_api.time.sleep"):
        meta = download_firms("DUMMYKEY", "VIIRS_NOAA20_NRT", INDIA_BBOX, "2026-08-01", "2026-08-01", output_path=out, session=sess)
    assert meta["record_count"] == 0


# --- raw file writing ---
def test_raw_file_writing(tmp_path):
    sess = Mock()
    sess.get.return_value = _mock_response(200, SYNTHETIC_CSV)
    out_dir = tmp_path / "raw"
    with patch("ml.data.firms_api.time.sleep"):
        meta = download_india_firms("2026-08-01", "2026-08-05", output_dir=out_dir, sources=["VIIRS_NOAA20_NRT"], map_key="DUMMYKEY", session=sess)
    raw_file = out_dir / "VIIRS_NOAA20_NRT" / "VIIRS_NOAA20_NRT_2026-08-01_2026-08-05.csv"
    assert raw_file.exists()
    assert "latitude" in raw_file.read_text()
    assert (raw_file.with_suffix(".json")).exists()


# --- resumable download ---
def test_resumable_download_skips_existing(tmp_path):
    out_dir = tmp_path / "raw2"
    src_dir = out_dir / "VIIRS_NOAA20_NRT"
    src_dir.mkdir(parents=True)
    existing = src_dir / "VIIRS_NOAA20_NRT_2026-08-01_2026-08-05.csv"
    existing.write_text(SYNTHETIC_CSV)
    sess = Mock()
    # should not be called if file exists and not force
    with patch("ml.data.firms_api.time.sleep"):
        meta = download_india_firms("2026-08-01", "2026-08-05", output_dir=out_dir, sources=["VIIRS_NOAA20_NRT"], map_key="DUMMYKEY", session=sess)
    sess.get.assert_not_called()

    # with force, should re-download
    sess2 = Mock()
    sess2.get.return_value = _mock_response(200, SYNTHETIC_CSV)
    with patch("ml.data.firms_api.time.sleep"):
        meta2 = download_india_firms("2026-08-01", "2026-08-05", output_dir=out_dir, sources=["VIIRS_NOAA20_NRT"], map_key="DUMMYKEY", force=True, session=sess2)
    assert sess2.get.call_count == 1


# --- metadata creation ---
def test_metadata_creation(tmp_path):
    sess = Mock()
    sess.get.return_value = _mock_response(200, SYNTHETIC_CSV)
    out_dir = tmp_path / "meta_raw"
    with patch("ml.data.firms_api.time.sleep"):
        meta = download_india_firms("2026-08-01", "2026-08-05", output_dir=out_dir, sources=["VIIRS_NOAA20_NRT"], map_key="DUMMYKEY", session=sess)
    # aggregate metadata
    agg = json.loads((out_dir / "download_metadata.json").read_text())
    assert agg["bbox"] == [68, 6, 98, 36]
    assert agg["start_date"] == "2026-08-01"
    assert agg["end_date"] == "2026-08-05"
    assert "downloaded_at" in agg
    assert agg["sources"] == ["VIIRS_NOAA20_NRT"]
    # per-chunk json
    chunk_meta = json.loads((out_dir / "VIIRS_NOAA20_NRT" / "VIIRS_NOAA20_NRT_2026-08-01_2026-08-05.json").read_text())
    assert chunk_meta["source"] == "VIIRS_NOAA20_NRT"
    assert "record_count" in chunk_meta


# --- combine operation ---
def test_combine_operation(tmp_path):
    raw_dir = tmp_path / "raw_combine"
    raw_dir.mkdir()
    src1 = raw_dir / "VIIRS_NOAA20_NRT"
    src1.mkdir()
    (src1 / "VIIRS_NOAA20_NRT_2026-08-01_2026-08-05.csv").write_text(SYNTHETIC_CSV)
    src2 = raw_dir / "VIIRS_NOAA21_NRT"
    src2.mkdir()
    # second file with same header but different row
    csv2 = "latitude,longitude,bright_ti4,acq_date,acq_time,satellite,confidence,frp\n20.0,73.0,330.0,2026-08-06,1030,VIIRS,h,45.2\n"
    (src2 / "VIIRS_NOAA21_NRT_2026-08-06_2026-08-10.csv").write_text(csv2)

    out = tmp_path / "combined.csv"
    summary = combine_raw_chunks(raw_dir, out)
    assert summary["files_combined"] == 2
    assert summary["total_rows"] == 2
    content = out.read_text()
    assert content.count("latitude") == 1  # header only once
    assert "19.076" in content
    assert "20.0" in content


# --- no MAP_KEY in metadata/logs ---
def test_no_map_key_in_metadata(tmp_path):
    sess = Mock()
    sess.get.return_value = _mock_response(200, SYNTHETIC_CSV)
    secret = "SECRETKEY123"
    out_dir = tmp_path / "leak_check"
    with patch("ml.data.firms_api.time.sleep"):
        meta = download_india_firms("2026-08-01", "2026-08-05", output_dir=out_dir, sources=["VIIRS_NOAA20_NRT"], map_key=secret, session=sess)
    # check aggregate metadata does not contain secret
    agg_text = (out_dir / "download_metadata.json").read_text()
    assert secret not in agg_text
    # check per-chunk metadata
    chunk_text = (out_dir / "VIIRS_NOAA20_NRT" / "VIIRS_NOAA20_NRT_2026-08-01_2026-08-05.json").read_text()
    assert secret not in chunk_text
    # check combined metadata returned also not containing key (it never should)
    assert secret not in json.dumps(meta)
    # check raw csv does not contain key (it shouldn't)
    raw_text = (out_dir / "VIIRS_NOAA20_NRT" / "VIIRS_NOAA20_NRT_2026-08-01_2026-08-05.csv").read_text()
    assert secret not in raw_text
