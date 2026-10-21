# Destination Data Quality Audit

Generated from the local SQLite database and processed catalogs. The audit is read-only.

## Data lineage

- Planner/API data source: `travel_planner.db`, populated by `python scripts/populate_db_day2_5.py`.
- CSV-backed discovery catalog: `datasets/processed/destinations.csv`, `datasets/processed/attractions.csv`, and `datasets/processed/hotels.csv`.
- Attraction names and destination assignments originate in `datasets/raw/tourism/india_tourism_dataset.json`.
- Existing hotel names, locations, and raw fields originate in `datasets/raw/hotels/OYO_HOTEL_ROOMS.csv`; its price snapshot date and `Rating` field semantics are not documented.
- Enriched attraction coordinates use exact-name matches from `datasets/osm/northern-zone.gpkg`; the bundle is OpenStreetMap data under ODbL 1.0, snapshot date recorded in `datasets/osm/README`.

## Overall coverage

- Destinations: 93
- Database attractions: 378; source-verified coordinates: 6 (1.6% eligible for destination-anchor distance estimates)
- Attractions with usable text for preference scoring: 378 (100.0%)
- Processed CSV attraction fields with verified values: coordinates 6; fees 0; durations 0; ratings 0
- Hotels: 737; destination-linked hotels with verified coordinates: 0 (0.0%)
- Duplicate attraction records (same destination and normalized name): 0
- Duplicate hotel records (same normalized name and address): 0
- Processed CSV attraction rows: 378; verified entry fees 0; verified durations 0; verified ratings 0

Numeric values tagged as estimates, undated hotel prices, values without field-level provenance, invalid coordinates, and ratings outside 0–5 are not counted as verified. An attraction is preference-scoreable when its name or sourced category text exists; this does not mean it matches every requested interest. Fewer than six attraction records is flagged as insufficient for a six-day plan with one unique place per day.

## Per-destination results

