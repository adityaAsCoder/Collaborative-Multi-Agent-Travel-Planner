# Collaborative-Multi-Agent-Travel-Planner
# Collaborative Multi-Agent Travel Planner

The project now includes a user-facing CSV-backed travel discovery website. It uses the
processed destination, attraction, and hotel datasets directly so search results do not
depend on an incomplete database migration.

## Run the website

From the repository root:

```powershell
pip install -r requirements.txt
streamlit run app/travel_web.py
```

Create a local account, search by destination/state/country, choose interests, and
generate a day-by-day itinerary. Account passwords are stored as salted PBKDF2 hashes
in the local SQLite database; no external authentication service is required.

The existing development dashboard remains available at `app/dashboard/dashboard.py`.
