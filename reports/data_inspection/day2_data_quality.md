# Day 2 Data Quality Report

## Attractions
- **Total Attractions Extracted:** 308 (from destination list arrays)
- **Attractions mapped:** 15 geocoded via Nominatim
- **Attractions missing coordinates:** 293
- **Attractions with rating / cost / duration:** 0 (Missing entirely from base source)

## Hotels
- **Total Hotels:** 791
- **Hotels with Coordinates:** 15 (geocoded sample out of 791)
- **Hotels without Coordinates:** 776
- **Rating Coverage:** 791
- **Cost Coverage:** 791

## Destinations
- **Destinations covered:** 100
- **Destinations lacking complete data:** 100 (due to Missing cost and visit duration metrics across all destinations)
- **Unresolved records:** ~293 attractions still need geocoding via Nominatim.

## OSM Coverage
- Contains bounding box `(69.14, 23.02, 79.54, 35.56)` which covers Northern India (Delhi, UP, Rajasthan, etc.). Does NOT cover all 100 destinations inherently (e.g. Kerala, Tamil Nadu destinations in the south will fall outside OSM mesh).
