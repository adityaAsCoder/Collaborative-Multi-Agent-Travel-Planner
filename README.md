# Collaborative-Multi-Agent-Travel-Planner
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
