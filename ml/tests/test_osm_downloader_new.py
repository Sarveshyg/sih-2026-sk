"""
Tests for new OSM downloader features: User-Agent, status handling, tiled, cache, etc.
All network mocked.
"""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch
import pytest

from ml.geospatial.osm_downloader import (
    fetch_overpass,
    build_overpass_query,
    generate_tiles,
    download_tiled_osm,
    get_user_agent,
    get_endpoints,
)


def _mock_resp(status=200, json_data=None, headers=None, text=""):
    m = Mock()
    m.status_code = status
    m.headers = headers or {}
    m.text = text
    if json_data is not None:
        m.json = Mock(return_value=json_data)
    else:
        m.json = Mock(side_effect=Exception("no json"))
    return m


def test_user_agent_header(monkeypatch):
    # Default
    monkeypatch.delenv("OSM_USER_AGENT", raising=False)
    assert "SIH2026" in get_user_agent()
    # Custom
    monkeypatch.setenv("OSM_USER_AGENT", "CustomAgent/1.0")
    assert get_user_agent() == "CustomAgent/1.0"
    # Check fetch sends header
    sess = Mock()
    sess.post.return_value = _mock_resp(200, {"elements": []})
    fetch_overpass("query", endpoint="https://example.com", session=sess)
    args, kwargs = sess.post.call_args
    assert "User-Agent" in kwargs["headers"]
    assert kwargs["headers"]["User-Agent"] == "CustomAgent/1.0"
    assert "Accept" in kwargs["headers"]


def test_200_success():
    sess = Mock()
    sess.post.return_value = _mock_resp(200, {"elements": [{"type": "node", "id": 1}]})
    data = fetch_overpass("query", session=sess)
    assert len(data["elements"]) == 1


def test_406_handling_no_retry():
    sess = Mock()
    sess.post.return_value = _mock_resp(406, text="Not Acceptable")
    with pytest.raises(RuntimeError, match="406"):
        fetch_overpass("query", session=sess, max_retries=3)
    # Should have only one attempt (no retry for 406)
    assert sess.post.call_count == 1


def test_429_with_retry_after():
    sess = Mock()
    # First 429 with Retry-After, then 200
    sess.post.side_effect = [
        _mock_resp(429, headers={"Retry-After": "1"}, text="rate limit"),
        _mock_resp(200, {"elements": []}),
    ]
    with patch("ml.geospatial.osm_downloader.time.sleep") as mock_sleep:
        data = fetch_overpass("query", session=sess, max_retries=2, backoff=1.0)
        assert data["elements"] == []
        # Should have slept with Retry-After value 1
        mock_sleep.assert_called()
        assert sess.post.call_count == 2


def test_429_without_retry_after_uses_backoff():
    sess = Mock()
    sess.post.side_effect = [
        _mock_resp(429, headers={}, text="rate limit"),
        _mock_resp(200, {"elements": []}),
    ]
    with patch("ml.geospatial.osm_downloader.time.sleep") as mock_sleep:
        data = fetch_overpass("query", session=sess, max_retries=1, backoff=2.0)
        assert sess.post.call_count == 2
        mock_sleep.assert_called_with(2.0)


def test_500_retry_then_success():
    sess = Mock()
    sess.post.side_effect = [
        _mock_resp(500, text="server error"),
        _mock_resp(500, text="server error"),
        _mock_resp(200, {"elements": []}),
    ]
    with patch("ml.geospatial.osm_downloader.time.sleep"):
        data = fetch_overpass("query", session=sess, max_retries=2)
        assert sess.post.call_count == 3


def test_400_no_retry():
    sess = Mock()
    sess.post.return_value = _mock_resp(400, text="bad query")
    with pytest.raises(RuntimeError, match="400"):
        fetch_overpass("query", session=sess, max_retries=3)
    assert sess.post.call_count == 1


def test_timeout_failover():
    # Simulate timeout exception
    sess = Mock()
    sess.post.side_effect = Exception("ConnectTimeout")
    with pytest.raises(RuntimeError):
        fetch_overpass("query", session=sess, max_retries=1, timeout=(5, 10))
    # Should have tried max_retries+1 =2
    assert sess.post.call_count == 2


def test_endpoint_failover():
    # First endpoint fails with 500, second succeeds
    # Use download_tiled_osm with mocked fetch
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create minimal firms csv with 2 detections in same tile
        firms_path = Path(tmpdir) / "firms.csv"
        firms_path.write_text("id,latitude,longitude,frp,brightness_temperature,confidence,timestamp,satellite\n1,19.0,72.8,10,320,60,2026-08-01T00:00:00Z,VIIRS\n2,19.01,72.81,10,320,60,2026-08-01T00:00:00Z,VIIRS\n")
        cache_dir = Path(tmpdir) / "cache"
        # Mock fetch to fail first endpoint, succeed second
        def side_effect(query, endpoint=None, **kwargs):
            if "overpass-api.de" in endpoint:
                raise RuntimeError("Overpass 500 at https://overpass-api.de/api/interpreter")
            return {"elements": [{"type": "node", "id": 1, "lat": 19.0, "lon": 72.8, "tags": {"industrial": "factory"}}]}
        with patch("ml.geospatial.osm_downloader.fetch_overpass", side_effect=side_effect):
            report = download_tiled_osm(input_csv=firms_path, cache_dir=cache_dir, endpoints=["https://overpass-api.de/api/interpreter", "https://overpass.kumi.systems/api/interpreter"], tile_deg=1.0)
            assert report["successful_tiles"] == 1
            assert report["total_osm_elements"] == 1


