import math
from typing import Any, Dict, List
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.agents.base import (
    ResearchAgentContract, PreferenceAgentContract, AccommodationAgentContract,
    TransportAgentContract, BudgetAgentContract, ConstraintAgentContract,
    OptimizationAgentContract, PlannerAgentContract
)
from app.data.models import Attraction, Hotel, Destination
from app.data.database import SessionLocal
from app.schemas.planning import PlanningRequest, PlanningState

class ResearchAgent(ResearchAgentContract):
    def run(self, input_data: Dict) -> List[dict]:
        destination_name = input_data.get("destination")
        interests = [i.lower() for i in input_data.get("interests", [])]
        
        db = SessionLocal()
        try:
            dest = db.query(Destination).filter(
                func.lower(Destination.destination_name) == str(destination_name or "").strip().lower()
            ).first()
            if not dest:
                return []
            
            attractions = db.query(Attraction).filter(Attraction.destination_id == dest.destination_id).all()
            
            candidates = []
            for a in attractions:
                # Basic matching or return all if we let PreferenceAgent score them
                # The SRS says "retrieve available attractions for that destination"
                desc = a.description or ""
                cat = a.category or ""
                subcat = a.subcategory or ""
                
                candidates.append({
                    "id": a.attraction_id,
                    "name": a.name,
                    "category": cat,
                    "subcategory": subcat,
                    "rating": a.rating or 0.0,
                    "cost": a.estimated_cost or 0.0,
                    "duration": a.estimated_visit_duration_min or 60,
                    "description": desc,
                    "latitude": a.latitude,
                    "longitude": a.longitude
                })
            return candidates
        finally:
            db.close()

class PreferenceAgent(PreferenceAgentContract):
    def run(self, input_data: Dict) -> Dict[int, float]:
        interests = [str(i).lower() for i in input_data.get("interests", [])]
        candidates = input_data.get("candidate_attractions", [])
        
        scores = {}
        for c in candidates:
            score = 0.0
            cat_str = (c["category"] + " " + c["subcategory"] + " " + c["description"]).lower()
            
            for interest in interests:
                if interest in cat_str:
                    score += 5.0
            
            # rating/popularity where available
            rating = float(c.get("rating", 0.0))
            score += rating
            
            if score > 0:
                scores[c["id"]] = score
                
        return scores

class AccommodationAgent(AccommodationAgentContract):
    def run(self, input_data: Dict) -> List[dict]:
        destination_name = input_data.get("destination")
        db = SessionLocal()
        try:
            dest = db.query(Destination).filter(Destination.destination_name == destination_name).first()
            if not dest:
                return []
            
            hotels = db.query(Hotel).filter(Hotel.destination_id == dest.destination_id).all()
            
            h_candidates = []
            for h in hotels:
                if not h.latitude or not h.longitude:
                    continue # expressly handle missing coordinates as unusable
                
                h_candidates.append({
                    "id": h.hotel_id,
                    "name": h.name,
                    "price": float(h.price_per_night or 0.0),
                    "rating": float(h.rating or 0.0),
                    "latitude": h.latitude,
                    "longitude": h.longitude
                })
            return h_candidates
        finally:
            db.close()

class TransportAgent(TransportAgentContract):
    def run(self, input_data: Dict) -> Dict:
        origin = input_data.get("origin")
        dest = input_data.get("destination")
        
        if not origin or not dest:
            return {"distance_km": 0, "time_min": 0, "cost": 0, "status": "missing_coords"}
            
        olat, olon = origin.get("latitude"), origin.get("longitude")
        dlat, dlon = dest.get("latitude"), dest.get("longitude")
        
        if olat is None or olon is None or dlat is None or dlon is None:
            return {"distance_km": 0, "time_min": 0, "cost": 0, "status": "unavailable"}
            
        # Haversine abstraction
        R = 6371 # km
        phi1, phi2 = math.radians(olat), math.radians(dlat)
        dphi = math.radians(dlat - olat)
        dlam = math.radians(dlon - olon)
        a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlam/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        distance_km = R * c
        
        time_min = (distance_km / 30.0) * 60 # Assume 30km/h avg speed city transport
        cost = distance_km * 10 # Assume 10 units per km transport cost
        
        return {
            "distance_km": round(distance_km, 2),
            "time_min": round(time_min),
            "cost": round(cost, 2),
            "status": "calculated"
        }