| Destination | Attractions | Verified coords | Missing/unverified coords | Verified categories | Missing categories | Verified fees | Missing/unverified fees | Verified durations | Missing/unverified durations | Verified ratings | Missing/unverified ratings | Preference eligible | Linked hotels | Hotel coords | Usable nightly prices | Accommodation-eligible hotels | <6 attractions | No suitable hotel |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|:---:|:---:|
| Agra | 4 | 0 | 4 | 0 | 4 | 0 | 4 | 0 | 4 | 0 | 4 | 4 | 0 | 0 | 0 | 0 | yes | yes |
| Agumbe & Western Ghats Rainforest Belt | 3 | 0 | 3 | 0 | 3 | 0 | 3 | 0 | 3 | 0 | 3 | 3 | 0 | 0 | 0 | 0 | yes | yes |
| Almora & Kasar Devi Belt | 4 | 0 | 4 | 0 | 4 | 0 | 4 | 0 | 4 | 0 | 4 | 4 | 0 | 0 | 0 | 0 | yes | yes |
| Amarkantak Nature–Spiritual Loop | 3 | 0 | 3 | 0 | 3 | 0 | 3 | 0 | 3 | 0 | 3 | 3 | 0 | 0 | 0 | 0 | yes | yes |
| Amboli Ghat | 3 | 0 | 3 | 0 | 3 | 0 | 3 | 0 | 3 | 0 | 3 | 3 | 0 | 0 | 0 | 0 | yes | yes |
| Amritsar | 4 | 0 | 4 | 0 | 4 | 0 | 4 | 0 | 4 | 0 | 4 | 4 | 0 | 0 | 0 | 0 | yes | yes |
| Araku Valley | 4 | 0 | 4 | 0 | 4 | 0 | 4 | 0 | 4 | 0 | 4 | 4 | 0 | 0 | 0 | 0 | yes | yes |
| Astaranga & Ramachandi Beaches (Odisha Quiet Coast) | 3 | 0 | 3 | 0 | 3 | 0 | 3 | 0 | 3 | 0 | 3 | 3 | 0 | 0 | 0 | 0 | yes | yes |
| Auli (Garhwal Ski & Snow Resort) | 3 | 0 | 3 | 0 | 3 | 0 | 3 | 0 | 3 | 0 | 3 | 3 | 0 | 0 | 0 | 0 | yes | yes |
| Bandhavgarh National Park | 3 | 0 | 3 | 0 | 3 | 0 | 3 | 0 | 3 | 0 | 3 | 3 | 0 | 0 | 0 | 0 | yes | yes |
| Bangaram & Kadmat Islands (Lakshadweep Quiet Beaches) | 3 | 0 | 3 | 0 | 3 | 0 | 3 | 0 | 3 | 0 | 3 | 3 | 0 | 0 | 0 | 0 | yes | yes |
| Binsar | 3 | 0 | 3 | 0 | 3 | 0 | 3 | 0 | 3 | 0 | 3 | 3 | 0 | 0 | 0 | 0 | yes | yes |
| Bodh Gaya Buddhist Circuit Hub | 3 | 0 | 3 | 0 | 3 | 0 | 3 | 0 | 3 | 0 | 3 | 3 | 0 | 0 | 0 | 0 | yes | yes |
| Chakrata | 3 | 0 | 3 | 0 | 3 | 0 | 3 | 0 | 3 | 0 | 3 | 3 | 0 | 0 | 0 | 0 | yes | yes |
| Cherrapunji & Mawsmai Area (Sohra region) | 4 | 0 | 4 | 0 | 4 | 0 | 4 | 0 | 4 | 0 | 4 | 4 | 0 | 0 | 0 | 0 | yes | yes |
| Chikmagalur | 4 | 0 | 4 | 0 | 4 | 0 | 4 | 0 | 4 | 0 | 4 | 4 | 0 | 0 | 0 | 0 | yes | yes |
| Chitkul & Baspa Valley | 3 | 0 | 3 | 0 | 3 | 0 | 3 | 0 | 3 | 0 | 3 | 3 | 0 | 0 | 0 | 0 | yes | yes |
| Chitrakote Falls | 3 | 0 | 3 | 0 | 3 | 0 | 3 | 0 | 3 | 0 | 3 | 3 | 0 | 0 | 0 | 0 | yes | yes |
| Coorg (Kodagu) | 9 | 0 | 9 | 0 | 9 | 0 | 9 | 0 | 9 | 0 | 9 | 9 | 0 | 0 | 0 | 0 | no | yes |
| Darjeeling | 4 | 0 | 4 | 0 | 4 | 0 | 4 | 0 | 4 | 0 | 4 | 4 | 0 | 0 | 0 | 0 | yes | yes |
| Dawki & Shnongpdeng | 3 | 0 | 3 | 0 | 3 | 0 | 3 | 0 | 3 | 0 | 3 | 3 | 0 | 0 | 0 | 0 | yes | yes |
| Dhanushkodi (Ghost Town & Beach) | 4 | 0 | 4 | 0 | 4 | 0 | 4 | 0 | 4 | 0 | 4 | 4 | 0 | 0 | 0 | 0 | yes | yes |
| Dharamshala & McLeod Ganj | 5 | 0 | 5 | 0 | 5 | 0 | 5 | 0 | 5 | 0 | 5 | 5 | 0 | 0 | 0 | 0 | yes | yes |
| Gangtok & East Sikkim | 4 | 0 | 4 | 0 | 4 | 0 | 4 | 0 | 4 | 0 | 4 | 4 | 0 | 0 | 0 | 0 | yes | yes |
| Goa | 6 | 0 | 6 | 0 | 6 | 0 | 6 | 0 | 6 | 0 | 6 | 6 | 0 | 0 | 0 | 0 | no | yes |
| Gokarna | 7 | 0 | 7 | 0 | 7 | 0 | 7 | 0 | 7 | 0 | 7 | 7 | 0 | 0 | 0 | 0 | no | yes |
| Great Rann of Kutch (White Desert) | 4 | 0 | 4 | 0 | 4 | 0 | 4 | 0 | 4 | 0 | 4 | 4 | 0 | 0 | 0 | 0 | yes | yes |
| Gulmarg (Kashmir Ski & Snow Destination) | 3 | 0 | 3 | 0 | 3 | 0 | 3 | 0 | 3 | 0 | 3 | 3 | 0 | 0 | 0 | 0 | yes | yes |
| Hampi | 5 | 0 | 5 | 0 | 5 | 0 | 5 | 0 | 5 | 0 | 5 | 5 | 0 | 0 | 0 | 0 | yes | yes |
| Hampi & Pattadakal (UNESCO Vijayanagara–Chalukya Circuit) | 4 | 0 | 4 | 0 | 4 | 0 | 4 | 0 | 4 | 0 | 4 | 4 | 0 | 0 | 0 | 0 | yes | yes |
| Haridwar | 4 | 0 | 4 | 0 | 4 | 0 | 4 | 0 | 4 | 0 | 4 | 4 | 0 | 0 | 0 | 0 | yes | yes |
| Haridwar–Rishikesh–Char Dham Spiritual Trail (Meta‑Circuit Node) | 3 | 0 | 3 | 0 | 3 | 0 | 3 | 0 | 3 | 0 | 3 | 3 | 0 | 0 | 0 | 0 | yes | yes |
| Havelock Island (Swaraj Dweep) | 7 | 0 | 7 | 0 | 7 | 0 | 7 | 0 | 7 | 0 | 7 | 7 | 0 | 0 | 0 | 0 | no | yes |
| Hidden Goa Coves (Butterfly & Nearby Beaches) | 3 | 0 | 3 | 0 | 3 | 0 | 3 | 0 | 3 | 0 | 3 | 3 | 0 | 0 | 0 | 0 | yes | yes |
| Jaipur | 6 | 3 | 3 | 3 | 3 | 0 | 6 | 0 | 6 | 0 | 6 | 6 | 0 | 0 | 0 | 0 | no | yes |
| Jaisalmer & Thar Desert Dunes | 4 | 0 | 4 | 0 | 4 | 0 | 4 | 0 | 4 | 0 | 4 | 4 | 0 | 0 | 0 | 0 | yes | yes |
| Jaisalmer (Thar Desert & Fort Town) | 4 | 0 | 4 | 0 | 4 | 0 | 4 | 0 | 4 | 0 | 4 | 4 | 0 | 0 | 0 | 0 | yes | yes |
| Jibhi & Tirthan Valley | 3 | 0 | 3 | 0 | 3 | 0 | 3 | 0 | 3 | 0 | 3 | 3 | 0 | 0 | 0 | 0 | yes | yes |
| Kalpeni Island (Lakshadweep) | 3 | 0 | 3 | 0 | 3 | 0 | 3 | 0 | 3 | 0 | 3 | 3 | 0 | 0 | 0 | 0 | yes | yes |
| Kanatal | 3 | 0 | 3 | 0 | 3 | 0 | 3 | 0 | 3 | 0 | 3 | 3 | 0 | 0 | 0 | 0 | yes | yes |
| Kanha National Park | 3 | 0 | 3 | 0 | 3 | 0 | 3 | 0 | 3 | 0 | 3 | 3 | 0 | 0 | 0 | 0 | yes | yes |
| Kanyakumari | 6 | 0 | 6 | 0 | 6 | 0 | 6 | 0 | 6 | 0 | 6 | 6 | 0 | 0 | 0 | 0 | no | yes |
| Kaziranga National Park & Assam Tea Belt | 4 | 0 | 4 | 0 | 4 | 0 | 4 | 0 | 4 | 0 | 4 | 4 | 0 | 0 | 0 | 0 | yes | yes |
| Keoladeo National Park (Bharatpur Bird Sanctuary) | 3 | 0 | 3 | 0 | 3 | 0 | 3 | 0 | 3 | 0 | 3 | 3 | 0 | 0 | 0 | 0 | yes | yes |
| Kerala Backwaters (Alappuzha & Kumarakom) | 4 | 0 | 4 | 0 | 4 | 0 | 4 | 0 | 4 | 0 | 4 | 4 | 0 | 0 | 0 | 0 | yes | yes |
| Khajjiar | 3 | 0 | 3 | 0 | 3 | 0 | 3 | 0 | 3 | 0 | 3 | 3 | 0 | 0 | 0 | 0 | yes | yes |
| Khajuraho & Panna National Park | 4 | 0 | 4 | 0 | 4 | 0 | 4 | 0 | 4 | 0 | 4 | 4 | 0 | 0 | 0 | 0 | yes | yes |
| Krang Suri Falls | 2 | 0 | 2 | 0 | 2 | 0 | 2 | 0 | 2 | 0 | 2 | 2 | 0 | 0 | 0 | 0 | yes | yes |
| Krishna Heritage Circuit (Mathura–Vrindavan–Dwarka Focus) | 3 | 0 | 3 | 0 | 3 | 0 | 3 | 0 | 3 | 0 | 3 | 3 | 0 | 0 | 0 | 0 | yes | yes |
| Kudremukh & Surrounding Ghats | 3 | 0 | 3 | 0 | 3 | 0 | 3 | 0 | 3 | 0 | 3 | 3 | 0 | 0 | 0 | 0 | yes | yes |
| Kutch Interior Circuit (Bhuj–Mandvi–Villages) | 4 | 0 | 4 | 0 | 4 | 0 | 4 | 0 | 4 | 0 | 4 | 4 | 0 | 0 | 0 | 0 | yes | yes |
| Ladakh (Leh) | 7 | 2 | 5 | 2 | 5 | 0 | 7 | 0 | 7 | 0 | 7 | 7 | 0 | 0 | 0 | 0 | no | yes |
| Lakshadweep (Agatti–Bangaram–Kadmat circuit) | 4 | 0 | 4 | 0 | 4 | 0 | 4 | 0 | 4 | 0 | 4 | 4 | 0 | 0 | 0 | 0 | yes | yes |
| Mahabaleshwar & Panchgani | 4 | 0 | 4 | 0 | 4 | 0 | 4 | 0 | 4 | 0 | 4 | 4 | 0 | 0 | 0 | 0 | yes | yes |
| Majuli Island | 3 | 0 | 3 | 0 | 3 | 0 | 3 | 0 | 3 | 0 | 3 | 3 | 0 | 0 | 0 | 0 | yes | yes |
| Malanad–Malabar Backwater & Rural Belt | 3 | 0 | 3 | 0 | 3 | 0 | 3 | 0 | 3 | 0 | 3 | 3 | 0 | 0 | 0 | 0 | yes | yes |
| Mamallapuram (Mahabalipuram) & Coromandel Heritage Coast | 4 | 0 | 4 | 0 | 4 | 0 | 4 | 0 | 4 | 0 | 4 | 4 | 0 | 0 | 0 | 0 | yes | yes |
| Manali | 5 | 0 | 5 | 0 | 5 | 0 | 5 | 0 | 5 | 0 | 5 | 5 | 0 | 0 | 0 | 0 | yes | yes |
| Maravanthe & Karnataka Offbeat Coast | 3 | 0 | 3 | 0 | 3 | 0 | 3 | 0 | 3 | 0 | 3 | 3 | 0 | 0 | 0 | 0 | yes | yes |
| Mawlynnong & nearby (including Living Root Bridges region) | 3 | 0 | 3 | 0 | 3 | 0 | 3 | 0 | 3 | 0 | 3 | 3 | 0 | 0 | 0 | 0 | yes | yes |
| Meghalaya (Shillong–Cherrapunji–Mawlynnong circuit) | 4 | 0 | 4 | 0 | 4 | 0 | 4 | 0 | 4 | 0 | 4 | 4 | 0 | 0 | 0 | 0 | yes | yes |
| Miyar Valley | 3 | 0 | 3 | 0 | 3 | 0 | 3 | 0 | 3 | 0 | 3 | 3 | 0 | 0 | 0 | 0 | yes | yes |
| Munnar | 5 | 0 | 5 | 0 | 5 | 0 | 5 | 0 | 5 | 0 | 5 | 5 | 0 | 0 | 0 | 0 | yes | yes |
| Munsiyari | 3 | 0 | 3 | 0 | 3 | 0 | 3 | 0 | 3 | 0 | 3 | 3 | 0 | 0 | 0 | 0 | yes | yes |
| Nal Sarovar Bird Sanctuary | 3 | 0 | 3 | 0 | 3 | 0 | 3 | 0 | 3 | 0 | 3 | 3 | 0 | 0 | 0 | 0 | yes | yes |
| Neil Island (Shaheed Dweep) | 8 | 0 | 8 | 0 | 8 | 0 | 8 | 0 | 8 | 0 | 8 | 8 | 0 | 0 | 0 | 0 | no | yes |
| North Sikkim (Lachung–Lachen Belt) | 4 | 0 | 4 | 0 | 4 | 0 | 4 | 0 | 4 | 0 | 4 | 4 | 0 | 0 | 0 | 0 | yes | yes |
| Nubra Valley | 4 | 0 | 4 | 0 | 4 | 0 | 4 | 0 | 4 | 0 | 4 | 4 | 0 | 0 | 0 | 0 | yes | yes |
| Ooty (Udhagamandalam) | 5 | 0 | 5 | 0 | 5 | 0 | 5 | 0 | 5 | 0 | 5 | 5 | 0 | 0 | 0 | 0 | yes | yes |
| Orchha & Nearby Betwa Landscapes | 4 | 0 | 4 | 0 | 4 | 0 | 4 | 0 | 4 | 0 | 4 | 4 | 0 | 0 | 0 | 0 | yes | yes |
| Pangong Lake (Pangong Tso) | 3 | 0 | 3 | 0 | 3 | 0 | 3 | 0 | 3 | 0 | 3 | 3 | 0 | 0 | 0 | 0 | yes | yes |
| Pondicherry (Puducherry) | 5 | 0 | 5 | 0 | 5 | 0 | 5 | 0 | 5 | 0 | 5 | 5 | 0 | 0 | 0 | 0 | yes | yes |
| Port Blair & Nearby Islands | 4 | 0 | 4 | 0 | 4 | 0 | 4 | 0 | 4 | 0 | 4 | 4 | 0 | 0 | 0 | 0 | yes | yes |
| Rameswaram & Pamban Coast (Sacred Water Walk) | 3 | 0 | 3 | 0 | 3 | 0 | 3 | 0 | 3 | 0 | 3 | 3 | 0 | 0 | 0 | 0 | yes | yes |
| Ranganathittu Bird Sanctuary | 3 | 0 | 3 | 0 | 3 | 0 | 3 | 0 | 3 | 0 | 3 | 3 | 0 | 0 | 0 | 0 | yes | yes |
| Rann of Kutch (White Desert, Dhordo) | 4 | 0 | 4 | 0 | 4 | 0 | 4 | 0 | 4 | 0 | 4 | 4 | 0 | 0 | 0 | 0 | yes | yes |
| Ranthambore National Park | 3 | 0 | 3 | 0 | 3 | 0 | 3 | 0 | 3 | 0 | 3 | 3 | 0 | 0 | 0 | 0 | yes | yes |
| Rishikesh | 4 | 0 | 4 | 0 | 4 | 0 | 4 | 0 | 4 | 0 | 4 | 4 | 0 | 0 | 0 | 0 | yes | yes |
| Rishikesh & Haridwar (Himalayan Yoga Route) | 4 | 0 | 4 | 0 | 4 | 0 | 4 | 0 | 4 | 0 | 4 | 4 | 0 | 0 | 0 | 0 | yes | yes |
| Shillong | 4 | 0 | 4 | 0 | 4 | 0 | 4 | 0 | 4 | 0 | 4 | 4 | 0 | 0 | 0 | 0 | yes | yes |
| Shimla | 6 | 1 | 5 | 1 | 5 | 0 | 6 | 0 | 6 | 0 | 6 | 6 | 0 | 0 | 0 | 0 | no | yes |
| Spiti Valley | 9 | 0 | 9 | 0 | 9 | 0 | 9 | 0 | 9 | 0 | 9 | 9 | 0 | 0 | 0 | 0 | no | yes |
| Tadoba Andhari Tiger Reserve | 3 | 0 | 3 | 0 | 3 | 0 | 3 | 0 | 3 | 0 | 3 | 3 | 0 | 0 | 0 | 0 | yes | yes |
| Tamhini Ghat & Mulshi | 3 | 0 | 3 | 0 | 3 | 0 | 3 | 0 | 3 | 0 | 3 | 3 | 0 | 0 | 0 | 0 | yes | yes |
| Tawang | 8 | 0 | 8 | 0 | 8 | 0 | 8 | 0 | 8 | 0 | 8 | 8 | 0 | 0 | 0 | 0 | no | yes |
| Tiruvannamalai & Arunachala (Inner Fire Journey) | 3 | 0 | 3 | 0 | 3 | 0 | 3 | 0 | 3 | 0 | 3 | 3 | 0 | 0 | 0 | 0 | yes | yes |
| Udaipur | 5 | 0 | 5 | 0 | 5 | 0 | 5 | 0 | 5 | 0 | 5 | 5 | 0 | 0 | 0 | 0 | yes | yes |
| Unakoti & North Tripura Heritage Belt | 3 | 0 | 3 | 0 | 3 | 0 | 3 | 0 | 3 | 0 | 3 | 3 | 0 | 0 | 0 | 0 | yes | yes |
| Varanasi (Kashi) | 10 | 0 | 10 | 0 | 10 | 0 | 10 | 0 | 10 | 0 | 10 | 10 | 0 | 0 | 0 | 0 | no | yes |
| Varanasi Ganga Ghats Pilgrimage | 4 | 0 | 4 | 0 | 4 | 0 | 4 | 0 | 4 | 0 | 4 | 4 | 0 | 0 | 0 | 0 | yes | yes |
| Varkala | 4 | 0 | 4 | 0 | 4 | 0 | 4 | 0 | 4 | 0 | 4 | 4 | 0 | 0 | 0 | 0 | yes | yes |
| Wayanad | 4 | 0 | 4 | 0 | 4 | 0 | 4 | 0 | 4 | 0 | 4 | 4 | 0 | 0 | 0 | 0 | yes | yes |
| Ziro Valley | 3 | 0 | 3 | 0 | 3 | 0 | 3 | 0 | 3 | 0 | 3 | 3 | 0 | 0 | 0 | 0 | yes | yes |

## Interpretation

- Attraction `Verified coords` requires in-range India coordinates, a resolved/verified status, a non-estimate source, and a location within 300 km of the destination anchor.
- Hotel selection requires a reliable destination ID or exact normalized city/region address match, verified local coordinates, and a positive nightly price.
- Missing/unverified attraction fees, durations, ratings, and hotel prices remain unavailable; the planner does not infer free entry, default visit length, current nightly prices, or ratings.
- Transportation is a straight-line estimate only when both endpoints are verified. It is not road routing or a live fare.