def test_cache_hit():
    with tempfile.TemporaryDirectory() as tmpdir:
        firms_path = Path(tmpdir) / "firms.csv"
        firms_path.write_text("id,latitude,longitude,frp,brightness_temperature,confidence,timestamp,satellite\n1,19.0,72.8,10,320,60,2026-08-01T00:00:00Z,VIIRS\n")
        cache_dir = Path(tmpdir) / "cache"
        cache_dir.mkdir()
        # Create cached tile
        tiles = generate_tiles(firms_path, tile_deg=1.0)
        assert len(tiles) == 1
        tile = tiles[0]
        cache_file = cache_dir / f"{tile['id']}.json"
        cache_file.write_text(json.dumps({"elements": [{"type": "node", "id": 99, "lat": 19.0, "lon": 72.8, "tags": {}}]}))
        # Now download should hit cache, not call fetch
        with patch("ml.geospatial.osm_downloader.fetch_overpass") as mock_fetch:
            report = download_tiled_osm(input_csv=firms_path, cache_dir=cache_dir, tile_deg=1.0)
            mock_fetch.assert_not_called()
            assert report["cache_hits"] == 1
            assert report["successful_tiles"] == 1


def test_cache_miss_and_force():
    with tempfile.TemporaryDirectory() as tmpdir:
        firms_path = Path(tmpdir) / "firms.csv"
        firms_path.write_text("id,latitude,longitude,frp,brightness_temperature,confidence,timestamp,satellite\n1,19.0,72.8,10,320,60,2026-08-01T00:00:00Z,VIIRS\n")
        cache_dir = Path(tmpdir) / "cache"
        # First run creates cache
        with patch("ml.geospatial.osm_downloader.fetch_overpass", return_value={"elements": [{"type": "node", "id": 1, "lat": 19.0, "lon": 72.8, "tags": {}}]}):
            report1 = download_tiled_osm(input_csv=firms_path, cache_dir=cache_dir, tile_deg=1.0)
            assert report1["cache_hits"] == 0
        # Second run without force should hit cache
        with patch("ml.geospatial.osm_downloader.fetch_overpass") as mock_fetch:
            report2 = download_tiled_osm(input_csv=firms_path, cache_dir=cache_dir, tile_deg=1.0, force=False)
            mock_fetch.assert_not_called()
            assert report2["cache_hits"] == 1
        # With force, should fetch again
        with patch("ml.geospatial.osm_downloader.fetch_overpass", return_value={"elements": [{"type": "node", "id": 2, "lat": 19.0, "lon": 72.8, "tags": {}}]}):
            report3 = download_tiled_osm(input_csv=firms_path, cache_dir=cache_dir, tile_deg=1.0, force=True)
            assert report3["cache_hits"] == 0


def test_tile_generation_deterministic():
    with tempfile.TemporaryDirectory() as tmpdir:
        firms_path = Path(tmpdir) / "firms.csv"
        firms_path.write_text("id,latitude,longitude,frp,brightness_temperature,confidence,timestamp,satellite\n1,19.0,72.8,10,320,60,2026-08-01T00:00:00Z,VIIRS\n2,19.5,73.0,10,320,60,2026-08-01T00:00:00Z,VIIRS\n")
        tiles1 = generate_tiles(firms_path, tile_deg=1.0, buffer_deg=0.05)
        tiles2 = generate_tiles(firms_path, tile_deg=1.0, buffer_deg=0.05)
        assert tiles1 == tiles2
        # Check that number of tiles is less than detections (grouped)
        assert len(tiles1) <= 2
        # Check bbox format
        for t in tiles1:
            assert "south" in t and "west" in t
            assert t["bbox"].count(",") == 3


