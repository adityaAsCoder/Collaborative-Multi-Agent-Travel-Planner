import { Link, useLocation } from 'react-router-dom';
import { useState } from 'react';
import { fetchApi } from '../lib/api';

function money(value, currency = 'INR') {
    return new Intl.NumberFormat('en-IN', { style: 'currency', currency, maximumFractionDigits: 0 }).format(Number(value || 0));
}

export default function Itinerary() {
    const location = useLocation();
    const [saveState, setSaveState] = useState('idle');
    const result = location.state || JSON.parse(sessionStorage.getItem('last_itinerary') || 'null');
    if (!result) return <div className="card empty"><h2>No itinerary selected</h2><p>Start a new plan to see your personalized days here.</p><Link to="/plan" className="btn btn-primary">Plan a trip</Link></div>;
    const request = result.request || {};
    const budget = result.budget || {};
    const days = (() => {
        const existing = new Map((result.itinerary || []).map(day => [day.day, day]));
        return Array.from({ length: Number(request.duration || 0) }, (_, index) => existing.get(index + 1) || { day: index + 1, legs: [], note: 'No eligible attractions were available for this day.' });
    })();
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
        <div className="page-header"><div><div className="eyebrow">Your itinerary</div><h2>{request.destination || 'Trip plan'}</h2><p>{request.duration} days · {request.travelers} traveller{Number(request.travelers) === 1 ? '' : 's'} · {request.interests?.join(', ')}</p></div><div className="actions" style={{ marginTop: 0 }}><button className="btn btn-primary" onClick={saveTrip} disabled={saveState === 'saving' || saveState === 'saved'}>{saveState === 'saving' ? 'Saving…' : saveState === 'saved' ? 'Saved to My Trips' : 'Save this trip'}</button><Link to="/plan" className="btn btn-secondary">Plan another</Link></div></div>
        {result.validation_error && <div className="notice" style={{ marginBottom: 18 }}><strong>Planning note:</strong> {result.validation_error} The days below are shown so you can still review the request and try another destination.</div>}
        {result.planning_note && <div className="notice" style={{ marginBottom: 18 }}><strong>How this was matched:</strong> {result.planning_note}</div>}
        {saveState !== 'idle' && saveState !== 'saving' && saveState !== 'saved' && <div className="error">{saveState}</div>}
        {result.constraints && !result.constraints.feasible && <div className="notice" style={{ marginBottom: 18 }}>Some constraints need attention: {result.constraints.violations.join(' · ')}</div>}
        {days.map(day => <section className="card day" key={day.day}><div className="day-title"><span>Day {day.day}</span><span>{day.hotel ? day.hotel.name : 'Accommodation unavailable'}</span></div>{day.legs?.length ? day.legs.map((leg, index) => <div className="leg" key={`${day.day}-${leg.attraction.id}`}><div className="number">{index + 1}</div><div><div className="leg-title">{leg.attraction.name}</div><div className="leg-meta">{leg.attraction.category || 'Attraction'} · {leg.attraction.duration} min · Entry {money(leg.attraction.cost, request.currency)}<br />Travel: {leg.transport.status === 'calculated' ? `${leg.transport.distance_km} km · ${leg.transport.time_min} min` : 'Distance unavailable'}</div></div><div className="price">{money(leg.attraction.cost, request.currency)}</div></div>) : <div className="empty"><p>{day.note || 'No activities scheduled.'}</p><span className="muted">This day is intentionally open; no eligible attraction was invented.</span></div>}</section>)}
        <div className="budget"><div className="card"><h3>Budget summary</h3><div className="budget-row"><span>Accommodation</span><strong>{money(budget.accommodation_cost, request.currency)}</strong></div><div className="budget-row"><span>Attractions</span><strong>{money(budget.attraction_cost, request.currency)}</strong></div><div className="budget-row"><span>Transport</span><strong>{money(budget.transport_cost, request.currency)}</strong></div><div className="budget-row total"><span>Estimated total</span><strong>{money(budget.total_estimated_cost, request.currency)}</strong></div></div><div className="card"><h3>Planning status</h3><p className="muted">{result.preference_score ? `Preference score: ${result.preference_score}` : 'Preference score unavailable'}</p><p className="muted">{result.candidate_hotels?.length ? `${result.candidate_hotels.length} hotels with validated coordinates were considered.` : 'No hotels with validated coordinates were available for this destination. We have not invented accommodation details.'}</p></div></div>
    </div>;
}
