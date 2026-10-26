from typing import Any, Dict, List
from sqlalchemy import func
from app.agents.base import (
    ResearchAgentContract, PreferenceAgentContract, AccommodationAgentContract,
    TransportAgentContract, BudgetAgentContract, ConstraintAgentContract,
    OptimizationAgentContract, PlannerAgentContract
)
from app.data.models import Attraction, Hotel, Destination
from app.data.database import SessionLocal
from app.data.quality import (
    address_matches_destination,
    finite_number,
    has_verified_source,
    valid_india_coordinates,
    verified_coordinates,
    verified_measure,
)
from app.data.preferences import matched_interests
from app.schemas.planning import PlanningRequest, PlanningState
from app.agents.cost_estimator import (
    calculate_trip_costs,
    demo_attractions_enabled,
    demo_hotels_enabled,
    estimate_transport,
    load_demo_attractions,
    load_demo_hotels,
)


class ResearchAgent(ResearchAgentContract):
    def run(self, input_data: Dict) -> List[dict]:
        destination_name = input_data.get("destination")
        db = SessionLocal()
        try:
            dest = db.query(Destination).filter(
                func.lower(Destination.destination_name) == str(destination_name or "").strip().lower()
            ).first()
            if not dest:
                return []

            anchor = None
            anchor_latitude = finite_number(getattr(dest, "latitude", None))
            anchor_longitude = finite_number(getattr(dest, "longitude", None))
            if (
                has_verified_source(getattr(dest, "source", None))
                and valid_india_coordinates(anchor_latitude, anchor_longitude)
            ):
                anchor = {
                    "latitude": anchor_latitude,
                    "longitude": anchor_longitude,
                    "location_type": "destination_center",
                    "id": dest.destination_id,
                    "name": dest.destination_name + " destination reference point",
                }

            attractions = (
                db.query(Attraction)
                .filter(
                    Attraction.destination_id == dest.destination_id,
                    Attraction.is_active.is_(True),
                )
                .all()
            )
            candidates = []
            for a in attractions:
                estimated_record = "estimate" in str(a.data_quality_status or "").casefold()
                source_url = a.source_url if not estimated_record else None
                coordinates = verified_coordinates(
                    a.latitude,
                    a.longitude,
                    a.coordinate_source,
                    a.coordinate_status,
                    dest.latitude,
                    dest.longitude,
                )
                category_is_sourced = bool(source_url)
                category = a.category if category_is_sourced else None
                subcategory = a.subcategory if category_is_sourced else None
                description = a.description if category_is_sourced else None
                rating = verified_measure(
                    a.rating,
                    a.rating_source,
                    minimum=0,
                    maximum=5,
                    validation_status=a.rating_validation_status,
                )
                cost = verified_measure(
                    a.estimated_cost,
                    a.cost_source,
                    minimum=0,
                    validation_status=a.cost_validation_status,
                )
                cost_currency = str(getattr(a, "currency", "") or "").strip().upper()
                if cost is not None and cost_currency not in {"INR", "₹"}:
                    cost = None
                duration = verified_measure(
                    a.estimated_visit_duration_min,
                    a.duration_source,
                    minimum=1,
                    validation_status=a.duration_validation_status,
                )
                candidates.append({
                    "id": a.attraction_id,
                    "name": a.name,
                    "category": category,
                    "subcategory": subcategory,
                    "rating": rating,
                    "rating_validation_status": a.rating_validation_status,
                    "cost": cost,
                    "cost_validation_status": a.cost_validation_status,
                    "cost_basis": "per_person",
                    "cost_data_status": "verified" if cost is not None else "unknown",
                    "duration": int(duration) if duration is not None else None,
                    "duration_validation_status": a.duration_validation_status,
                    "description": description,
                    "latitude": coordinates[0] if coordinates else None,
                    "longitude": coordinates[1] if coordinates else None,
                    "coordinate_status": "verified" if coordinates else "unavailable",
                    "coordinate_reason": None if coordinates else (
                        "Coordinates are missing, unverified, invalid, or too far from this destination."
                    ),
                    "destination_origin": anchor,
                })
            if demo_attractions_enabled() and anchor:
                demo_attractions = load_demo_attractions(
                    dest.destination_name,
                    dest.state,
                    anchor["latitude"],
                    anchor["longitude"],
                )
                if demo_attractions:
                    for attraction in demo_attractions:
                        attraction["destination_origin"] = anchor
                    return demo_attractions
            return candidates
        finally:
            db.close()