def test_duplicate_osm_removal():
    with tempfile.TemporaryDirectory() as tmpdir:
        firms_path = Path(tmpdir) / "firms.csv"
        # Two detections in same tile, each tile would return same OSM element id 1
        firms_path.write_text("id,latitude,longitude,frp,brightness_temperature,confidence,timestamp,satellite\n1,19.0,72.8,10,320,60,2026-08-01T00:00:00Z,VIIRS\n2,19.01,72.81,10,320,60,2026-08-01T00:00:00Z,VIIRS\n")
        cache_dir = Path(tmpdir) / "cache"
        # Mock fetch to return same element for tile
        with patch("ml.geospatial.osm_downloader.fetch_overpass", return_value={"elements": [{"type": "node", "id": 1, "lat": 19.0, "lon": 72.8, "tags": {"industrial": "factory"}}, {"type": "node", "id": 1, "lat": 19.0, "lon": 72.8, "tags": {"industrial": "factory"}}]}):
            report = download_tiled_osm(input_csv=firms_path, cache_dir=cache_dir, tile_deg=1.0)
            # Even though two tiles might be one, deduplication should result in 1 unique
            # In this case, only one tile, so elements 2 but duplicate id should be deduplicated to 1 in combined
            # Check combined file
            combined = Path("data/geospatial/cache/osm_india.json")
            # Our function writes to cache_dir parent combined, but also cache_dir/osm_download_report.json
            # Check total_osm_elements is deduplicated
            assert report["total_osm_elements"] == 1


def test_resume_after_failed_tile():
    with tempfile.TemporaryDirectory() as tmpdir:
        firms_path = Path(tmpdir) / "firms.csv"
        # Create 3 tiles by using spaced detections (each ~1 deg apart → 3 tiles)
        firms_path.write_text("id,latitude,longitude,frp,brightness_temperature,confidence,timestamp,satellite\n1,19.0,72.8,10,320,60,2026-08-01T00:00:00Z,VIIRS\n2,20.0,73.8,10,320,60,2026-08-01T00:00:00Z,VIIRS\n3,21.0,74.8,10,320,60,2026-08-01T00:00:00Z,VIIRS\n")
        cache_dir = Path(tmpdir) / "cache"
        # First run: mock tile containing 20.0 lat to fail on all endpoints
        def side_effect(query, endpoint=None, **kwargs):
            # Tile for 20.0,73.8 has buffered bbox 19.95,72.95,21.05,74.05
            if "19.9500,72.9500,21.0500,74.0500" in query:
                raise RuntimeError("Overpass 500 for tile 20")
            return {"elements": [{"type": "node", "id": 1, "lat": 19.0, "lon": 72.8, "tags": {}}]}
        with patch("ml.geospatial.osm_downloader.fetch_overpass", side_effect=side_effect):
            report = download_tiled_osm(input_csv=firms_path, cache_dir=cache_dir, tile_deg=1.0)
            assert report["failed_tiles"] == 1
            assert report["successful_tiles"] == 2
        # Second run (resume): should only retry failed tile, cache hits for others
        with patch("ml.geospatial.osm_downloader.fetch_overpass", return_value={"elements": [{"type": "node", "id": 99, "lat": 19.0, "lon": 72.8, "tags": {}}]}):
            report2 = download_tiled_osm(input_csv=firms_path, cache_dir=cache_dir, tile_deg=1.0)
            # Now all 3 should succeed (2 cache hits + 1 fetched)
            assert report2["successful_tiles"] == 3
            assert report2["cache_hits"] == 2


def test_no_credentials_in_logs(caplog):
    # Ensure no MAP_KEY or OSM credentials in logs (we don't use credentials, but check User-Agent not containing key)
    import logging
    # Check that get_user_agent does not contain FIRMS_MAP_KEY
    os.environ["FIRMS_MAP_KEY"] = "SECRET123"
    ua = get_user_agent()
    assert "SECRET123" not in ua
    assert "SECRET123" not in json.dumps({"ua": ua})


def test_deterministic_tile_generation():
    with tempfile.TemporaryDirectory() as tmpdir:
        firms_path = Path(tmpdir) / "firms.csv"
        firms_path.write_text("id,latitude,longitude,frp,brightness_temperature,confidence,timestamp,satellite\n2,19.01,72.81,10,320,60,2026-08-01T00:00:00Z,VIIRS\n1,19.0,72.8,10,320,60,2026-08-01T00:00:00Z,VIIRS\n")
        tiles1 = generate_tiles(firms_path, tile_deg=1.0)
        # Reverse order input should give same tiles sorted
        firms_path2 = Path(tmpdir) / "firms2.csv"
        firms_path2.write_text("id,latitude,longitude,frp,brightness_temperature,confidence,timestamp,satellite\n1,19.0,72.8,10,320,60,2026-08-01T00:00:00Z,VIIRS\n2,19.01,72.81,10,320,60,2026-08-01T00:00:00Z,VIIRS\n")
        tiles2 = generate_tiles(firms_path2, tile_deg=1.0)
        assert tiles1 == tiles2


def test_endpoints_configurable(monkeypatch):
    monkeypatch.setenv("OSM_OVERPASS_ENDPOINTS", "https://a.example.com/api,https://b.example.com/api")
    eps = get_endpoints()
    assert eps == ["https://a.example.com/api", "https://b.example.com/api"]
    monkeypatch.delenv("OSM_OVERPASS_ENDPOINTS", raising=False)
    eps2 = get_endpoints()
    assert len(eps2) >= 1
    assert "https://overpass-api.de/api/interpreter" in eps2
