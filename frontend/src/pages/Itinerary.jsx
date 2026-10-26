import { Link, useLocation } from 'react-router-dom';
import { useState } from 'react';
import { fetchApi } from '../lib/api';

function money(value, currency = 'INR') {
    const amount = value === null || value === undefined || value === '' ? null : Number(value);
    if (amount === null || !Number.isFinite(amount)) return 'Unavailable';
    return new Intl.NumberFormat('en-IN', { style: 'currency', currency, maximumFractionDigits: 2 }).format(amount);
}

export default function Itinerary() {
    const location = useLocation();
    const [saveState, setSaveState] = useState('idle');
    const result = location.state || JSON.parse(sessionStorage.getItem('last_itinerary') || 'null');
    if (!result) return <div className="card empty"><h2>No itinerary selected</h2><p>Start a new plan to see your personalized days here.</p><Link to="/plan" className="btn btn-primary">Plan a trip</Link></div>;
    const request = result.request || {};
    const budget = result.budget || {};
    const isEstimateComplete = budget.is_estimate_complete ?? budget.total_is_complete ?? false;
    const accommodation = result.accommodation || {};
    const days = (() => {
        const existing = new Map((result.itinerary || []).map(day => [day.day, day]));
        return Array.from({ length: Number(request.duration || 0) }, (_, index) => existing.get(index + 1) || { day: index + 1, legs: [], note: 'No eligible attractions were available for this day.' });
    })();
    const selectedHotel = days.find(day => day.hotel)?.hotel;
    const accommodationDetails = accommodation.hotel_name
        ? accommodation
        : selectedHotel ? {
            ...selectedHotel,
            hotel_name: selectedHotel.name,
            price_per_night: selectedHotel.price_per_night ?? selectedHotel.price,
        } : accommodation;
    const hasAccommodation = Boolean(accommodationDetails.hotel_name || selectedHotel);
    const hasDemoData = budget.data_status === 'DEMO_SYNTHETIC'
        || days.some(day => day.hotel?.source_type === 'synthetic'
            || day.legs?.some(leg => leg.attraction?.source_type === 'synthetic'));
    const constraintMessages = [
        ...(result.constraints?.violations || []),
        ...(result.constraints?.warnings || []),
    ].filter(message => !(hasDemoData && message === 'Budget feasibility is not verified.'));
    const transportDescription = transport => {
        if (!transport) return null;
        if (transport.status !== 'calculated') {
            return `${transport.origin || 'Origin unavailable'} → ${transport.destination || 'destination unavailable'} · Not estimated: ${transport.reason || 'Route data unavailable.'}`;
        }
        const method = transport.method === 'haversine_straight_line_estimate'
            ? 'Straight-line estimate (not road distance)'
            : transport.method || 'Estimated route';
        const mode = transport.mode === 'car_taxi_estimate'
            ? 'Car/taxi (estimate)'
            : (transport.mode || 'Transport').replaceAll('_', ' ');
        const rate = transport.cost_per_km == null
            ? ''
            : ` (${money(transport.cost_per_km, request.currency)}/km)`;
        return `${transport.origin} → ${transport.destination} · ${transport.distance_km} km · ~${transport.time_min} min · ${mode} · ${money(transport.cost, request.currency)}${rate} · ${method}`;
    };
    async function saveTrip() {
        setSaveState('saving');
        try {
            const saved = await fetchApi('/trips', { method: 'POST', body: JSON.stringify({ email: localStorage.getItem('user_email'), request, result }) });
            const savedResult = { ...result, trip_id: saved.trip_id };
            sessionStorage.setItem('last_itinerary', JSON.stringify(savedResult));
            setSaveState('saved');
        } catch (error) {
            setSaveState(error.message);
        }
    }
    return <div>
        <div className="page-header"><div><div className="eyebrow">Your itinerary</div><h2>{request.destination || 'Trip plan'}</h2><p>{request.duration} days · {request.travelers} traveller{Number(request.travelers) === 1 ? '' : 's'} · Budget {money(request.budget, request.currency)} · {request.interests?.join(', ')}</p></div><div className="actions" style={{ marginTop: 0 }}><button className="btn btn-primary" onClick={saveTrip} disabled={saveState === 'saving' || saveState === 'saved'}>{saveState === 'saving' ? 'Saving…' : saveState === 'saved' ? 'Saved to My Trips' : 'Save this trip'}</button><Link to="/plan" className="btn btn-secondary">Plan another</Link></div></div>
        {result.validation_error && <div className="notice" style={{ marginBottom: 18 }}><strong>Planning note:</strong> {result.validation_error} The days below are shown so you can still review the request and try another destination.</div>}
        {result.planning_note && <div className="notice" style={{ marginBottom: 18 }}><strong>Planning note:</strong> {result.planning_note}</div>}
        {hasDemoData && <div className="notice" style={{ marginBottom: 18 }}><strong>Illustrative itinerary:</strong> Accommodation, attraction fees, locations, and transport costs are estimates for demonstration, not verified listings, prices, or road routes.</div>}
        {saveState !== 'idle' && saveState !== 'saving' && saveState !== 'saved' && <div className="error">{saveState}</div>}
        {result.constraints && result.constraints.status !== 'feasible' && constraintMessages.length > 0 && <div className="notice" style={{ marginBottom: 18 }}>{result.constraints.status === 'incomplete' ? 'Some constraints could not be verified: ' : 'Some constraints need attention: '}{constraintMessages.join(' · ')}</div>}
        {days.map(day => <section className="card day" key={day.day}>
            <div className="day-title"><span>Day {day.day}</span><span>{day.hotel ? day.hotel.source_type === 'synthetic' ? `${day.hotel.name} · Illustrative stay` : day.hotel.name : 'Accommodation unavailable'}</span></div>
            {day.legs?.length ? day.legs.map((leg, index) => {
                const att = leg.attraction;
                const entryFee = att.source_type === 'synthetic'
                    ? `Entry fee estimate: ${att.cost === 0 ? 'Free' : `Paid · ${money(att.cost, request.currency)} per person`}`
                    : att.cost === null || att.cost === undefined ? 'Entry fee unavailable' : att.cost === 0 ? 'Free entry' : `Entry ${money(att.cost, request.currency)}`;
                const duration = att.duration == null ? 'Visit duration unavailable' : `${att.duration} min`;
                return <div className="leg" key={`${day.day}-${att.id}`}>
                    <div className="number">{index + 1}</div>
                    <div>
                        <div className="leg-title">{att.name}</div>
                        <div className="leg-meta">{att.category || att.subcategory || 'Attraction'} · {duration} · {entryFee}{att.source_type !== 'synthetic' && att.cost_basis !== 'group' && att.cost != null ? ' per person' : ''}</div>
                        {leg.recommendation_reason && <div className="leg-meta"><strong>Why this place:</strong> {leg.recommendation_reason}</div>}
                    </div>
                    <div className="price">{money(att.cost, request.currency)}</div>
                </div>;
            }) : <div className="empty"><p>{day.note || 'No activities scheduled.'}</p><span className="muted">No attraction has been invented to fill this day.</span></div>}
        </section>)}
        <section className="card transport-breakdown">
            <h3>Transportation estimates</h3>
            {days.some(day => day.legs?.length || day.return_transport) ? days.map(day => [
                ...(day.legs || []).map((leg, index) => (
                    <div className="transport-leg" key={`${day.day}-${leg.attraction?.id || index}`}>
                        <strong>Day {day.day}</strong>
                        <div className="leg-meta">{transportDescription(leg.transport || {})}</div>
                    </div>
                )),
                ...(day.return_transport ? [<div className="transport-leg" key={`${day.day}-return`}>
                    <strong>Day {day.day} return</strong>
                    <div className="leg-meta">{transportDescription(day.return_transport)}</div>
                </div>] : []),
            ]) : <p className="muted">No transportation legs were available to estimate.</p>}
            <p className="leg-meta">Total transportation estimate: {money(budget.transportation_total ?? budget.transport_cost, request.currency)}. Unavailable legs are excluded from that partial amount and listed above.</p>
        </section>
        <div className="budget">
            <div className="card">
                <h3>Budget summary</h3>
                <div className="budget-row"><span>Your budget</span><strong>{money(request.budget, request.currency)}</strong></div>
                <div className="budget-row"><span>Accommodation{budget.accommodation_cost_complete === false ? ' (unavailable)' : ''}</span><strong>{budget.accommodation?.data_status === 'NOT_REQUIRED' ? 'Not applicable — no overnight stay' : !hasAccommodation ? 'Not available — excluded' : (budget.accommodation_total ?? budget.accommodation_cost) == null ? 'Not available — excluded' : money(budget.accommodation_total ?? budget.accommodation_cost, request.currency)}</strong></div>
                <div className="budget-row"><span>Attractions{budget.attraction_cost_complete === false ? ' (partial)' : ''}</span><strong>{money(budget.attraction_total ?? budget.attraction_cost, request.currency)}</strong></div>
                <div className="budget-row"><span>Transportation{budget.transport_cost_complete === false ? ' (partial)' : ''}</span><strong>{money(budget.transportation_total ?? budget.transport_cost, request.currency)}</strong></div>
                <div className="budget-row total"><span>{hasDemoData ? 'Illustrative trip total' : isEstimateComplete ? 'Estimated trip total' : 'Known cost total (incomplete)'}</span><strong>{money(budget.known_cost_total ?? budget.total_estimated_cost, request.currency)}</strong></div>
                <div className="budget-row"><span>Average per day (available components)</span><strong>{money(budget.daily_cost, request.currency)}</strong></div>
                <div className="budget-row"><span>{hasDemoData ? 'Budget minus illustrative costs' : 'Budget minus known costs'}</span><strong>{money(budget.remaining_budget_after_known_costs ?? budget.remaining_budget, request.currency)}</strong></div>
                {hasDemoData && <p className="notice" style={{ marginTop: 14 }}>Illustrative remainder only; it is not a spendable trip balance.</p>}
                {!isEstimateComplete && <p className="notice" style={{ marginTop: 14 }}>This arithmetic remainder is not your spendable balance because important trip costs are unknown. {budget.unknown_components?.join(' ') || 'Some costs could not be verified.'}</p>}
                <p className="leg-meta">Verified components: {money(budget.verified_cost_total, request.currency)} · Estimated components: {money(budget.estimated_cost_total, request.currency)} · Illustrative components: {money(budget.demonstration_cost_total, request.currency)}</p>
            </div>
            <div className="card">
                <h3>Accommodation</h3>
                {hasAccommodation
                    ? <>
                        <p className="muted"><strong>{accommodationDetails.hotel_name || selectedHotel.name}</strong></p>
                        {accommodationDetails.source_type === 'synthetic' && <p className="leg-meta"><strong>Illustrative stay · estimated price · not bookable</strong></p>}
                        {accommodationDetails.source_type !== 'synthetic' && <p className="muted">Verified accommodation record · {accommodationDetails.data_status || 'VERIFIED'}</p>}
                        <p className="muted">{accommodationDetails.destination || request.destination}{accommodationDetails.source_type !== 'synthetic' && accommodationDetails.address ? ` · ${accommodationDetails.address}` : ''}</p>
                        <p className="muted">Rating: {accommodationDetails.rating == null ? 'Unavailable' : accommodationDetails.rating}</p>
                        <p className="muted">{accommodationDetails.source_type === 'synthetic' ? 'Illustrative nightly rate' : 'Price per night'}: {money(accommodationDetails.price_per_night ?? selectedHotel?.price, request.currency)} · Nights: {accommodationDetails.nights ?? Math.max(0, Number(request.duration || 0) - 1)} · Rooms: {accommodationDetails.rooms_required ?? 'Unknown'}</p>
                        <p className="muted">{accommodationDetails.source_type === 'synthetic' ? 'Illustrative accommodation estimate' : 'Accommodation estimate'}: {accommodationDetails.total_accommodation_cost == null ? 'Unavailable — room occupancy or price is unknown' : money(accommodationDetails.total_accommodation_cost, request.currency)}</p>
                    </>
                    : <p className="muted">{accommodationDetails.reason || `No suitable accommodation was available for ${request.destination}.`} Accommodation is unavailable and is not free.</p>}
                <h3>Planning status</h3>
                <p className="muted">{result.preference_score ? `Preference score: ${result.preference_score}` : 'Preference score unavailable'}</p>
                <p className="muted">{result.candidate_hotels?.length ? `${result.candidate_hotels.length} accommodation candidate(s) were considered.` : 'No suitable accommodation candidates were found.'}</p>
            </div>
        </div>
    </div>;
}
