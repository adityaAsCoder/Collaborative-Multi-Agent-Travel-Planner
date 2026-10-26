"""
WanderWise — User-facing travel planning app.
Uses the real FastAPI backend which calls the real PlannerAgent → real SQLite data.
"""
from __future__ import annotations

import html as _html
import json
import time
from pathlib import Path
import sys

import requests
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

# ─── Config ──────────────────────────────────────────────────────────────────
API_BASE = "http://127.0.0.1:8000"

st.set_page_config(
    page_title="WanderWise | India Travel Planning",
    page_icon="✈️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ─── Global CSS ──────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

.stApp { background: #f0f4f8; }

/* ── Hero ── */
.hero {
  background: linear-gradient(135deg, #0f2027, #203a43, #2c5364);
  border-radius: 1.2rem; padding: 3rem 3.5rem; color: white; margin-bottom: 1.5rem;
}
.hero h1 { font-size: 3rem; font-weight: 700; margin-bottom: .4rem; letter-spacing: -1px; }
.hero p  { font-size: 1.1rem; opacity: .85; max-width: 540px; }

/* ── Cards ── */
.card {
  background: white; border-radius: 1rem; padding: 1.5rem 1.8rem;
  border: 1px solid #e2e8f0; margin-bottom: 1rem;
  box-shadow: 0 1px 4px rgba(0,0,0,.06);
}
.card-accent { border-left: 4px solid #2c5364; }

/* ── Day header ── */
.day-header {
  background: linear-gradient(90deg, #2c5364, #203a43);
  color: white; border-radius: .6rem; padding: .6rem 1.2rem;
  font-weight: 600; font-size: 1rem; margin: 1.2rem 0 .5rem;
}

/* ── Attraction row ── */
.att-row {
  display: flex; align-items: flex-start; gap: 1rem;
  padding: .75rem 0; border-bottom: 1px solid #f1f5f9;
}
.att-icon {
  width: 40px; height: 40px; border-radius: 50%;
  background: #e0f2fe; display: flex; align-items: center;
  justify-content: center; font-size: 1.2rem; flex-shrink: 0;
}
.att-body h4 { margin: 0 0 .2rem; font-size: .95rem; font-weight: 600; }
.att-body p  { margin: 0; font-size: .82rem; color: #64748b; }

/* ── Budget table ── */
.budget-row { display: flex; justify-content: space-between; padding: .4rem 0;
               border-bottom: 1px solid #f1f5f9; font-size: .92rem; }
.budget-total { display: flex; justify-content: space-between; padding: .6rem 0;
                font-weight: 700; font-size: 1rem; border-top: 2px solid #2c5364; }

/* ── Status chips ── */
.chip-feasible { background:#d1fae5; color:#065f46; padding:.2rem .6rem;
                  border-radius:999px; font-size:.8rem; font-weight:600; }
.chip-violated { background:#fee2e2; color:#991b1b; padding:.2rem .6rem;
                  border-radius:999px; font-size:.8rem; font-weight:600; }
.chip-warn     { background:#fef3c7; color:#92400e; padding:.2rem .6rem;
                  border-radius:999px; font-size:.8rem; font-weight:600; }

/* ── Nav ── */
.topnav {
  display: flex; align-items: center; gap: 2rem;
  background: white; border-radius: .8rem; padding: .8rem 1.5rem;
  margin-bottom: 1.5rem; border: 1px solid #e2e8f0;
  box-shadow: 0 1px 3px rgba(0,0,0,.05);
}
.topnav .brand { font-weight: 700; font-size: 1.1rem; color: #2c5364; }
.topnav a { color: #475569; text-decoration: none; font-size: .9rem; }

/* ── Interests tags ── */
.tag { display: inline-block; background:#e0f2fe; color:#0369a1;
       border-radius:999px; padding:.2rem .7rem; font-size:.8rem;
       margin:.2rem .2rem .2rem 0; }
</style>
""", unsafe_allow_html=True)


# ─── API helpers ─────────────────────────────────────────────────────────────
def api(method: str, path: str, **kwargs):
    """Call the backend API. Returns (data, error_msg)."""
    try:
        resp = getattr(requests, method)(f"{API_BASE}{path}", timeout=60, **kwargs)
        if resp.status_code == 200:
            return resp.json(), None
        return None, resp.json().get("detail", "Unknown error")
    except requests.ConnectionError:
        return None, "⚠️ Backend API is not running. Start it with:  uvicorn app.api:app --reload"
    except Exception as e:
        return None, str(e)


def ss(key, default=None):
    return st.session_state.get(key, default)


CATEGORY_ICONS = {
    "historical": "🏛️", "nature": "🌿", "religious": "🛕",
    "cultural": "🎭", "adventure": "🧭", "beach": "🏖️",
    "food": "🍽️", "": "📍",
}

def cat_icon(category: str) -> str:
    return CATEGORY_ICONS.get((category or "").lower(), "📍")


# ─── Page components ──────────────────────────────────────────────────────────

def render_navbar():
    user = ss("user_email")
    page = ss("page", "home")

    nav_html = '<div class="topnav">'
    nav_html += '<span class="brand">✈️ WanderWise</span>'
    if user:
        nav_html += f'<span style="color:#64748b;font-size:.9rem;">Welcome, {_html.escape(user.split("@")[0].title())}</span>'
    nav_html += '</div>'
    st.markdown(nav_html, unsafe_allow_html=True)

    if user:
        cols = st.columns([1, 1, 1, 1, 2])
        with cols[0]:
            if st.button("🏠 Home", use_container_width=True):
                st.session_state.page = "dashboard"
                st.rerun()
        with cols[1]:
            if st.button("✈️ Plan Trip", use_container_width=True):
                st.session_state.page = "plan"
                st.rerun()
        with cols[2]:
            if st.button("📋 My Trips", use_container_width=True):
                st.session_state.page = "trips"
                st.rerun()
        with cols[3]:
            if st.button("🚪 Logout", use_container_width=True):
                for k in ["user_email", "page", "itinerary", "trip_id", "saved_trip_id"]:
                    st.session_state.pop(k, None)
                st.rerun()


def page_landing():
    st.markdown("""
    <div class="hero">
      <h1>Plan the trip you'll talk about.</h1>
      <p>Enter your destination, interests, and budget — our multi-agent travel planner builds
         a day-by-day itinerary. Selected demo destinations include clearly labeled illustrative fees and stays.</p>
    </div>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("🔑 Log In")
        email = st.text_input("Email", key="login_email")
        password = st.text_input("Password", type="password", key="login_pw")
        if st.button("Log In", type="primary", use_container_width=True, key="btn_login"):
            if not email or not password:
                st.error("Please enter email and password.")
            else:
                data, err = api("post", "/auth/login", json={"email": email, "password": password})
                if err:
                    st.error(err)
                else:
                    st.session_state.user_email = data["email"]
                    st.session_state.page = "dashboard"
                    st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    with col2:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("📝 Create Account")
        r_email = st.text_input("Email", key="reg_email")
        r_pw = st.text_input("Password (8+ chars)", type="password", key="reg_pw")
        r_pw2 = st.text_input("Confirm Password", type="password", key="reg_pw2")
        if st.button("Create Account", use_container_width=True, key="btn_reg"):
            if r_pw != r_pw2:
                st.error("Passwords do not match.")
            else:
                data, err = api("post", "/auth/register", json={"email": r_email, "password": r_pw})
                if err:
                    st.error(err)
                else:
                    st.success("Account created! You can now log in.")
        st.markdown('</div>', unsafe_allow_html=True)

    st.divider()
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown('<div class="card card-accent"><h4>🗺️ 93 Destinations</h4><p style="color:#64748b">India destination catalog, with 20 places configured for complete illustrative demo plans.</p></div>', unsafe_allow_html=True)
    with col2:
        st.markdown('<div class="card card-accent"><h4>🏛️ 20 Demo Destinations</h4><p style="color:#64748b">Illustrative attraction fees, visit durations, sample stays, and route estimates are labeled as demo data.</p></div>', unsafe_allow_html=True)
    with col3:
        st.markdown('<div class="card card-accent"><h4>🤖 8 AI Agents</h4><p style="color:#64748b">Research, preference, accommodation, transport, budget, constraint, and optimization agents.</p></div>', unsafe_allow_html=True)


def page_dashboard():
    user = ss("user_email")
    name = (user or "").split("@")[0].title()

    st.markdown(f"""
    <div class="hero">
      <h1>Welcome back, {_html.escape(name)} 👋</h1>
      <p>Ready to plan your next adventure? Choose a destination and let our agents build your itinerary.</p>
    </div>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        st.markdown('<div class="card card-accent"><h4>✈️ Plan a New Trip</h4><p style="color:#64748b">Pick a destination, set your budget and interests, and get a day-by-day itinerary with demo data clearly identified.</p></div>', unsafe_allow_html=True)
        if st.button("Start Planning →", type="primary", key="goto_plan"):
            st.session_state.page = "plan"
            st.rerun()

    with col2:
        trips, err = api("get", f"/trips/{user}")
        if err:
            st.warning(err)
            trips = []
        st.markdown(f'<div class="card card-accent"><h4>📋 My Trips ({len(trips or [])})</h4><p style="color:#64748b">View your past itineraries and revisit your travel plans.</p></div>', unsafe_allow_html=True)
        if st.button("View My Trips →", key="goto_trips"):
            st.session_state.page = "trips"
            st.rerun()

    if trips:
        st.subheader("Recent Trips")
        for t in (trips or [])[:3]:
            req = t["request"]
            dest = req.get("destination", "")
            dur = req.get("duration", "")
            created = t.get("created_at", "")[:10]
            interests = ", ".join(req.get("interests", []))
            st.markdown(
                f'<div class="card"><b>📍 {_html.escape(dest)}</b> · {dur} days · {_html.escape(interests)}'
                f'<br><span style="color:#94a3b8;font-size:.8rem;">{created}</span></div>',
                unsafe_allow_html=True,
            )
            if st.button(f"View Itinerary →", key=f"view_{t['trip_id']}"):
                st.session_state.trip_id = t["trip_id"]
                st.session_state.itinerary = t["result"]
                st.session_state.itinerary_req = t["request"]
                st.session_state.page = "itinerary"
                st.rerun()
    else:
        st.info("No trips planned yet. Click 'Start Planning' to create your first itinerary.")


def page_plan():
    st.markdown('<div class="hero"><h1>✈️ Plan Your Trip</h1><p>Generate an itinerary. Selected destinations use illustrative demo fees and stays, labeled as demonstration data.</p></div>', unsafe_allow_html=True)

    # Load destination list
    dests, err = api("get", "/destinations")
    if err:
        st.error(err)
        return

    dest_names = [f"{d['name']} ({d['state']})" if d['state'] else d['name'] for d in dests]
    dest_map = {f"{d['name']} ({d['state']})" if d['state'] else d['name']: d['name'] for d in dests}

    INTEREST_OPTIONS = [
        "Forts", "History", "Temples", "Beaches", "Trekking",
        "Wildlife", "Food", "Shopping", "Monasteries", "Waterfalls",
        "Lakes", "Culture", "Photography", "Adventure", "Backpacking",
    ]

    with st.form("plan_form"):
        st.subheader("Destination & Duration")
        col1, col2 = st.columns(2)
        with col1:
            selected_label = st.selectbox("Destination", dest_names)
        with col2:
            duration = st.number_input("Duration (days)", min_value=1, max_value=14, value=3)

        st.subheader("Travelers & Budget")
        col3, col4, col5 = st.columns(3)
        with col3:
            travelers = st.number_input("Number of Travelers", min_value=1, max_value=20, value=2)
        with col4:
            budget = st.number_input("Budget (₹)", min_value=1000, max_value=1000000, value=20000, step=1000)
        with col5:
            accommodation = st.selectbox("Accommodation Preference", ["any", "budget", "standard", "luxury"])

        st.subheader("Interests")
        interests = st.multiselect(
            "Select your interests (choose at least one)",
            INTEREST_OPTIONS,
            default=["History", "Forts"],
        )

        st.subheader("Advanced Options")
        col6, col7 = st.columns(2)
        with col6:
            max_travel = st.number_input(
                "Max daily travel time (minutes, 0 = no limit)",
                min_value=0, max_value=480, value=0,
            )

        submitted = st.form_submit_button("🗺️ Generate My Itinerary", type="primary", use_container_width=True)

    if submitted:
        if not interests:
            st.error("Please select at least one interest.")
            return

        destination_name = dest_map.get(selected_label, selected_label)

        with st.spinner("Generating your personalized itinerary..."):
            # Show agent activity steps
            steps = st.empty()
            agent_steps = [
                "🔍 Researching attractions...",
                "⭐ Scoring your preferences...",
                "🏨 Checking accommodation...",
                "🚗 Calculating travel distances...",
                "💰 Estimating budget...",
                "✅ Validating constraints...",
                "🎯 Optimizing itinerary...",
            ]
            for i, step in enumerate(agent_steps):
                steps.markdown(f"**{step}**")
                time.sleep(0.25)
            steps.empty()

            payload = {
                "email": ss("user_email"),
                "destination": destination_name,
                "duration": int(duration),
                "travelers": int(travelers),
                "budget": float(budget),
                "currency": "INR",
                "interests": interests,
                "max_daily_travel_time": int(max_travel) if max_travel > 0 else None,
                "accommodation_preference": accommodation,
            }
            result, err = api("post", "/plan", json=payload)

        if err:
            st.error(f"Planning failed: {err}")
            return

        st.session_state.itinerary = result
        st.session_state.itinerary_req = payload
        st.session_state.trip_id = result.get("trip_id")
        st.session_state.saved_trip_id = None
        st.session_state.page = "itinerary"
        st.rerun()


def _render_budget(br: dict, currency="INR"):
    def amount(value):
        return "Unavailable" if value is None else f"{currency} {value:,.2f}"

    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown("**💰 Budget Breakdown**")
    for label, field, complete_field in (
        ("🏨 Accommodation", "accommodation_total", "accommodation_cost_complete"),
        ("🏛️ Attractions", "attraction_total", "attraction_cost_complete"),
        ("🚗 Transportation", "transportation_total", "transport_cost_complete"),
    ):
        value = br.get(field)
        complete = br.get(complete_field, True)
        status = "" if complete else " (partial/unavailable)"
        if field == "accommodation_total" and br.get("accommodation", {}).get("data_status") == "NOT_REQUIRED":
            value_text = "Not applicable — no overnight stay"
        else:
            value_text = amount(value)
        st.markdown(
            f'<div class="budget-row"><span>{label}{status}</span>'
            f'<span>{value_text}</span></div>',
            unsafe_allow_html=True,
        )
    total_label = (
        "Illustrative trip total"
        if br.get("data_status") == "DEMO_SYNTHETIC"
        else "Estimated trip total" if br.get("is_estimate_complete")
        else "Known cost total (incomplete)"
    )
    st.markdown(
        f'<div class="budget-total">'
        f'<span>{total_label}</span>'
        f'<span>{amount(br.get("known_cost_total"))}</span>'
        f'</div>',
        unsafe_allow_html=True,
    )
    remaining = br.get("remaining_budget_after_known_costs")
    if remaining is not None:
        color = "#16a34a" if remaining >= 0 else "#dc2626"
        remaining_label = (
            "Budget minus illustrative costs (not spendable)"
            if br.get("data_status") == "DEMO_SYNTHETIC"
            else
            "Budget minus known costs (not spendable)"
            if not br.get("is_estimate_complete")
            else "Budget minus estimated trip costs"
        )
        st.markdown(
            f'<p style="color:{color};font-weight:600;">'
            f'{remaining_label}: {amount(remaining)}</p>',
            unsafe_allow_html=True,
        )
    st.caption(
        f"Verified: {amount(br.get('verified_cost_total'))} · "
        f"Estimated: {amount(br.get('estimated_cost_total'))} · "
        f"Illustrative: {amount(br.get('demonstration_cost_total'))}"
    )
    if not br.get("is_estimate_complete", False) and br.get("data_status") != "DEMO_SYNTHETIC":
        detail = " ".join(br.get("unknown_components", []))
        st.warning(
            "This is not the complete trip cost. "
            + (detail or "Some trip costs could not be verified.")
        )
    st.markdown('</div>', unsafe_allow_html=True)


def _render_constraints(cr: dict):
    status = cr.get("status", "incomplete")
    feasible = status == "feasible"
    violations = cr.get("violations", [])
    chip = (
        '<span class="chip-feasible">✓ FEASIBLE</span>'
        if feasible else '<span class="chip-violated">! UNVERIFIED / NEEDS ATTENTION</span>'
    )
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown(f"**✅ Constraint Validation** &nbsp; {chip}", unsafe_allow_html=True)
    if violations:
        for v in violations:
            st.error(v)
    elif not feasible:
        for warning in cr.get("warnings", []):
            st.warning(warning)
    else:
        st.caption("Budget, duration, and daily attraction limits are all within acceptable bounds.")
    st.markdown('</div>', unsafe_allow_html=True)


def _render_accommodation(itinerary: list, destination: str, accommodation: dict | None = None):
    accommodation = accommodation or {}

    def amount_for_display(value):
        return "Unavailable" if value is None else f"₹{float(value):,.2f}"

    hotel = None
    for day in itinerary:
        if day.get("hotel"):
            hotel = day["hotel"]
            break
    hotel_name = accommodation.get("hotel_name") or (hotel or {}).get("name")

    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown("**🏨 Accommodation**")
    if hotel_name:
        if accommodation.get("source_type") == "synthetic":
            st.markdown(f"**{_html.escape(hotel_name)}**")
            st.caption("Illustrative stay · estimated price · not bookable")
        else:
            st.markdown(f"✅ **{_html.escape(hotel_name)}**")
            st.caption(
                f"Verified accommodation record · "
                f"{_html.escape(str(accommodation.get('data_status') or 'VERIFIED'))}"
            )
        nightly_rate = accommodation.get("price_per_night", (hotel or {}).get("price"))
        nightly_label = "Illustrative nightly rate" if accommodation.get("source_type") == "synthetic" else "Price per night"
        st.caption(
            f"{_html.escape(str(accommodation.get('destination') or destination))}"
            + (
                f" · {_html.escape(str(accommodation['address']))}"
                if accommodation.get("source_type") != "synthetic" and accommodation.get("address")
                else ""
            )
        )
        st.caption(
            f"{nightly_label}: {amount_for_display(nightly_rate)} · "
            f"Nights: {accommodation.get('nights', 'Unavailable')} · "
            f"Rooms: {accommodation.get('rooms_required', 'Unknown')}"
        )
        st.caption(
            f"Rating: {accommodation.get('rating') if accommodation.get('rating') is not None else 'Unavailable'} · "
            f"Total accommodation estimate: "
            f"{amount_for_display(accommodation.get('total_accommodation_cost'))}"
        )
        if accommodation.get("source_type") != "synthetic" and accommodation.get("reason"):
            st.warning(accommodation["reason"])
    else:
        st.markdown('<span class="chip-warn">Unavailable</span>', unsafe_allow_html=True)
        st.caption(
            f"{_html.escape(accommodation.get('reason') or f'No suitable accommodation was available for {destination}.')} "
            "Accommodation is not free and is excluded from the known cost total."
        )
    st.markdown('</div>', unsafe_allow_html=True)


def page_itinerary():
    result = ss("itinerary")
    req = ss("itinerary_req", {})
    if not result:
        st.warning("No itinerary loaded. Please plan a trip first.")
        if st.button("← Plan a Trip"):
            st.session_state.page = "plan"
            st.rerun()
        return

    destination = req.get("destination", "")
    duration = req.get("duration", "")
    travelers = req.get("travelers", "")
    budget = req.get("budget", "")
    interests = req.get("interests", [])

    # Hero
    tags_html = "".join(f'<span class="tag">{_html.escape(i)}</span>' for i in interests)
    st.markdown(f"""
    <div class="hero">
      <h1>📍 {_html.escape(destination)}</h1>
      <p>{duration} Days &nbsp;·&nbsp; {travelers} Travellers &nbsp;·&nbsp; Budget ₹{float(budget):,.0f}</p>
      <div style="margin-top:.8rem">{tags_html}</div>
    </div>
    """, unsafe_allow_html=True)

    action_col, save_col = st.columns(2)
    with action_col:
        if st.button("← Plan Another Trip"):
            st.session_state.page = "plan"
            st.rerun()
    with save_col:
        if st.button("💾 Save to My Trips", disabled=bool(ss("saved_trip_id"))):
            saved, err = api(
                "post",
                "/trips",
                json={"email": ss("user_email"), "request": req, "result": result},
            )
            if err:
                st.error(f"Could not save trip: {err}")
            else:
                st.session_state.saved_trip_id = saved["trip_id"]
                st.success("Trip saved to My Trips.")

    itinerary = result.get("itinerary", [])
    pref_score = result.get("preference_score", 0)

    # Summary cards
    col1, col2, col3 = st.columns(3)
    br = result.get("budget", {})
    col1.metric("Preference Score", f"{pref_score:.1f}")
    known_cost = br.get("known_cost_total")
    total_label = (
        "Illustrative trip total"
        if br.get("data_status") == "DEMO_SYNTHETIC"
        else "Known cost total" if not br.get("is_estimate_complete")
        else "Estimated trip total"
    )
    col2.metric(
        total_label,
        "Unavailable" if known_cost is None else f"₹{known_cost:,.2f}",
    )
    col3.metric(
        "Budget minus illustrative costs" if br.get("data_status") == "DEMO_SYNTHETIC"
        else "Budget minus known costs" if not br.get("is_estimate_complete")
        else "Budget minus estimated costs",
        "Unavailable"
        if br.get("remaining_budget_after_known_costs") is None
        else f"₹{br['remaining_budget_after_known_costs']:,.2f}",
    )
    if not br.get("is_estimate_complete", False):
        if br.get("data_status") == "DEMO_SYNTHETIC":
            st.warning("Illustrative remainder only; it is not a spendable trip balance.")
        else:
            st.warning("The arithmetic remainder is not spendable budget; unavailable components are excluded.")
    if br.get("data_status") == "DEMO_SYNTHETIC":
        st.info("Illustrative plan: accommodation, attraction fees, locations, and transport costs are estimates, not verified listings, prices, or road routes.")

    st.markdown("---")

    # Main layout: itinerary left, sidebar right
    left, right = st.columns([2, 1])

    with left:
        st.subheader("🗓️ Your Itinerary")
        if not itinerary:
            st.info("No itinerary was generated. The destination may not have enriched attraction data yet.")
        for day in itinerary:
            day_num = day["day"]
            legs = day.get("legs", [])
            note = day.get("note", "")

            st.markdown(f'<div class="day-header">Day {day_num}</div>', unsafe_allow_html=True)

            if not legs:
                st.markdown(
                    f'<div class="card"><span class="chip-warn">No eligible attractions remaining</span>'
                    f'<p style="color:#64748b;margin-top:.5rem;font-size:.88rem;">'
                    f'{_html.escape(note or "No eligible attractions were available for this day.")}</p></div>',
                    unsafe_allow_html=True,
                )
                continue

            for leg in legs:
                att = leg["attraction"]
                tr = leg["transport"]
                icon = cat_icon(att.get("category", ""))
                cat_str = att.get("category") or att.get("subcategory") or "Attraction"
                cost = att.get("cost")
                if att.get("source_type") == "synthetic":
                    cost_str = (
                        "Entry fee estimate: Free"
                        if cost == 0
                        else f"Entry fee estimate: Paid · ₹{cost:,.0f} per person"
                    )
                else:
                    cost_str = "Entry fee unavailable" if cost is None else "Free entry" if cost == 0 else f"₹{cost:,.0f} entry"
                duration = att.get("duration")
                dur_str = "Visit duration unavailable" if duration is None else f"{duration} min"
                rating = att.get("rating")
                rating_str = f"⭐ {rating:.1f}" if rating is not None else ""

                if tr["status"] == "calculated":
                    source_label = "estimate"
                    travel_str = (
                        f"{_html.escape(str(tr.get('origin') or 'Origin'))} → "
                        f"{_html.escape(str(tr.get('destination') or att['name']))}: "
                        f"straight-line estimate (not road distance), {tr['distance_km']} km · "
                        f"~{tr['time_min']} min · ₹{tr['cost']:.2f} · {source_label}"
                    )
                else:
                    travel_str = f"Travel unavailable: {tr.get('reason') or 'verified coordinates are missing'}"

                st.markdown(f"""
                <div class="att-row">
                  <div class="att-icon">{icon}</div>
                  <div class="att-body">
                    <h4>{_html.escape(att['name'])}</h4>
                    <p>{_html.escape(cat_str)} &nbsp;·&nbsp; {cost_str} &nbsp;·&nbsp; {dur_str} {rating_str}</p>
                    <p style="color:#94a3b8;font-size:.78rem;">{travel_str}</p>
                    <p style="color:#64748b;font-size:.78rem;">{_html.escape(leg.get('recommendation_reason') or '')}</p>
                  </div>
                </div>
                """, unsafe_allow_html=True)

            return_route = day.get("return_transport")
            if return_route:
                if return_route.get("status") == "calculated":
                    return_description = (
                        f"{_html.escape(str(return_route.get('origin') or 'Origin unavailable'))} → "
                        f"{_html.escape(str(return_route.get('destination') or 'Destination unavailable'))} · "
                        f"{return_route.get('distance_km')} km · ~{return_route.get('time_min')} min · "
                        f"₹{return_route.get('cost')} · straight-line estimate, not road routing"
                    )
                else:
                    return_description = (
                        f"Return leg unavailable: {return_route.get('reason') or 'location data unavailable'}"
                    )
                st.caption(f"Return leg: {return_description}")

    with right:
        _render_accommodation(itinerary, destination, result.get("accommodation"))
        st.markdown("")
        _render_budget(br)
        st.markdown("")
        _render_constraints(result.get("constraints", {}))
        st.markdown("")
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown("**⚙️ Optimization Info**")
        st.caption("Strategy: Deterministic greedy distribution (equal attractions per day, sorted by preference score).")
        st.caption("Transport: Haversine straight-line distance (not road-network routing).")
        st.caption("OR-Tools optimization: Not yet implemented.")
        st.markdown('</div>', unsafe_allow_html=True)


def page_trips():
    user = ss("user_email")
    st.subheader("📋 My Trips")

    trips, err = api("get", f"/trips/{user}")
    if err:
        st.error(err)
        return

    if not trips:
        st.info("You haven't planned any trips yet.")
        if st.button("Plan Your First Trip →"):
            st.session_state.page = "plan"
            st.rerun()
        return

    for t in trips:
        req = t["request"]
        dest = req.get("destination", "")
        dur = req.get("duration", "")
        budget = req.get("budget", "")
        travelers = req.get("travelers", "")
        interests = ", ".join(req.get("interests", []))
        created = t.get("created_at", "")[:10]
        result = t["result"]
        br = result.get("budget", {})
        total_cost = br.get("known_cost_total")
        total_label = "Known cost total" if not br.get("is_estimate_complete") else "Estimated cost"
        total_text = "Unavailable" if total_cost is None else f"₹{total_cost:,.2f}"

        col1, col2 = st.columns([3, 1])
        with col1:
            st.markdown(
                f'<div class="card">'
                f'<b>📍 {_html.escape(dest)}</b> &nbsp;·&nbsp; {dur} days &nbsp;·&nbsp; {travelers} travellers<br>'
                f'<span style="color:#64748b;font-size:.88rem;">Budget: ₹{float(budget):,.0f} &nbsp;·&nbsp; '
                f'{total_label}: {total_text} &nbsp;·&nbsp; Interests: {_html.escape(interests)}</span><br>'
                f'<span style="color:#94a3b8;font-size:.8rem;">Planned on {created}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )
        with col2:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("View →", key=f"view_{t['trip_id']}"):
                st.session_state.trip_id = t["trip_id"]
                st.session_state.itinerary = t["result"]
                st.session_state.itinerary_req = t["request"]
                st.session_state.page = "itinerary"
                st.rerun()


# ─── Router ──────────────────────────────────────────────────────────────────
def main():
    user = ss("user_email")
    page = ss("page", "home")

    if user:
        render_navbar()
        if page == "dashboard":
            page_dashboard()
        elif page == "plan":
            page_plan()
        elif page == "itinerary":
            page_itinerary()
        elif page == "trips":
            page_trips()
        else:
            page_dashboard()
    else:
        page_landing()


if __name__ == "__main__":
    main()