class BudgetAgent(BudgetAgentContract):
    def run(self, input_data: Dict) -> Dict:
        itinerary = input_data.get("itinerary", [])
        total_budget = input_data.get("total_budget", 0.0)
        
        accommodation_cost = 0.0
        attraction_cost = 0.0
        transport_cost = 0.0
        
        for day in itinerary:
            if "hotel" in day and day["hotel"]:
                accommodation_cost += day["hotel"].get("price", 0.0)
            
            for leg in day.get("legs", []):
                if leg.get("transport"):
                    transport_cost += leg["transport"].get("cost", 0.0)
                if leg.get("attraction"):
                    attraction_cost += leg["attraction"].get("cost", 0.0)
                    
        total_estimated_cost = accommodation_cost + attraction_cost + transport_cost
        
        return {
            "accommodation_cost": accommodation_cost,
            "attraction_cost": attraction_cost,
            "transport_cost": transport_cost,
            "daily_cost": round(total_estimated_cost / max(1, len(itinerary)), 2) if itinerary else 0,
            "total_estimated_cost": total_estimated_cost,
            "remaining_budget": total_budget - total_estimated_cost
        }

class ConstraintAgent(ConstraintAgentContract):
    def run(self, input_data: Dict) -> Dict:
        budget_result = input_data.get("budget_result", {})
        itinerary = input_data.get("itinerary", [])
        total_budget = input_data.get("total_budget", 0)
        max_daily_travel_time = input_data.get("max_daily_travel_time", 9999)
        max_attractions_per_day = input_data.get("max_attractions_per_day", 4)
        
        violations = []
        
        if budget_result.get("total_estimated_cost", 0) > total_budget:
            violations.append(f"Budget exceeded: {budget_result['total_estimated_cost']} > {total_budget}")
            
        for d_idx, day in enumerate(itinerary):
            day_travel_time = sum([leg.get("transport", {}).get("time_min", 0) for leg in day.get("legs", [])])
            if day_travel_time > max_daily_travel_time:
                violations.append(f"Day {d_idx+1} travel time exceeded: {day_travel_time} > {max_daily_travel_time}")
                
            attraction_count = sum([1 for leg in day.get("legs", []) if leg.get("attraction")])
            if attraction_count > max_attractions_per_day:
                violations.append(f"Day {d_idx+1} attractions exceeded: {attraction_count} > {max_attractions_per_day}")
                
        return {
            "feasible": len(violations) == 0,
            "violations": violations
        }

