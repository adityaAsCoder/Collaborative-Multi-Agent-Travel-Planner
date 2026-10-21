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
