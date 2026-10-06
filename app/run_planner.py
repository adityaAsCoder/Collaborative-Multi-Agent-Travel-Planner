import json
from app.schemas.planning import PlanningRequest
from app.agents.implementations import PlannerAgent

def main():
    print("Initializing Collaborative Multi-Agent Travel Planner...")
    print()

    req = PlanningRequest(
        destination="Jaipur",
        duration=3,
        travelers=2,
        budget=20000,
        currency="INR",
        interests=["Forts", "History", "Food"],
        accommodation_preference="standard"
    )

    print("--- PlanningRequest ---")
    print(f"  Destination: {req.destination}")
    print(f"  Duration: {req.duration} days")
    print(f"  Travelers: {req.travelers}")
    print(f"  Budget: {req.budget} {req.currency}")
    print(f"  Interests: {', '.join(req.interests)}")
    print(f"  Accommodation preference: {req.accommodation_preference}")
    print()

    agent = PlannerAgent()
    state = agent.run(req)

    if state.validation_result and "error" in state.validation_result:
        print(f"FAILED TO PLAN: {state.validation_result['error']}")
        return

    # --- Agent trace ---
    print("--- Research Agent ---")
    print(f"  Attractions retrieved: {len(state.candidate_attractions)}")
    for a in state.candidate_attractions:
        coords = f"({a['latitude']}, {a['longitude']})" if a.get('latitude') else "(no coords)"
        print(f"    [{a['id']}] {a['name']} | {a['category'] or 'uncategorized'} | cost={a['cost']} | dur={a['duration']}min | {coords}")
    print()

    print("--- Preference Agent ---")
    print(f"  Scored attractions: {len(state.preference_scores)}")
    for aid, score in sorted(state.preference_scores.items(), key=lambda x: x[1], reverse=True):
        name = next((a['name'] for a in state.candidate_attractions if a['id'] == aid), '?')
        print(f"    [{aid}] {name}: {score}")
    print()

    print("--- Accommodation Agent ---")
    print(f"  Hotels with valid coordinates: {len(state.candidate_hotels)}")
    if state.candidate_hotels:
        for h in state.candidate_hotels:
            print(f"    [{h['id']}] {h['name']} | price={h['price']} | rating={h['rating']} | ({h['latitude']}, {h['longitude']})")
    else:
        print("    Status: UNAVAILABLE — no hotels for this destination have validated coordinates.")
    print()

    print("--- Optimization Agent ---")
    itinerary = state.optimized_itinerary
    all_att_ids = []
    for day in itinerary:
        for leg in day.get('legs', []):
            all_att_ids.append(leg['attraction']['id'])
    print(f"  Total attractions scheduled: {len(all_att_ids)}")
    print(f"  Unique attraction IDs: {len(set(all_att_ids))} (duplicates: {len(all_att_ids) - len(set(all_att_ids))})")
    per_day_counts = [len(day.get('legs', [])) for day in itinerary]
    print(f"  Attractions per day: {per_day_counts}")
    print()

    print("--- Transport Agent ---")
    for day in itinerary:
        legs = day.get('legs', [])
        if legs:
            for leg in legs:
                tr = leg['transport']
                print(f"  Day {day['day']}: {leg['attraction']['name']} — {tr['distance_km']}km, {tr['time_min']}min, cost={tr['cost']} ({tr['status']})")
    print()

    print("--- Budget Agent ---")
    br = state.budget_result
    print(f"  Accommodation cost: {br['accommodation_cost']} {req.currency}")
    print(f"  Attraction cost:    {br['attraction_cost']} {req.currency}")
    print(f"  Transport cost:     {br['transport_cost']} {req.currency}")
    print(f"  Daily average:      {br['daily_cost']} {req.currency}")
    print(f"  Total estimated:    {br['total_estimated_cost']} {req.currency}")
    print(f"  Remaining budget:   {br['remaining_budget']} {req.currency}")
    print()

    print("--- Constraint Agent ---")
    cr = state.constraint_result
    if cr['feasible']:
        print("  Status: FEASIBLE — all constraints satisfied")
    else:
        print("  Status: VIOLATED")
        for v in cr['violations']:
            print(f"    - {v}")
    print()

    # --- Final itinerary ---
    print("==================================================")
    print("         PERSONALIZED TRAVEL ITINERARY")
    print("==================================================")
    print()
    print(f"Destination:  {req.destination}")
    print(f"Duration:     {req.duration} days")
    print(f"Travelers:    {req.travelers}")
    print(f"Budget:       {req.budget} {req.currency}")
    print(f"Interests:    {', '.join(req.interests)}")
    print()

    for day in itinerary:
        print(f"--- DAY {day['day']} ---")
        hotel_status = day.get('hotel_status', 'unknown')
        if day.get('hotel'):
            h = day['hotel']
            print(f"  Accommodation: {h['name']} ({h['price']} {req.currency}/night, rating {h['rating']})")
        else:
            print(f"  Accommodation: UNAVAILABLE (no geocoded hotels for {req.destination})")

        if day.get('legs'):
            for idx, leg in enumerate(day['legs'], 1):
                att = leg['attraction']
                tr = leg['transport']
                print(f"  {idx}. {att['name']} ({att['category'] or 'uncategorized'})")
                print(f"     Visit duration: {att['duration']} minutes")
                print(f"     Entry cost:     {att['cost']} {req.currency}")
                if tr['status'] == 'calculated':
                    print(f"     Travel:         {tr['distance_km']} km, ~{tr['time_min']} min (cost {tr['cost']} {req.currency})")
                else:
                    print(f"     Travel:         {tr['status']}")
        else:
            note = day.get('note', 'No activities')
            print(f"  [{note}]")
        print()

    print("==================================================")
    print(f"TOTAL COST:          {br['total_estimated_cost']} {req.currency}")
    print(f"REMAINING BUDGET:    {br['remaining_budget']} {req.currency}")
    status_str = "FEASIBLE" if cr['feasible'] else f"VIOLATED ({', '.join(cr['violations'])})"
    print(f"CONSTRAINT STATUS:   {status_str}")
    total_pref = sum(state.preference_scores.values())
    print(f"PREFERENCE SCORE:    {total_pref}")
    print(f"OPTIMIZATION STATUS: Completed")
    print("==================================================")

if __name__ == "__main__":
    main()
