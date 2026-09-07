"""
ml/geospatial/enrichment.py — High-level enrichment orchestrator.

Converts clean ThermalEvent dicts → AI-ready EnrichedEvent dicts.

Design:
  enrich_events(
    events,
    facilities="industrial_facilities.geojson",
    landcover="landcover.geojson",
    forest="forest.geojson",  # optional separate
    agriculture="agri.geojson",
    history=...  # optional list for temporal
  )

Missing datasets → None / unknown (no fabrication).
Geodesic distances in meters.
Temporal leakage documented.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import List, Dict, Any, Optional, Union

from .facility_enrichment import FacilityEnricher
from .landcover_enrichment import LandcoverEnricher
from .temporal_enrichment import TemporalEnricher

# For type normalization export


def _load_events(events: Union[List[Dict[str, Any]], Dict[str, Any], str, Path]) -> List[Dict[str, Any]]:
    if isinstance(events, (str, Path)) and Path(events).exists():
        p = Path(events)
        if p.suffix.lower() == ".json":
            data = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(data, dict) and "features" in data:
                # GeoJSON? Extract?
                return []
            if isinstance(data, list):
                return data
            return [data]
        if p.suffix.lower() in (".csv", ".txt"):
            # FIRMS cleaned CSV? Use ml.data pipeline output
            import csv

            rows = []
            with p.open(encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for r in reader:
                    # Convert numeric strings
                    try:
                        r["latitude"] = float(r["latitude"])
                    except Exception:
                        pass
                    try:
                        r["longitude"] = float(r["longitude"])
                    except Exception:
                        pass
                    try:
                        r["frp"] = float(r["frp"])
                    except Exception:
                        pass
                    try:
                        r["brightness_temperature"] = float(r["brightness_temperature"])
                    except Exception:
                        pass
                    try:
                        r["confidence"] = float(r["confidence"])
                    except Exception:
                        pass
                    rows.append(r)
            return rows
        # Generic JSON
        return json.loads(p.read_text(encoding="utf-8"))
    if isinstance(events, dict):
        return [events]
    if isinstance(events, list):
        return events
    raise ValueError(f"Unsupported events input: {events!r}")


class EnrichmentPipeline:
    """
    Orchestrates geospatial + temporal enrichment for FIRMS events.

    All dataset paths may be None (missing → None/unknown).
    Caller (Yash) can supply local GeoJSON files; no live API.

    Persistence logic: spatial radius default 500m for temporal, 1000m for cluster.
    Facility baseline radius default 1000m.

    Leakage safety: when leakage_safe=True, all temporal fields (detections_24h/7d/30d,
    persistence_score, hotspot_cluster_size, facility_baseline/current_activity/anomaly)
    only use history with timestamp < event.timestamp (strict). Same-time records
    are excluded. Default False preserves backward compatibility for simple inference.
    """

    def __init__(
        self,
        facilities: Union[str, Path, Dict[str, Any], List[Dict[str, Any]], None] = None,
        landcover: Union[str, Path, Dict[str, Any], None] = None,
        forest: Union[str, Path, Dict[str, Any], None] = None,
        agriculture: Union[str, Path, Dict[str, Any], None] = None,
        history: Optional[List[Dict[str, Any]]] = None,
        *,
        persistence_radius_m: float = 500.0,
        cluster_radius_m: float = 1000.0,
        facility_assign_radius_m: float = 1000.0,
        leakage_safe: bool = False,
    ):
        # Facility
        if isinstance(facilities, FacilityEnricher):
            self.facility_enricher = facilities
        elif facilities is not None:
            try:
                self.facility_enricher = FacilityEnricher.from_geojson(facilities)
            except Exception:
                self.facility_enricher = FacilityEnricher.from_file(facilities)
        else:
            self.facility_enricher = FacilityEnricher([])

        # Landcover: if forest/agriculture supplied separately, build combined
        # Otherwise use single landcover file for all classes
        if landcover is not None:
            self.landcover_enricher = LandcoverEnricher.from_geojson(landcover)
        elif forest is not None or agriculture is not None:
            # Build combined from separate files by loading both and merging
            polys = []
            if forest is not None:
                en = LandcoverEnricher.from_geojson(forest)
                polys.extend(en.polygons)
            if agriculture is not None:
                en = LandcoverEnricher.from_geojson(agriculture)
                polys.extend(en.polygons)
            self.landcover_enricher = LandcoverEnricher(polys)
        else:
            self.landcover_enricher = LandcoverEnricher([])

        # Separate distance enrichers? If forest/agriculture separate files, we may want dedicated distance
        # For now landcover_enricher handles both distances from its polygon set.

        # Temporal
        self.temporal_enricher = TemporalEnricher(
            history=history,
            persistence_radius_m=persistence_radius_m,
            cluster_radius_m=cluster_radius_m,
            facility_assign_radius_m=facility_assign_radius_m,
            leakage_safe=leakage_safe,
        )
        self.history = history or []

    def enrich_one(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Enrich a single ThermalEvent dict → EnrichedEvent dict.
        Missing datasets yield None (never 0).
        """
        lat = float(event["latitude"])
        lon = float(event["longitude"])

        enriched = dict(event)  # shallow copy

        # Facility enrichment
        fac_info = self.facility_enricher.enrich(lat, lon)
        enriched["nearest_facility_id"] = fac_info["nearest_facility_id"]
        enriched["nearest_facility_name"] = fac_info["nearest_facility_name"]
        enriched["facility_type"] = fac_info["facility_type"]
        # Preserve original type if needed
        if fac_info.get("original_facility_type"):
            enriched["original_facility_type"] = fac_info["original_facility_type"]
        enriched["distance_to_industry"] = fac_info["distance_to_industry"]
        enriched["distance_to_facility_m"] = fac_info["distance_to_facility_m"]
        enriched["inside_industrial_area"] = fac_info["inside_industrial_area"]

        # Landcover enrichment
        lc_info = self.landcover_enricher.enrich(lat, lon)
        enriched["landcover_class"] = lc_info["landcover_class"]
        # Provide both _m variants for schema compatibility
        enriched["distance_to_forest"] = lc_info["distance_to_forest"]
        enriched["distance_to_forest_m"] = lc_info["distance_to_forest_m"]
        enriched["distance_to_agriculture"] = lc_info["distance_to_agriculture"]
        enriched["distance_to_agriculture_m"] = lc_info["distance_to_agriculture_m"]

        # Temporal enrichment (if history supplied)
        if self.history:
            temp_info = self.temporal_enricher.enrich(event)
            enriched["detections_24h"] = temp_info["detections_24h"]
            enriched["detections_7d"] = temp_info["detections_7d"]
            enriched["detections_30d"] = temp_info["detections_30d"]
            enriched["persistence"] = temp_info["persistence"]
            enriched["persistence_score"] = temp_info["persistence_score"]
            enriched["hotspot_cluster_size"] = temp_info["hotspot_cluster_size"]

            # Facility baseline (if facility exists)
            if fac_info["nearest_facility_id"] not in (None, "") and fac_info["distance_to_industry"] is not None and fac_info["distance_to_industry"] <= self.temporal_enricher.facility_assign_radius_m:
                # For baseline, use facility centroid? For Point facilities, use facility location
                # Find facility geometry point if available; else use event lat/lon as proxy?
                # For prototype, use event location as facility proxy (distance already small)
                # Better: use facility's actual location for baseline counting (distance from facility)
                # Retrieve facility entry to get its coordinates
                fac_entry = None
                for f in self.facility_enricher.facilities:
                    if f["id"] == fac_info["nearest_facility_id"]:
                        fac_entry = f
                        break
                if fac_entry and fac_entry["geometry"]["type"] == "Point":
                    fac_lon, fac_lat = fac_entry["geometry"]["coordinates"][0], fac_entry["geometry"]["coordinates"][1]
                    bl = self.temporal_enricher.facility_baseline(
                        fac_lat, fac_lon, current_event=event
                    )
                else:
                    # For polygon facility, use event location as approx
                    bl = self.temporal_enricher.facility_baseline(lat, lon, current_event=event)
                enriched["facility_baseline"] = bl["facility_baseline"]
                enriched["current_activity"] = bl["current_activity"]
                enriched["activity_anomaly"] = bl["activity_anomaly"]
                # Also expose ratio if we want (schema currently uses activity_anomaly, anomaly_ratio internally)
                # Store anomaly_ratio as extra for pipeline? Not in schema but can carry
                if bl.get("anomaly_ratio") is not None:
                    enriched["anomaly_ratio"] = bl["anomaly_ratio"]
        else:
            # No history → ensure missing temporal fields remain absent/None
            # Do not fabricate zeros
            pass

        # Ensure EnrichedEvent validation: coerce timestamp if needed? Keep as-is strings
        # Remove internal temp keys if they were None fabrications? We already handled.

        return enriched

    def enrich_events(self, events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return [self.enrich_one(e) for e in events]


def enrich_events(
    events: Union[List[Dict[str, Any]], Dict[str, Any], str, Path],
    facilities: Union[str, Path, Dict[str, Any], List[Dict[str, Any]], None] = None,
    landcover: Union[str, Path, Dict[str, Any], None] = None,
    history: Optional[List[Dict[str, Any]]] = None,
    **kwargs: Any,
) -> List[Dict[str, Any]]:
    """
    Convenience function.

    Example:
      enriched = enrich_events(
        events,
        facilities="industrial_facilities.geojson",
        landcover="landcover.geojson",
        history=historical_firms_events
      )
      result = predict(enriched[0])
    """
    ev_list = _load_events(events)
    pipeline = EnrichmentPipeline(
        facilities=facilities, landcover=landcover, history=history, **kwargs
    )
    return pipeline.enrich_events(ev_list)


# Alias for requested API shape: enrich_events(events, facilities=..., landcover=...)
# Also support forest/agriculture kwargs passthrough
