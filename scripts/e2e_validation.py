import requests
import json

BASE = "http://127.0.0.1:8000"
TEST_EMAIL = "test_demo@wanderwise.test"
TEST_PW = "Demo@12345"

print("=== STEP 1: REGISTER ===")
r = requests.post(f"{BASE}/auth/register", json={"email": TEST_EMAIL, "password": TEST_PW})
print(f"Status: {r.status_code}  Response: {r.json()}")

print()
print("=== STEP 2: LOGIN ===")
r = requests.post(f"{BASE}/auth/login", json={"email": TEST_EMAIL, "password": TEST_PW})
print(f"Status: {r.status_code}  Response: {r.json()}")

print()
print("=== STEP 3: LIST DESTINATIONS (check Jaipur) ===")
r = requests.get(f"{BASE}/destinations", params={"search": "Jaipur"})
dests = r.json()
print(f"Status: {r.status_code}  Found: {len(dests)} destinations")
for d in dests:
    print(f"  id={d['id']} | {d['name']} | {d['state']}")

print()
print("=== STEP 4: PLAN JAIPUR TRIP ===")
payload = {
    "email": TEST_EMAIL,
    "destination": "Jaipur",
    "duration": 3,
    "travelers": 2,
    "budget": 20000,
    "currency": "INR",
    "interests": ["Forts", "History", "Food"],
    "accommodation_preference": "standard",
}
r = requests.post(f"{BASE}/plan", json=payload, timeout=60)
print(f"Status: {r.status_code}")
result = r.json()
print(f"Trip ID: {result.get('trip_id')}")
print(f"Preference Score: {result.get('preference_score')}")
print(f"Validation Error: {result.get('validation_error')}")

print()
print("=== STEP 5: VERIFY ITINERARY CONTENT ===")
for day in result.get("itinerary", []):
    atts = [leg["attraction"]["name"] for leg in day.get("legs", [])]
    hotel_status = day.get("hotel_status", "unknown")
    note = day.get("note", "")
    print(f"  Day {day['day']}: {atts} | hotel_status={hotel_status} note={repr(note)}")

print()
print("=== STEP 6: BUDGET BREAKDOWN ===")
br = result.get("budget", {})
print(f"  Accommodation cost: {br.get('accommodation_cost')}")
print(f"  Attraction cost:    {br.get('attraction_cost')}")
print(f"  Transport cost:     {br.get('transport_cost')}")
print(f"  Total estimated:    {br.get('total_estimated_cost')}")
print(f"  Remaining budget:   {br.get('remaining_budget')}")

print()
print("=== STEP 7: CONSTRAINT STATUS ===")
cr = result.get("constraints", {})
print(f"  Feasible: {cr.get('feasible')}")
print(f"  Violations: {cr.get('violations')}")

print()
print("=== STEP 8: VERIFY ACCOMMODATION UNAVAILABLE ===")
hotels = result.get("candidate_hotels", [])
print(f"  Hotels with valid coords: {len(hotels)}")
for day in result.get("itinerary", []):
    if day.get("hotel"):
        print(f"  FAIL: Day {day['day']} has a fabricated hotel")
    else:
        print(f"  PASS: Day {day['day']} has no hotel, hotel_status={day.get('hotel_status')}")

print()
print("=== STEP 9: TRIP HISTORY ===")
r = requests.get(f"{BASE}/trips/{TEST_EMAIL}")
trips = r.json()
print(f"Status: {r.status_code}  Trips stored: {len(trips)}")
for t in trips[:2]:
    dest = t["request"]["destination"]
    created = t["created_at"][:10]
    print(f"  trip_id={t['trip_id']}  dest={dest}  created={created}")

print()
print("=== ALL CHECKS COMPLETE ===")
