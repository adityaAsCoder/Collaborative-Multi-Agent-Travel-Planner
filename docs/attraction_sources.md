# Attraction Sources

1. **Tourism Source Text:** Open dataset `india_tourism_dataset.json` used for extracting base names.
2. **Nominatim (OpenStreetMap):** Used to retrieve deterministic geocodings for hotel string names and attraction string names.
    - URL: https://nominatim.openstreetmap.org/search
    - Purpose: Reverse geocode raw string references into coordinates.
    - Usage: Automated python calls limited to 1 qps as per the terms of service.
3. **OSM Geometry Cache:** `northern-zone.gpkg` for routing.