class PreferenceAgent(PreferenceAgentContract):
    @classmethod
    def matched_interests(cls, attraction: Dict, interests: List[str]) -> List[str]:
        return matched_interests(attraction, interests)

    def run(self, input_data: Dict) -> Dict[int, float]:
        interests = [str(i) for i in input_data.get("interests", [])]
        candidates = input_data.get("candidate_attractions", [])

        scores = {}
        for c in candidates:
            matches = self.matched_interests(c, interests)
            if matches:
                rating = finite_number(c.get("rating")) or 0.0
                scores[c["id"]] = 10.0 * len(matches) + rating
        return scores


class AccommodationAgent(AccommodationAgentContract):
    def __init__(self):
        self.last_status: Dict[str, Any] = {
            "status": "unavailable",
            "reason": "No destination hotel records were checked.",
            "matched_hotel_count": 0,
        }

    def run(self, input_data: Dict) -> List[dict]:
        destination_name = str(input_data.get("destination") or "").strip()
        db = SessionLocal()
        try:
            dest = db.query(Destination).filter(
                func.lower(Destination.destination_name) == destination_name.casefold()
            ).first()
            if not dest:
                self.last_status = {
                    "status": "unavailable",
                    "reason": "The requested destination does not exist in the destination catalog.",
                    "matched_hotel_count": 0,
                }
                return []

            destination_id = getattr(dest, "destination_id", None)
            destination_name = getattr(dest, "destination_name", "")
            destination_state = getattr(dest, "state", None)
            destination_latitude = getattr(dest, "latitude", None)
            destination_longitude = getattr(dest, "longitude", None)
            all_destinations = db.query(Destination).all()
            hotels = db.query(Hotel).all()
            h_candidates = []
            matched_count = 0
            no_coordinates_count = 0
            no_price_count = 0
            for h in hotels:
                hotel_address = getattr(h, "address", None)
                linked_by_id = getattr(h, "destination_id", None) == destination_id
                linked_by_address = address_matches_destination(
                    hotel_address, destination_name, destination_state
                )
                if not linked_by_id and not linked_by_address:
                    continue
                if hotel_address and not linked_by_address:
                    conflicting_location = any(
                        getattr(other, "destination_id", None) != destination_id
                        and address_matches_destination(
                            hotel_address,
                            getattr(other, "destination_name", ""),
                            getattr(other, "state", None),
                        )
                        for other in all_destinations
                    )
                    if conflicting_location:
                        continue
                matched_count += 1
                coordinates = verified_coordinates(
                    h.latitude,
                    h.longitude,
                    h.provenance_source or h.source_url,
                    h.data_quality_status,
                    destination_latitude,
                    destination_longitude,
                )
                if not coordinates:
                    no_coordinates_count += 1
                    continue
                price = verified_measure(
                    h.price_per_night,
                    h.price_source,
                    minimum=0.01,
                    validation_status=h.price_validation_status,
                )
                hotel_currency = str(getattr(h, "currency", "") or "").strip().upper()
                if price is not None and hotel_currency not in {"INR", "₹"}:
                    price = None
                if price is None:
                    no_price_count += 1
                    continue
                rating = verified_measure(
                    h.rating,
                    h.rating_source,
                    minimum=0,
                    maximum=5,
                    validation_status=h.rating_validation_status,
                )
                h_candidates.append({
                    "id": h.hotel_id,
                    "name": h.name,
                    "price": price,
                    "price_per_night": price,
                    "currency": hotel_currency,
                    "rating": rating,
                    "latitude": coordinates[0],
                    "longitude": coordinates[1],
                    "destination": destination_name,
                    "address": hotel_address,
                    "coordinate_status": "verified",
                    "data_status": "VERIFIED",
                    "source_type": "verified",
                })

            if not h_candidates and demo_hotels_enabled():
                destination_reference = None
                if (
                    has_verified_source(getattr(dest, "source", None))
                    and valid_india_coordinates(destination_latitude, destination_longitude)
                ):
                    destination_reference = (
                        float(destination_latitude),
                        float(destination_longitude),
                    )
                if destination_reference:
                    demo_candidates = load_demo_hotels(
                        destination_name,
                        destination_state,
                        destination_reference[0],
                        destination_reference[1],
                    )
                    h_candidates.extend(demo_candidates)

            if h_candidates:
                reason = None
                is_demo_only = all(
                    hotel.get("source_type") == "synthetic" for hotel in h_candidates
                )
                status = "demo_available" if is_demo_only else "available"
                if is_demo_only:
                    reason = (
                        "Sample hotel — demonstration data. The property and nightly rate "
                        "are synthetic illustrations, not a real hotel or market price."
                    )
            elif not matched_count:
                reason = "No hotel record could be reliably linked to this destination."
                status = "unavailable"
            elif no_coordinates_count:
                reason = (
                    f"{matched_count} linked hotel record(s) exist, but none has verified "
                    "coordinates suitable for distance-based selection."
                )
                status = "unavailable"
            else:
                reason = "Linked hotel records do not have a verified positive nightly price."
                status = "unavailable"
            self.last_status = {
                "status": status,
                "reason": reason,
                "matched_hotel_count": matched_count,
                "eligible_hotel_count": len(h_candidates),
                "missing_or_invalid_coordinates": no_coordinates_count,
                "missing_or_invalid_prices": no_price_count,
            }
            return h_candidates
        finally:
            db.close()


