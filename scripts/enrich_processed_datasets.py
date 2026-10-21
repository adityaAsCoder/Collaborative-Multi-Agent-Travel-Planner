"""Rebuild the processed catalog from raw names and validated local OSM evidence."""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
import unicodedata
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import geopandas as gpd
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
DESTINATIONS_CSV = ROOT / "datasets" / "processed" / "destinations.csv"
ATTRACTIONS_CSV = ROOT / "datasets" / "processed" / "attractions.csv"
HOTELS_CSV = ROOT / "datasets" / "processed" / "hotels.csv"
TOURISM_JSON = ROOT / "datasets" / "raw" / "tourism" / "india_tourism_dataset.json"
OSM_GPKG = ROOT / "datasets" / "osm" / "northern-zone.gpkg"
OSM_README = ROOT / "datasets" / "osm" / "README"
PROVENANCE_CSV = ROOT / "datasets" / "processed" / "attraction_field_provenance.csv"
OSM_SOURCE_URL = "https://www.openstreetmap.org/"
OSM_SNAPSHOT_RE = re.compile(r"as of (\d{4}-\d{2}-\d{2})T")
MAX_OSM_MATCH_DISTANCE_KM = 100.0
OSM_LAYERS = (
    "gis_osm_pois_free",
    "gis_osm_pois_a_free",
    "gis_osm_natural_free",
    "gis_osm_pofw_free",
)
ATTRACTIVE_FEATURES = {
    "archaeological",
    "attraction",
    "beach",
    "castle",
    "cave",
    "christian",
    "hindu",
    "mosque",
    "monument",
    "museum",
    "peak",
    "sikh",
    "theme_park",
    "viewpoint",
    "waterfall",
    "zoo",
}
OSM_CATEGORY_MAP = {
    "archaeological": "history",
    "attraction": "attraction",
    "beach": "beach",
    "castle": "history",
    "cave": "nature",
    "christian": "religious",
    "hindu": "religious",
    "mosque": "religious",
    "monument": "history",
    "museum": "culture",
    "peak": "nature",
    "sikh": "religious",
    "theme_park": "attraction",
    "viewpoint": "nature",
    "waterfall": "nature",
    "zoo": "nature",
}
ATTRACTION_COLUMNS = [
    "attraction_id",
    "name",
    "normalized_name",
    "destination_id",
    "category",
    "subcategory",
    "latitude",
    "longitude",
    "rating",
    "review_count",
    "estimated_cost",
    "currency",
    "estimated_visit_duration_min",
    "popularity",
    "description",
    "source",
    "source_record_id",
    "source_url",
    "source_confidence",
    "coordinate_source",
    "coordinate_status",
    "coordinate_source_url",
    "coordinate_retrieved_at",
    "coordinate_validation_status",
    "category_source_url",
    "category_retrieved_at",
    "category_validation_status",
    "rating_source",
    "rating_source_url",
    "rating_retrieved_at",
    "rating_validation_status",
    "cost_source",
    "cost_source_url",
    "cost_retrieved_at",
    "cost_validation_status",
    "duration_source",
    "duration_source_url",
    "duration_retrieved_at",
    "duration_validation_status",
    "popularity_source_url",
    "popularity_retrieved_at",
    "popularity_validation_status",
    "data_quality_status",
]
HOTEL_COLUMNS = [
    "hotel_id",
    "name",
    "normalized_name",
    "destination_id",
    "latitude",
    "longitude",
    "coordinate_source",
    "coordinate_source_url",
    "coordinate_retrieved_at",
    "coordinate_validation_status",
    "price_per_night",
    "price_source",
    "price_source_url",
    "price_retrieved_at",
    "price_validation_status",
    "currency",
    "rating",
    "rating_source",
    "rating_source_url",
    "rating_retrieved_at",
    "rating_validation_status",
    "review_count",
    "room_type",
    "amenities",
    "address",
    "source",
    "source_record_id",
    "source_url",
    "provenance_source",
    "data_quality_status",
    "destination_match_status",
]


