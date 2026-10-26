# Collaborative Multi-Agent Travel Planner

The project now includes a user-facing CSV-backed travel discovery website. It uses the
processed destination, attraction, and hotel datasets directly so search results do not
depend on an incomplete database migration.

## Run the website

### React frontend and FastAPI backend

From the repository root, run the launcher whenever you want to start the complete
application:

```powershell
powershell -ExecutionPolicy Bypass -File .\run_project.ps1
```

It starts the backend at `http://127.0.0.1:8000` and the React frontend at
`http://127.0.0.1:5173`. The API documentation is available at
`http://127.0.0.1:8000/docs`.

From the repository root:

```powershell
pip install -r requirements.txt
streamlit run app/travel_web.py
```

Create a local account, search by destination/state/country, choose interests, and
generate a day-by-day itinerary. Account passwords are stored as salted PBKDF2 hashes
in the local SQLite database; no external authentication service is required.

The existing development dashboard remains available at `app/dashboard/dashboard.py`.

## Data sources and refresh

The planner API reads `travel_planner.db`; the CSV-backed discovery website reads
the processed catalogs directly. CSV changes therefore do not update the planner
database until the import is run. The attraction names and destination assignments
are sourced from `datasets/raw/tourism/india_tourism_dataset.json`. Hotel records
originate in `datasets/raw/hotels/OYO_HOTEL_ROOMS.csv`.

Preview the offline enrichment without changing files:

```powershell
python scripts/enrich_processed_datasets.py
```

Apply the proposed changes to the processed catalogs, update SQLite, and generate
the destination coverage report:

```powershell
python scripts/process_day2_5.py
```

The wrapper preserves raw datasets, uses an idempotent transactional import, and
does not reset accounts, saved trips, or their foreign-key records. To run only an
individual stage, use:

```powershell
python scripts/enrich_processed_datasets.py --apply
python scripts/populate_db_day2_5.py
python scripts/audit_data_quality.py
```

Enrichment only retains values supported by field-level evidence. The current
offline coordinate enrichment uses exact-name matches from
`datasets/osm/northern-zone.gpkg`, an OpenStreetMap-derived bundle under ODbL 1.0
(attribution: © OpenStreetMap contributors; see `datasets/osm/README` for bundle
and snapshot details). This regional snapshot does not cover every destination.
The existing OYO hotel prices are undated, its rating-field semantics are
undocumented, and the local OSM snapshot did not provide exact hotel-property
matches; those values remain unavailable rather than being presented as verified
prices, ratings, or locations. The generated
`reports/data_inspection/data_quality_audit.md` reports coverage and remaining
gaps by destination. Do not interpret an incomplete budget as spendable remaining
money or as live hotel availability.

## Cost estimates and demonstration data

The planner calculates entry fees, transportation, and accommodation through the
shared `app/agents/cost_estimator.py` module. Attraction fees are multiplied by
travellers unless a record explicitly identifies a group charge. Accommodation
estimates require both nightly pricing and known room occupancy; synthetic sample
properties include an illustrative occupancy of two. An incomplete budget still
shows the arithmetic difference from known costs, but identifies it as not
spendable remaining money.

Without a routing provider, transportation uses validated coordinates to derive a
Haversine straight-line distance. It is explicitly not a road distance. The
illustrative car/taxi calculation is distance in kilometres multiplied by the
configurable rate in `datasets/demo/demo_transport.json` (default ₹12/km); the
duration estimate uses its configurable speed (default 30 km/h). Override these
for the backend process with `WANDERWISE_TRANSPORT_COST_PER_KM` and
`WANDERWISE_ESTIMATED_SPEED_KMH`. These are not live fares or verified market
prices.
The current dataset and configured rates are INR-only; other currencies are
rejected rather than relabelled or silently converted.

Demonstration records are stored separately in `datasets/demo/demo_hotels.csv`
and `datasets/demo/demo_attractions.csv`. They are enabled by default for 20
destinations: Goa, Ladakh (Leh), Jaipur, Varanasi, Agra, Udaipur, Kerala
Backwaters, Shimla, Coorg, Ziro Valley, Dharamshala & McLeod Ganj, Manali,
Tawang, Spiti Valley, Nubra Valley, Ooty, Munnar, Kanyakumari, Hampi, and
Pondicherry. Each has three attraction recommendations with illustrative
free/paid entry fees and visit durations, plus an illustrative sample stay.
The planner includes the available sample details and estimates in the
demonstration itinerary and budget. These are synthetic records, not real
property listings, verified fees, actual attraction coordinates, live prices,
or bookings. The interface labels the attraction, accommodation, and budget
values as demonstration data. To disable the demo accommodation and attraction
records, set this in PowerShell before starting the backend:

```powershell
$env:WANDERWISE_DEMO_HOTELS = "false"
$env:WANDERWISE_DEMO_ATTRACTIONS = "false"
powershell -ExecutionPolicy Bypass -File .\run_project.ps1
```

To restore the default demonstration behavior, clear these switches before
starting the app:

```powershell
Remove-Item Env:WANDERWISE_DEMO_HOTELS -ErrorAction SilentlyContinue
Remove-Item Env:WANDERWISE_DEMO_ATTRACTIONS -ErrorAction SilentlyContinue
Remove-Item Env:WANDERWISE_DEMO_DATA -ErrorAction SilentlyContinue
powershell -ExecutionPolicy Bypass -File .\run_project.ps1
```

`WANDERWISE_DEMO_DATA=true` separately marks configured transport costs as
demonstration data; without it, transport costs remain labeled estimates.

Demo attraction coordinates are illustrative offsets from each sourced
destination reference point, not actual attraction coordinates. Demo property
locations also use the destination reference point, not real addresses. The app
labels these values and sample fees as demonstration data; do not use them as
verified travel prices, property listings, directions, or bookings.