class TransportAgent(TransportAgentContract):
    def run(self, input_data: Dict) -> Dict:
        return estimate_transport(
            input_data.get("origin"),
            input_data.get("destination"),
            mode=input_data.get("mode", "car_taxi_estimate"),
        )


class BudgetAgent(BudgetAgentContract):
    def run(self, input_data: Dict) -> Dict:
        return calculate_trip_costs(
            input_data.get("itinerary", []),
            duration=int(input_data.get("duration", 0)),
            travelers=int(input_data.get("travelers", 1)),
            budget_limit=finite_number(input_data.get("total_budget")),
            currency=str(input_data.get("currency", "INR")),
            accommodation_status=input_data.get("accommodation_status"),
        )


class ConstraintAgent(ConstraintAgentContract):
    def run(self, input_data: Dict) -> Dict:
        budget_result = input_data.get("budget_result", {})
        itinerary = input_data.get("itinerary", [])
        total_budget = input_data.get("total_budget", 0)
        max_daily_travel_time = input_data.get("max_daily_travel_time", 9999)
        max_attractions_per_day = input_data.get("max_attractions_per_day", 4)
        
        violations = []
        warnings = []

        if budget_result.get("total_is_complete") is False:
            warnings.append("Budget feasibility is unverified because one or more costs are unavailable.")
        if budget_result.get("data_status") == "DEMO_SYNTHETIC":
            warnings.append("Budget feasibility is not verified.")
        estimated_total = finite_number(budget_result.get("total_estimated_cost"))
        if estimated_total is not None and estimated_total > total_budget:
            violations.append(f"Budget exceeded: {budget_result['total_estimated_cost']} > {total_budget}")
            
        for d_idx, day in enumerate(itinerary):
            legs = day.get("legs", [])
            routes = [leg.get("transport", {}) for leg in legs]
            if day.get("return_transport"):
                routes.append(day["return_transport"])
            known_times = [
                finite_number(route.get("time_min"))
                for route in routes
                if route.get("status") == "calculated"
            ]
            if max_daily_travel_time < 9999 and len(known_times) < len(routes):
                warnings.append(f"Day {d_idx+1} travel-time limit cannot be verified.")
            day_travel_time = sum(value for value in known_times if value is not None)
            if day_travel_time > max_daily_travel_time:
                violations.append(f"Day {d_idx+1} travel time exceeded: {day_travel_time} > {max_daily_travel_time}")
                
            attraction_count = sum(1 for leg in legs if leg.get("attraction"))
            if attraction_count > max_attractions_per_day:
                violations.append(f"Day {d_idx+1} attractions exceeded: {attraction_count} > {max_attractions_per_day}")
                
        status = "violated" if violations else "incomplete" if warnings else "feasible"
        return {
            "feasible": status == "feasible",
            "status": status,
            "violations": violations,
            "warnings": warnings,
        }