def normalize(value: Any) -> str:
    ascii_value = unicodedata.normalize("NFKD", str(value or ""))
    ascii_value = ascii_value.encode("ascii", "ignore").decode("ascii")
    return " ".join(re.findall(r"[a-z0-9]+", ascii_value.casefold()))


def haversine_km(lat_a: float, lon_a: float, lat_b: float, lon_b: float) -> float:
    radius_km = 6371.0
    p_a, p_b = math.radians(lat_a), math.radians(lat_b)
    delta_lat = math.radians(lat_b - lat_a)
    delta_lon = math.radians(lon_b - lon_a)
    value = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(p_a) * math.cos(p_b) * math.sin(delta_lon / 2) ** 2
    )
    return radius_km * 2 * math.atan2(math.sqrt(value), math.sqrt(1 - value))


def _as_number(value: Any) -> float | None:
    if value is None or pd.isna(value) or str(value).strip() == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _atomic_csv(frame: pd.DataFrame, path: Path) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    frame.to_csv(temporary, index=False, na_rep="", encoding="utf-8")
    temporary.replace(path)


def _load_osm_snapshot_date() -> str:
    contents = OSM_README.read_text(encoding="utf-8")
    match = OSM_SNAPSHOT_RE.search(contents)
    if not match:
        raise ValueError(f"Could not determine the OSM snapshot date from {OSM_README}")
    return match.group(1)


def _existing_db_ids() -> dict[tuple[int, str], list[int]]:
    from app.data.database import SessionLocal
    from app.data.models import Attraction

    db = SessionLocal()
    try:
        return_mapping: dict[tuple[int, str], list[int]] = defaultdict(list)
        rows = db.query(
            Attraction.attraction_id,
            Attraction.destination_id,
            Attraction.name,
        ).all()
        for attraction_id, destination_id, name in rows:
            if attraction_id is None or destination_id is None:
                raise ValueError("An existing attraction is missing its stable ID or destination.")
            return_mapping[
                (int(destination_id), normalize(name))
            ].append(int(attraction_id))
        return dict(return_mapping)
    finally:
        db.close()


def _destination_id_map(destinations: pd.DataFrame) -> dict[str, int]:
    result: dict[str, int] = {}
    for row in destinations.to_dict("records"):
        key = normalize(row["destination_name"])
        if key in result:
            raise ValueError(f"Duplicate normalized destination name: {row['destination_name']}")
        result[key] = int(row["destination_id"])
    return result


def _osm_candidates() -> dict[tuple[int, str], list[dict]]:
    by_name: dict[str, list[dict]] = defaultdict(list)
    for layer in OSM_LAYERS:
        frame = gpd.read_file(OSM_GPKG, layer=layer)
        required = {"osm_id", "fclass", "name", "geometry"}
        if not required.issubset(frame.columns):
            raise ValueError(f"OSM layer {layer} lacks required columns: {required - set(frame.columns)}")
        for row in frame.itertuples(index=False):
            name = getattr(row, "name", None)
            feature_class = str(getattr(row, "fclass", "") or "").casefold()
            if not name or feature_class not in ATTRACTIVE_FEATURES:
                continue
            geometry = getattr(row, "geometry", None)
            if geometry is None or geometry.is_empty:
                continue
            point = geometry if geometry.geom_type == "Point" else geometry.representative_point()
            latitude, longitude = float(point.y), float(point.x)
            by_name[normalize(name)].append({
                "osm_id": str(getattr(row, "osm_id")),
                "layer": layer,
                "feature_class": feature_class,
                "latitude": latitude,
                "longitude": longitude,
                "name": str(name),
                "geometry_method": (
                    "point" if geometry.geom_type == "Point" else "polygon_representative_point"
                ),
            })

    resolved: dict[tuple[int, str], list[dict]] = defaultdict(list)
    # Return all name candidates; destination-specific filtering happens when rows are built.
    for key, values in by_name.items():
        resolved[(0, key)].extend(values)
    return resolved


