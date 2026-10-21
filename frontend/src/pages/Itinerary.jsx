import { Link, useLocation } from 'react-router-dom';
import { useState } from 'react';
import { fetchApi } from '../lib/api';

function money(value, currency = 'INR') {
    const amount = value === null || value === undefined || value === '' ? null : Number(value);
    if (amount === null || !Number.isFinite(amount)) return 'Unavailable';
    return new Intl.NumberFormat('en-IN', { style: 'currency', currency, maximumFractionDigits: 0 }).format(amount);
}

export default function Itinerary() {
    const location = useLocation();
    const [saveState, setSaveState] = useState('idle');
    const result = location.state || JSON.parse(sessionStorage.getItem('last_itinerary') || 'null');
    if (!result) return <div className="card empty"><h2>No itinerary selected</h2><p>Start a new plan to see your personalized days here.</p><Link to="/plan" className="btn btn-primary">Plan a trip</Link></div>;
    const request = result.request || {};
    const budget = result.budget || {};
    const accommodation = result.accommodation || {};
    const days = (() => {
        const existing = new Map((result.itinerary || []).map(day => [day.day, day]));
        return Array.from({ length: Number(request.duration || 0) }, (_, index) => existing.get(index + 1) || { day: index + 1, legs: [], note: 'No eligible attractions were available for this day.' });
    })();
    const selectedHotel = days.find(day => day.hotel)?.hotel;
    const hasAccommodation = Boolean(selectedHotel);
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
        {saveState !== 'idle' && saveState !== 'saving' && saveState !== 'saved' && <div className="error">{saveState}</div>}
        {result.constraints && result.constraints.status !== 'feasible' && <div className="notice" style={{ marginBottom: 18 }}>{result.constraints.status === 'incomplete' ? 'Some constraints could not be verified: ' : 'Some constraints need attention: '}{[...(result.constraints.violations || []), ...(result.constraints.warnings || [])].join(' · ')}</div>}
        {days.map(day => <section className="card day" key={day.day}>
            <div className="day-title"><span>Day {day.day}</span><span>{day.hotel ? `${day.hotel.name} · ${money(day.hotel.price, request.currency)}/night${day.hotel.rating != null ? ` · Rating ${day.hotel.rating}` : ''}` : 'Accommodation unavailable'}</span></div>
            {day.legs?.length ? day.legs.map((leg, index) => {
                const att = leg.attraction;
                const transport = leg.transport || {};
                const entryFee = att.cost === null || att.cost === undefined ? 'Entry fee unavailable' : att.cost === 0 ? 'Free entry' : `Entry ${money(att.cost, request.currency)}`;
                const duration = att.duration == null ? 'Visit duration unavailable' : `${att.duration} min`;
                const travel = transport.status === 'calculated'
                    ? `Straight-line estimate: ${transport.distance_km} km · ~${transport.time_min} min`
                    : `Travel unavailable: ${transport.reason || 'No verified route coordinates.'}`;
                return <div className="leg" key={`${day.day}-${att.id}`}>
                    <div className="number">{index + 1}</div>
                    <div>
                        <div className="leg-title">{att.name}</div>
                        <div className="leg-meta">{att.category || att.subcategory || 'Attraction'} · {duration} · {entryFee}<br />{travel}</div>
                        {leg.recommendation_reason && <div className="leg-meta"><strong>Why this place:</strong> {leg.recommendation_reason}</div>}
                    </div>
                    <div className="price">{money(att.cost, request.currency)}</div>
                </div>;
            }) : <div className="empty"><p>{day.note || 'No activities scheduled.'}</p><span className="muted">No attraction has been invented to fill this day.</span></div>}
        </section>)}
        <div className="budget">
            <div className="card">
                <h3>Budget summary</h3>
                <div className="budget-row"><span>Your budget</span><strong>{money(request.budget, request.currency)}</strong></div>
                <div className="budget-row"><span>Accommodation{budget.accommodation_cost_complete === false ? ' (unavailable)' : ''}</span><strong>{hasAccommodation || budget.accommodation_cost === 0 ? money(budget.accommodation_cost, request.currency) : 'Not available — excluded'}</strong></div>
                <div className="budget-row"><span>Attractions{budget.attraction_cost_complete === false ? ' (partial)' : ''}</span><strong>{money(budget.attraction_cost, request.currency)}</strong></div>
                <div className="budget-row"><span>Transport{budget.transport_cost_complete === false ? ' (partial)' : ''}</span><strong>{money(budget.transport_cost, request.currency)}</strong></div>
                <div className="budget-row total"><span>Estimated cost of available components</span><strong>{money(budget.total_estimated_cost, request.currency)}</strong></div>
                <div className="budget-row"><span>Average per day (available components)</span><strong>{money(budget.daily_cost, request.currency)}</strong></div>
                <div className="budget-row"><span>Remaining budget (complete estimates only)</span><strong>{budget.total_is_complete ? money(budget.remaining_budget, request.currency) : 'Unavailable — costs incomplete'}</strong></div>
                {!budget.total_is_complete && <p className="notice" style={{ marginTop: 14 }}>This is not the complete trip cost. {budget.unknown_components?.join(' ') || 'Some costs could not be verified.'}</p>}
            </div>
            <div className="card">
                <h3>Accommodation</h3>
                {selectedHotel
                    ? <p className="muted">Selected stay: <strong>{selectedHotel.name}</strong> · {money(selectedHotel.price, request.currency)} per night{selectedHotel.rating ? ` · Rating ${selectedHotel.rating}` : ''}. This nightly rate is included in the estimated accommodation total.</p>
                    : <p className="muted">{accommodation.reason || `No hotel with validated location and pricing was available for ${request.destination}.`} Accommodation is not included in the estimated total; it is not free.</p>}
                <h3>Planning status</h3>
                <p className="muted">{result.preference_score ? `Preference score: ${result.preference_score}` : 'Preference score unavailable'}</p>
                <p className="muted">{result.candidate_hotels?.length ? `${result.candidate_hotels.length} hotels with validated coordinates were considered.` : 'No validated hotel candidates were found.'}</p>
            </div>
        </div>
    </div>;
}