class OptimizationAgent(OptimizationAgentContract):
    MAX_ATTRACTIONS_PER_DAY = 4

    def run(self, input_data: Dict) -> List[dict]:
        req = input_data["request"]
        duration = req.duration
        candidate_hotels = input_data["candidate_hotels"]
        candidate_att = input_data["candidate_attractions"]
        prefs = input_data["preference_scores"]
        accommodation_result = input_data.get("accommodation_result", {})

        transport_agent = TransportAgent()

        selected_hotel = None
        if candidate_hotels:
            def hotel_rank(hotel):
                rating = finite_number(hotel.get("rating")) or 0.0
                price = finite_number(hotel.get("price")) or float("inf")
                preference = req.accommodation_preference
                if preference == "budget":
                    return (price, -rating)
                if preference == "luxury":
                    return (-rating, -price)
                return (-rating, price)

            sorted_hotels = sorted(candidate_hotels, key=hotel_rank)
            selected_hotel = sorted_hotels[0]

        scored_atts = sorted(
            candidate_att,
            key=lambda x: (
                -prefs.get(x["id"], 0.0),
                -(finite_number(x.get("rating")) or 0.0),
                -(finite_number(x.get("duration")) or 0.0),
                str(x.get("name") or "").casefold(),
            ),
        )

        destination_origin = next(
            (attraction.get("destination_origin") for attraction in candidate_att
             if attraction.get("destination_origin")),
            None,
        )
        daily_times = [0.0 for _ in range(duration)]
        itinerary = [
            {
                "day": day_num,
                "hotel": selected_hotel,
                "hotel_status": (
                    "demo_selected" if selected_hotel and selected_hotel.get("source_type") == "synthetic"
                    else "selected" if selected_hotel else "unavailable"
                ),
                "hotel_reason": accommodation_result.get("reason"),
                "legs": [],
            }
            for day_num in range(1, duration + 1)
        ]
        seen_ids = set()
        unscheduled = []

        for attraction in scored_atts:
            if attraction["id"] in seen_ids:
                continue
            seen_ids.add(attraction["id"])

            day_order = sorted(
                range(duration),
                key=lambda index: (len(itinerary[index]["legs"]), index),
            )
            placed = False
            for day_index in day_order:
                day_plan = itinerary[day_index]
                if len(day_plan["legs"]) >= self.MAX_ATTRACTIONS_PER_DAY:
                    continue
                if day_plan["legs"]:
                    origin = day_plan["legs"][-1]["attraction"]
                else:
                    origin = selected_hotel or destination_origin
                transport = transport_agent.run({
                    "origin": origin,
                    "destination": attraction,
                })
                route_time = finite_number(transport.get("time_min"))
                max_time = req.max_daily_travel_time
                if (
                    max_time is not None
                    and transport.get("status") == "calculated"
                    and route_time is not None
                    and daily_times[day_index] + route_time > max_time
                ):
                    continue

                matches = PreferenceAgent.matched_interests(attraction, req.interests)
                if matches:
                    recommendation_reason = f"Matched interests: {', '.join(matches)}."
                else:
                    recommendation_reason = (
                        "Fallback recommendation: no selected interest matched this "
                        "attraction's available text."
                    )
                day_plan["legs"].append({
                    "attraction": attraction,
                    "transport": transport,
                    "recommendation_reason": recommendation_reason,
                })
                if route_time is not None and transport.get("status") == "calculated":
                    daily_times[day_index] += route_time
                placed = True
                break
            if not placed:
                unscheduled.append(attraction.get("name", "Attraction"))

        for day_plan in itinerary:
            if day_plan["legs"]:
                final_attraction = day_plan["legs"][-1]["attraction"]
                return_destination = selected_hotel or destination_origin
                day_plan["return_transport"] = transport_agent.run({
                    "origin": final_attraction,
                    "destination": return_destination,
                })
            if not day_plan["legs"]:
                day_plan["note"] = (
                    "No remaining attraction could be scheduled within the known "
                    "daily and budget constraints."
                    if unscheduled else "No eligible attractions were available for this day."
                )
        if unscheduled and itinerary:
            itinerary[0]["unscheduled_attractions"] = unscheduled

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
                "error": "No attraction records were found for this destination."
            }
            state.optimized_itinerary = [
                {
                    "day": day,
                    "hotel": None,
                    "hotel_status": "unavailable",
                    "hotel_reason": "No suitable verified hotel was available.",
                    "legs": [],
                    "note": "No verified attractions are available for this destination yet.",
                }
                for day in range(1, req.duration + 1)
            ]
            state.budget_result = BudgetAgent().run({
                "itinerary": state.optimized_itinerary,
                "total_budget": req.budget,
                "duration": req.duration,
                "travelers": req.travelers,
                "currency": req.currency,
                "accommodation_status": state.accommodation_result,
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
        state.accommodation_result = acc_agent.last_status
        
        # 4. Optimization
        opt_agent = OptimizationAgent()
        itinerary = opt_agent.run({
            "request": req,
            "candidate_hotels": state.candidate_hotels,
            "candidate_attractions": state.candidate_attractions,
            "preference_scores": state.preference_scores,
            "accommodation_result": state.accommodation_result,
        })

        scheduled_ids = {
            leg["attraction"]["id"]
            for day in itinerary
            for leg in day.get("legs", [])
        }
        if not state.preference_scores and scheduled_ids:
            state.planning_note = (
                "No selected interest matched the available attraction text. "
                "The itinerary uses fallback recommendations from this destination."
            )
        elif fallback_attraction_ids := [
            leg["attraction"]["id"]
            for day in itinerary
            for leg in day.get("legs", [])
            if leg["attraction"]["id"] not in state.preference_scores
        ]:
            state.planning_note = (
                f"{len(fallback_attraction_ids)} attraction(s) were added as fallback "
                "recommendations after matching-interest attractions were prioritized."
            )
        unscheduled = [
            name
            for day in itinerary
            for name in day.get("unscheduled_attractions", [])
        ]
        if unscheduled:
            state.planning_note = " ".join(filter(None, [
                state.planning_note,
                f"{len(unscheduled)} attraction(s) could not be scheduled within the known constraints.",
            ]))
        if len(state.candidate_attractions) < req.duration:
            empty_days = sum(not day.get("legs") for day in itinerary)
            state.planning_note = " ".join(filter(None, [
                state.planning_note,
                (
                    f"Only {len(state.candidate_attractions)} attraction record(s) were "
                    f"available for the {req.duration}-day request; "
                    f"{empty_days} day(s) have no attraction recommendation."
                ),
            ]))
        
        # 5. Budget
        bud_agent = BudgetAgent()
        state.budget_result = bud_agent.run({
            "itinerary": itinerary,
            "total_budget": req.budget,
            "duration": req.duration,
            "travelers": req.travelers,
            "currency": req.currency,
            "accommodation_status": state.accommodation_result,
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