def _unique_osm_match(
    candidates: list[dict], destination: dict, destination_name: str
) -> tuple[dict | None, str]:
    latitude = _as_number(destination.get("latitude"))
    longitude = _as_number(destination.get("longitude"))
    if latitude is None or longitude is None:
        return None, "unresolved_destination_coordinates_missing"

    matching: dict[tuple[str, float, float], dict] = {}
    for candidate in candidates:
        distance = haversine_km(
            latitude,
            longitude,
            candidate["latitude"],
            candidate["longitude"],
        )
        if distance > MAX_OSM_MATCH_DISTANCE_KM:
            continue
        key = (
            candidate["osm_id"],
            round(candidate["latitude"], 6),
            round(candidate["longitude"], 6),
        )
        current = matching.get(key)
        if current is None or candidate["layer"] < current["layer"]:
            matching[key] = {**candidate, "distance_km": distance}

    if len(matching) == 1:
        return next(iter(matching.values())), "exact_name_unique_within_100km"
    if len(matching) > 1:
        return None, f"ambiguous_exact_name_candidates:{len(matching)}"
    return None, f"no_exact_osm_match_within_100km:{destination_name}"


def prepare_processed_datasets(*, apply: bool = False) -> dict:
    destinations = pd.read_csv(DESTINATIONS_CSV, keep_default_na=False)
    existing_attractions = pd.read_csv(ATTRACTIONS_CSV, keep_default_na=False)
    hotels = pd.read_csv(HOTELS_CSV, keep_default_na=False)
    raw_records = json.loads(TOURISM_JSON.read_text(encoding="utf-8"))
    destination_ids = _destination_id_map(destinations)
    snapshot_date = _load_osm_snapshot_date()
    retrieved_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

    db_ids = _existing_db_ids()
    db_identity_by_id = {
        attraction_id: identity
        for identity, identity_ids in db_ids.items()
        for attraction_id in identity_ids
    }
    osm_by_name = _osm_candidates()
    old_by_identity: dict[tuple[int, str], dict] = {}
    for row in existing_attractions.to_dict("records"):
        name_key = normalize(row.get("name"))
        destination_key = int(row.get("destination_id") or 0)
        if name_key and destination_key:
            old_by_identity.setdefault((destination_key, name_key), row)

    canonical: dict[tuple[int, str], dict] = {}
    for record in raw_records:
        raw_destination = record.get("destination_name", record.get("id", ""))
        destination_id = destination_ids.get(normalize(raw_destination))
        if destination_id is None:
            raise ValueError(f"Raw tourism destination is missing from processed destinations: {raw_destination}")
        for raw_name in record.get("primary_attractions", []):
            name = str(raw_name).strip()
            name_key = normalize(name)
            if not name_key:
                continue
            key = (destination_id, name_key)
            canonical.setdefault(key, {
                "name": name,
                "normalized_name": name.casefold().strip(),
                "destination_id": destination_id,
                "source_record_id": str(record.get("id", "")),
            })

    used_ids: set[int] = set()
    next_id = max(
        max(
            (int(attraction_id) for ids in db_ids.values() for attraction_id in ids),
            default=0,
        ),
        max(
            (
                int(value)
                for value in existing_attractions["attraction_id"]
                if str(value).strip()
            ),
            default=0,
        ),
    ) + 1
    rows: list[dict] = []
    provenance: list[dict] = []
    existing_provenance: dict[tuple[int, str], dict] = {}
    if PROVENANCE_CSV.exists():
        prior_provenance = pd.read_csv(PROVENANCE_CSV, keep_default_na=False)
        for prior in prior_provenance.to_dict("records"):
            try:
                prior_key = (int(prior["entity_id"]), str(prior["field"]))
            except (KeyError, TypeError, ValueError):
                continue
            existing_provenance[prior_key] = prior
    summary = {
        "raw_unique_attractions": len(canonical),
        "coordinates_enriched": 0,
        "categories_enriched": 0,
        "coordinates_preserved": 0,
        "categories_preserved": 0,
        "ambiguous_osm_matches": 0,
        "unmatched_attractions": 0,
        "preserved_verified_fields": 0,
        "hotel_count": len(hotels),
        "hotel_prices_cleared": 0,
        "hotel_ratings_cleared": 0,
        "hotel_coordinates_added": 0,
        "by_destination": defaultdict(lambda: {
            "attractions": 0,
            "coordinates_enriched": 0,
            "categories_enriched": 0,
            "ambiguous_osm_matches": 0,
            "unmatched_attractions": 0,
        }),
    }

    dest_rows = {
        int(row["destination_id"]): row
        for row in destinations.to_dict("records")
    }
    db_destinations = {}
    from app.data.database import SessionLocal
    from app.data.models import Destination

    db = SessionLocal()
    try:
        db_destinations = {
            normalize(destination_name): int(destination_id)
            for destination_id, destination_name in db.query(
                Destination.destination_id,
                Destination.destination_name,
            ).all()
            if destination_id is not None and destination_name
        }
    finally:
        db.close()

    for key, raw in sorted(canonical.items(), key=lambda item: (item[0][0], item[0][1])):
        destination_id, name_key = key
        destination_row = dest_rows[destination_id]
        destination_name = str(destination_row["destination_name"])
        db_destination_id = db_destinations.get(normalize(destination_name), destination_id)
        identity_ids = sorted(db_ids.get((db_destination_id, name_key), []))
        old_row = old_by_identity.get(key, {})
        old_id = _as_number(old_row.get("attraction_id"))
        old_id_value = int(old_id) if old_id is not None else None
        old_id_identity = db_identity_by_id.get(old_id_value) if old_id_value is not None else None
        if (
            old_id_value is not None
            and old_id_value not in used_ids
            and old_id_identity in (None, (db_destination_id, name_key))
        ):
            attraction_id = old_id_value
        else:
            available_ids = [value for value in identity_ids if value not in used_ids]
            if available_ids:
                attraction_id = available_ids[0]
            else:
                while next_id in used_ids:
                    next_id += 1
                attraction_id = next_id
                next_id += 1
        if attraction_id in used_ids:
            raise ValueError(f"Stable attraction ID reused for different records: {attraction_id}")
        used_ids.add(attraction_id)

        from app.data.quality import verified_coordinates, verified_measure

        old_coordinates = verified_coordinates(
            old_row.get("latitude"),
            old_row.get("longitude"),
            old_row.get("coordinate_source"),
            old_row.get("coordinate_status"),
            destination_row.get("latitude"),
            destination_row.get("longitude"),
        )
        if old_coordinates:
            match, match_status = None, "preserved_existing_verified_coordinates"
        else:
            match, match_status = _unique_osm_match(
                osm_by_name.get((0, name_key), []),
                destination_row,
                destination_name,
            )
        rating = _as_number(old_row.get("rating"))
        rating_source = old_row.get("rating_source")
        rating = verified_measure(
            rating,
            rating_source,
            minimum=0,
            maximum=5,
        )
        if rating is not None:
            summary["preserved_verified_fields"] += 1
        else:
            rating = None
            rating_source = ""

        cost = _as_number(old_row.get("estimated_cost"))
        cost_source = old_row.get("cost_source")
        cost = verified_measure(cost, cost_source, minimum=0)
        if cost is not None:
            summary["preserved_verified_fields"] += 1
        else:
            cost = None
            cost_source = ""

        duration = _as_number(old_row.get("estimated_visit_duration_min"))
        duration_source = old_row.get("duration_source")
        duration = verified_measure(duration, duration_source, minimum=1)
        if duration is not None:
            summary["preserved_verified_fields"] += 1
        else:
            duration = None
            duration_source = ""

        category_value = str(old_row.get("category") or "")
        category_source = str(old_row.get("category_source_url") or "")
        if category_value and category_source and not any(
            marker in category_source.casefold()
            for marker in ("estimate", "unverified", "unknown")
        ):
            category = category_value
            subcategory = str(old_row.get("subcategory") or "")
            category_source_url = category_source
            category_retrieved_at = str(old_row.get("category_retrieved_at") or "")
            category_validation = str(
                old_row.get("category_validation_status") or "preserved_verified_category"
            )
        else:
            category = subcategory = ""
            category_source_url = category_retrieved_at = ""
            category_validation = "unavailable_no_verified_category_source"

        if old_coordinates:
            latitude, longitude = old_coordinates
            coordinate_source = str(old_row.get("coordinate_source") or "")
            coordinate_url = str(
                old_row.get("coordinate_source_url") or old_row.get("source_url") or ""
            )
            coordinate_retrieved_at = str(
                old_row.get("coordinate_retrieved_at") or ""
            )
            coordinate_validation = str(
                old_row.get("coordinate_validation_status") or "preserved_verified_coordinates"
            )
            summary["coordinates_enriched"] += 1
            summary["categories_enriched"] += int(bool(category))
            summary["coordinates_preserved"] += 1
            summary["categories_preserved"] += int(bool(category))
            summary["by_destination"][destination_name]["coordinates_enriched"] += 1
            summary["by_destination"][destination_name]["categories_enriched"] += int(
                bool(category)
            )
            coordinate_key = (attraction_id, "latitude,longitude")
            source_parts = coordinate_source.split(";")
            osm_identity = re.search(r"osm_id=(\d+)", coordinate_source)
            snapshot_match = re.search(
                r"snapshot=(\d{4}-\d{2}-\d{2})",
                coordinate_validation,
            )
            source_record_id = (
                f"{source_parts[1].strip()}:{osm_identity.group(1)}"
                if len(source_parts) > 1 and osm_identity
                else ""
            )
            previous_coordinate_provenance = existing_provenance.get(coordinate_key)
            if previous_coordinate_provenance:
                provenance.append(previous_coordinate_provenance)
            else:
                provenance.append({
                    "entity_type": "attraction",
                    "entity_id": attraction_id,
                    "destination": destination_name,
                    "field": "latitude,longitude",
                    "source": coordinate_source,
                    "source_url": coordinate_url,
                    "source_record_id": source_record_id,
                    "source_snapshot_date": snapshot_match.group(1) if snapshot_match else "",
                    "retrieved_at": coordinate_retrieved_at,
                    "validation_status": coordinate_validation,
                })
            if category:
                category_key = (attraction_id, "category,subcategory")
                previous_category_provenance = existing_provenance.get(category_key)
                if previous_category_provenance:
                    provenance.append(previous_category_provenance)
                else:
                    provenance.append({
                        "entity_type": "attraction",
                        "entity_id": attraction_id,
                        "destination": destination_name,
                        "field": "category,subcategory",
                        "source": coordinate_source,
                        "source_url": category_source_url,
                        "source_record_id": source_record_id,
                        "source_snapshot_date": snapshot_match.group(1) if snapshot_match else "",
                        "retrieved_at": category_retrieved_at,
                        "validation_status": category_validation,
                    })
        elif match:
            latitude, longitude = match["latitude"], match["longitude"]
            coordinate_source = (
                f"OpenStreetMap / Geofabrik ODbL 1.0; {match['layer']}; "
                f"osm_id={match['osm_id']}; {match['geometry_method']}"
            )
            coordinate_url = (
                f"{OSM_SOURCE_URL}?mlat={latitude:.6f}&mlon={longitude:.6f}"
                f"#map=18/{latitude:.6f}/{longitude:.6f}"
            )
            coordinate_retrieved_at = retrieved_at
            coordinate_validation = (
                f"verified_exact_name_unique_within_100km;"
                f"snapshot={snapshot_date};distance_km={match['distance_km']:.2f};"
                f"geometry={match['geometry_method']}"
            )
            category = OSM_CATEGORY_MAP[match["feature_class"]]
            subcategory = match["feature_class"]
            category_source_url = coordinate_url
            category_retrieved_at = retrieved_at
            category_validation = "verified_exact_name_unique_osm_feature_class"
            summary["coordinates_enriched"] += 1
            summary["categories_enriched"] += 1
            summary["by_destination"][destination_name]["coordinates_enriched"] += 1
            summary["by_destination"][destination_name]["categories_enriched"] += 1
            provenance.append({
                "entity_type": "attraction",
                "entity_id": attraction_id,
                "destination": destination_name,
                "field": "latitude,longitude",
                "source": "OpenStreetMap / Geofabrik northern-zone.gpkg (ODbL 1.0)",
                "source_url": coordinate_url,
                "source_record_id": f"{match['layer']}:{match['osm_id']}",
                "source_snapshot_date": snapshot_date,
                "retrieved_at": retrieved_at,
                "validation_status": coordinate_validation,
            })
            provenance.append({
                "entity_type": "attraction",
                "entity_id": attraction_id,
                "destination": destination_name,
                "field": "category,subcategory",
                "source": "OpenStreetMap / Geofabrik northern-zone.gpkg (ODbL 1.0)",
                "source_url": coordinate_url,
                "source_record_id": f"{match['layer']}:{match['osm_id']}",
                "source_snapshot_date": snapshot_date,
                "retrieved_at": retrieved_at,
                "validation_status": category_validation,
            })
        else:
            latitude = longitude = None
            coordinate_source = ""
            coordinate_url = ""
            coordinate_retrieved_at = ""
            coordinate_validation = match_status

        if match is None and not old_coordinates and match_status.startswith("ambiguous"):
            summary["ambiguous_osm_matches"] += 1
            summary["by_destination"][destination_name]["ambiguous_osm_matches"] += 1
        elif match is None and not old_coordinates:
            summary["unmatched_attractions"] += 1
            summary["by_destination"][destination_name]["unmatched_attractions"] += 1

        summary["by_destination"][destination_name]["attractions"] += 1
        coordinates_verified = bool(match or old_coordinates)
        rows.append({
            "attraction_id": attraction_id,
            "name": raw["name"],
            "normalized_name": raw["normalized_name"],
            "destination_id": destination_id,
            "category": category,
            "subcategory": subcategory,
            "latitude": latitude,
            "longitude": longitude,
            "rating": rating,
            "review_count": "",
            "estimated_cost": cost,
            "currency": "INR",
            "estimated_visit_duration_min": duration,
            "popularity": "",
            "description": "",
            "source": "india_tourism_dataset.json",
            "source_record_id": raw["source_record_id"],
            "source_url": OSM_SOURCE_URL if match else "",
            "source_confidence": "high" if match else "",
            "coordinate_source": coordinate_source,
            "coordinate_status": "verified" if coordinates_verified else "unresolved",
            "coordinate_source_url": coordinate_url,
            "coordinate_retrieved_at": coordinate_retrieved_at,
            "coordinate_validation_status": coordinate_validation,
            "category_source_url": category_source_url,
            "category_retrieved_at": category_retrieved_at,
            "category_validation_status": category_validation,
            "rating_source": rating_source,
            "rating_source_url": old_row.get("rating_source_url", ""),
            "rating_retrieved_at": old_row.get("rating_retrieved_at", ""),
            "rating_validation_status": (
                old_row.get("rating_validation_status") or "verified"
                if rating is not None else "unavailable_no_authoritative_rating_source"
            ),
            "cost_source": cost_source,
            "cost_source_url": old_row.get("cost_source_url", ""),
            "cost_retrieved_at": old_row.get("cost_retrieved_at", ""),
            "cost_validation_status": (
                old_row.get("cost_validation_status") or "verified"
                if cost is not None else "unavailable_no_authoritative_entry_fee_source"
            ),
            "duration_source": duration_source,
            "duration_source_url": old_row.get("duration_source_url", ""),
            "duration_retrieved_at": old_row.get("duration_retrieved_at", ""),
            "duration_validation_status": (
                old_row.get("duration_validation_status") or "verified"
                if duration is not None else "unavailable_no_authoritative_duration_source"
            ),
            "popularity_source_url": "",
            "popularity_retrieved_at": "",
            "popularity_validation_status": "unavailable_no_reliable_popularity_metric",
            "data_quality_status": (
                "coordinate_verified_osm"
                if match
                else "preserved_verified_values"
                if old_coordinates
                else "missing_unverified_values"
            ),
        })

    # The OYO source has no acquisition date, and its Rating values are not consistently
    # on a 0-5 scale. Keep the property records but do not present either as verified.
    hotel_rows = hotels.to_dict("records")
    for row in hotel_rows:
        price = _as_number(row.get("price_per_night"))
        rating = _as_number(row.get("rating"))
        if price is not None:
            summary["hotel_prices_cleared"] += 1
        if rating is not None:
            summary["hotel_ratings_cleared"] += 1
        address = str(row.get("address") or "")
        address_matches = [
            int(destination["destination_id"])
            for destination in dest_rows.values()
            if _address_matches_destination(
                address,
                str(destination.get("destination_name") or ""),
                str(destination.get("state") or ""),
            )
        ]
        destination_id = address_matches[0] if len(address_matches) == 1 else ""
        row.update({
            "destination_id": destination_id,
            "latitude": "",
            "longitude": "",
            "coordinate_source": "",
            "coordinate_source_url": "",
            "coordinate_retrieved_at": "",
            "coordinate_validation_status": "unavailable_no_exact_verified_property_match",
            "price_per_night": "",
            "price_source": "unverified undated source: OYO_HOTEL_ROOMS.csv::Price",
            "price_source_url": "",
            "price_retrieved_at": "",
            "price_validation_status": "unavailable_source_snapshot_date_not_provided",
            "rating": "",
            "rating_source": "unverified ambiguous source: OYO_HOTEL_ROOMS.csv::Rating",
            "rating_source_url": "",
            "rating_retrieved_at": "",
            "rating_validation_status": "unavailable_source_field_semantics_not_verified",
            "currency": row.get("currency") or "INR",
            "source": row.get("source") or "OYO_HOTEL_ROOMS.csv",
            "destination_match_status": (
                "verified_exact_location_suffix"
                if len(address_matches) == 1
                else "unmatched_or_ambiguous_location"
            ),
            "data_quality_status": "coordinates_unavailable;price_unverified;rating_unverified",
        })
        summary["hotel_coordinates_added"] += int(bool(row.get("latitude")) and bool(row.get("longitude")))
        for column in HOTEL_COLUMNS:
            row.setdefault(column, "")

    attraction_frame = pd.DataFrame(rows, columns=ATTRACTION_COLUMNS)
    hotel_columns = list(dict.fromkeys([*hotels.columns, *HOTEL_COLUMNS]))
    hotel_frame = pd.DataFrame(hotel_rows, columns=hotel_columns)
    provenance_frame = pd.DataFrame(provenance, columns=[
        "entity_type",
        "entity_id",
        "destination",
        "field",
        "source",
        "source_url",
        "source_record_id",
        "source_snapshot_date",
        "retrieved_at",
        "validation_status",
    ])
    summary["by_destination"] = dict(summary["by_destination"])
    summary["osm_snapshot_date"] = snapshot_date
    summary["would_write"] = {
        "attractions": len(attraction_frame),
        "hotels": len(hotel_frame),
        "field_provenance_rows": len(provenance_frame),
    }

    if apply:
        _atomic_csv(attraction_frame, ATTRACTIONS_CSV)
        _atomic_csv(hotel_frame, HOTELS_CSV)
        _atomic_csv(provenance_frame, PROVENANCE_CSV)
        summary["written"] = True
    else:
        summary["written"] = False
    return summary


def _address_matches_destination(address: str, name: str, state: str) -> bool:
    from app.data.quality import address_matches_destination

    return address_matches_destination(address, name, state)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="write the processed CSVs; without this flag, only report planned changes",
    )
    args = parser.parse_args()
    summary = prepare_processed_datasets(apply=args.apply)
    print(json.dumps(summary, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
