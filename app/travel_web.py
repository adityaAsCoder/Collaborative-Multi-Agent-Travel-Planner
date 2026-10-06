"""End-user travel discovery and itinerary website."""

import html

import streamlit as st

from app.data.catalog import (
    build_itinerary,
    create_user,
    destination_attractions,
    destination_hotels,
    load_catalog,
    search_destinations,
    verify_user,
)


st.set_page_config(
    page_title="WanderWise | India travel planning",
    page_icon="✈️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    .stApp { background: #f7f8fc; }
    .hero { padding: 2.5rem 2.8rem; border-radius: 1.25rem;
            background: linear-gradient(120deg, #102a43, #176b87); color: white; }
    .hero h1 { font-size: 3rem; margin-bottom: .4rem; }
    .card { padding: 1rem 1.1rem; border: 1px solid #e4e7ec; border-radius: .8rem;
            background: white; min-height: 130px; }
    .muted { color: #667085; font-size: .9rem; }
    </style>
    """,
    unsafe_allow_html=True,
)


def auth_screen() -> None:
    st.markdown(
        '<div class="hero"><h1>WanderWise</h1><p>Find places worth remembering, then build a trip around them.</p></div>',
        unsafe_allow_html=True,
    )
    st.write("")
    login, signup = st.tabs(["Log in", "Create account"])
    with login:
        with st.form("login_form"):
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Log in", type="primary")
        if submitted:
            if verify_user(email, password):
                st.session_state.user = email.strip().lower()
                st.rerun()
            st.error("Email or password is incorrect.")
    with signup:
        with st.form("signup_form"):
            email = st.text_input("Email", key="signup_email")
            password = st.text_input("Password (8+ characters)", type="password", key="signup_password")
            confirm = st.text_input("Confirm password", type="password")
            submitted = st.form_submit_button("Create account", type="primary")
        if submitted:
            if password != confirm:
                st.error("Passwords do not match.")
            else:
                ok, message = create_user(email, password)
                if ok:
                    st.success(message + " You can now log in.")
                else:
                    st.error(message)


def render_destination(destination, attractions, hotels) -> None:
    name = destination["destination_name"]
    st.markdown(f"## {html.escape(name)}")
    st.caption(f"{destination['state']} · {destination['country']}")
    left, right = st.columns([1.4, 1])
    with left:
        st.subheader("Top things to do")
        if attractions.empty:
            st.info("This destination is in the catalog, but attraction details are not available yet.")
        for _, attraction in attractions.head(12).iterrows():
            title = str(attraction["name"])
            category = str(attraction["category"] or attraction["subcategory"] or "Experience")
            rating = float(attraction["rating"] or 0)
            cost = float(attraction["estimated_cost"] or 0)
            description = str(attraction["description"] or "A place to add to your travel list.")
            st.markdown(
                f'<div class="card"><b>{html.escape(title)}</b><br>'
                f'<span class="muted">{html.escape(category)} · ⭐ {rating:.1f} · '
                f'Estimated entry: ₹{cost:,.0f}</span><p>{html.escape(description)}</p></div>',
                unsafe_allow_html=True,
            )
            st.write("")
    with right:
        st.subheader("Stay options")
        if hotels.empty:
            st.info("No hotel record is linked to this destination in the supplied hotel dataset.")
        else:
            for _, hotel in hotels.head(8).iterrows():
                price = float(hotel["price_per_night"] or 0)
                rating = float(hotel["rating"] or 0)
                st.markdown(
                    f"**{html.escape(str(hotel['name']))}**  \n"
                    f"₹{price:,.0f}/night · ⭐ {rating:.1f}  \n"
                    f"<span class='muted'>{html.escape(str(hotel['address']))}</span>",
                    unsafe_allow_html=True,
                )


def main() -> None:
    if "user" not in st.session_state:
        auth_screen()
        return

    destinations, attractions, hotels = load_catalog()
    with st.sidebar:
        st.markdown("### ✈️ WanderWise")
        st.caption(f"Signed in as {st.session_state.user}")
        if st.button("Log out"):
            del st.session_state["user"]
            st.rerun()
        st.divider()
        query = st.text_input("Search destinations", placeholder="Jaipur, Kerala, mountains...")
        interest_text = st.text_input("Interests", placeholder="history, beaches, food")
        duration = st.slider("Trip length (days)", 1, 14, 3)

    st.markdown(
        '<div class="hero"><h1>Plan the trip you will talk about.</h1>'
        '<p>Search a destination, discover dataset-backed places, and get a practical day-by-day shortlist.</p></div>',
        unsafe_allow_html=True,
    )
    matches = search_destinations(destinations, query)
    st.write("")
    st.subheader("Explore destinations")
    st.caption(f"{len(matches)} destination(s) found from the curated catalog.")
    if matches.empty:
        st.warning("No matching destination. Try a city, state, or country name.")
        return

    labels = [
        f"{row.destination_name} · {row.state}" for row in matches.itertuples()
    ]
    selected_label = st.selectbox("Choose a destination", labels)
    selected_index = labels.index(selected_label)
    destination = matches.iloc[selected_index]
    interests = [item.strip() for item in interest_text.split(",") if item.strip()]
    ranked = destination_attractions(attractions, destination["destination_id"], interests)
    linked_hotels = destination_hotels(
        hotels, destination["destination_id"], destination["destination_name"]
    )
    render_destination(destination, ranked, linked_hotels)

    st.divider()
    st.subheader("Your suggested itinerary")
    if ranked.empty:
        st.info("Add another destination or choose one with attraction records to generate a plan.")
    else:
        itinerary = build_itinerary(ranked, duration)
        for day in itinerary:
            with st.expander(f"Day {day['day']}", expanded=day["day"] == 1):
                if not day["attractions"]:
                    st.caption("Free day")
                for attraction in day["attractions"]:
                    st.write(f"**{attraction['name']}** · {attraction.get('category') or 'Experience'}")
                    st.caption(attraction.get("description") or "Plan this experience around your interests.")


if __name__ == "__main__":
    main()