class OptimizationAgent(OptimizationAgentContract):
    MAX_ATTRACTIONS_PER_DAY = 4

    def run(self, input_data: Dict) -> List[dict]:
        import math as _math

        req = input_data["request"]
        duration = req.duration
        candidate_hotels = input_data["candidate_hotels"]
        candidate_att = input_data["candidate_attractions"]
        prefs = input_data["preference_scores"]

        transport_agent = TransportAgent()

        # Select best hotel (by rating) if any have valid coordinates
        selected_hotel = None
        if candidate_hotels:
            sorted_hotels = sorted(candidate_hotels, key=lambda x: x.get('rating', 0), reverse=True)
            selected_hotel = sorted_hotels[0]

        # Prefer interest matches, but never return a blank plan when the
        # destination has verified attractions with incomplete metadata.
        scored_atts = [att for att in candidate_att if att["id"] in prefs]
        scored_atts = sorted(scored_atts, key=lambda x: prefs.get(x["id"], 0), reverse=True)
        if not scored_atts and candidate_att:
            scored_atts = sorted(
                candidate_att,
                key=lambda x: (
                    float(x.get("rating") or 0),
                    float(x.get("duration") or 0),
                ),
                reverse=True,
            )

        total_atts = len(scored_atts)

        # Distribute attractions evenly across days, respecting max per day
        if total_atts > 0 and duration > 0:
            per_day = min(_math.ceil(total_atts / duration), self.MAX_ATTRACTIONS_PER_DAY)
        else:
            per_day = 0

        itinerary = []
        att_idx = 0
        seen_ids = set()

        for day_num in range(1, duration + 1):
            day_plan = {
                "day": day_num,
                "hotel": selected_hotel,
                "hotel_status": "selected" if selected_hotel else "unavailable",
                "legs": []
            }

            current_loc = selected_hotel
            slots = per_day

            while slots > 0 and att_idx < total_atts:
                next_att = scored_atts[att_idx]
                att_idx += 1

                # Guard against duplication
                if next_att["id"] in seen_ids:
                    continue
                seen_ids.add(next_att["id"])

                transport = transport_agent.run({"origin": current_loc, "destination": next_att})

                day_plan["legs"].append({
                    "attraction": next_att,
                    "transport": transport
                })
                current_loc = next_att
                slots -= 1

            if not day_plan["legs"]:
                day_plan["note"] = "No eligible attractions remaining"

            itinerary.append(day_plan)

        return itinerary

class PlannerAgent(PlannerAgentContract):
    def run(self, req: PlanningRequest) -> PlanningState:
        state = PlanningState(planning_request=req)
        
        # 1. Research
        res_agent = ResearchAgent()
        state.candidate_attractions = res_agent.run({
            "destination": req.destination,
            "interests": req.interests,
            "duration": req.duration
        })
        
        if not state.candidate_attractions:
            state.validation_result = {
                "error": "No verified attractions were found for this destination."
            }
            state.optimized_itinerary = [
                {
                    "day": day,
                    "hotel": None,
                    "hotel_status": "unavailable",
                    "legs": [],
                    "note": "No verified attractions are available for this destination yet.",
                }
                for day in range(1, req.duration + 1)
            ]
            state.budget_result = BudgetAgent().run({
                "itinerary": state.optimized_itinerary,
                "total_budget": req.budget,
            })
            state.constraint_result = ConstraintAgent().run({
                "budget_result": state.budget_result,
                "itinerary": state.optimized_itinerary,
                "total_budget": req.budget,
                "max_daily_travel_time": req.max_daily_travel_time or 9999,
                "max_attractions_per_day": 4,
            })
            return state
            
        # 2. Preference
        pref_agent = PreferenceAgent()
        state.preference_scores = pref_agent.run({
            "interests": req.interests,
            "candidate_attractions": state.candidate_attractions
        })
        
        # 3. Accommodation
        acc_agent = AccommodationAgent()
        state.candidate_hotels = acc_agent.run({
            "destination": req.destination,
            "preference": req.accommodation_preference
        })
        
        # 4. Optimization
        opt_agent = OptimizationAgent()
        itinerary = opt_agent.run({
            "request": req,
            "candidate_hotels": state.candidate_hotels,
            "candidate_attractions": state.candidate_attractions,
            "preference_scores": state.preference_scores
        })
        
        # 5. Budget
        bud_agent = BudgetAgent()
        state.budget_result = bud_agent.run({
            "itinerary": itinerary,
            "total_budget": req.budget
        })
        
        # 6. Constraints
        con_agent = ConstraintAgent()
        state.constraint_result = con_agent.run({
            "budget_result": state.budget_result,
            "itinerary": itinerary,
            "total_budget": req.budget,
            "max_daily_travel_time": req.max_daily_travel_time or 9999,
            "max_attractions_per_day": 4
        })
        
        state.optimized_itinerary = itinerary
        
        return state
