import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { fetchApi } from '../lib/api';

export default function Trips() {
    const navigate = useNavigate();
    const [trips, setTrips] = useState([]);
    const [error, setError] = useState('');
    useEffect(() => { fetchApi(`/trips/${encodeURIComponent(localStorage.getItem('user_email') || '')}`).then(setTrips).catch(e => setError(e.message)); }, []);
    if (error) return <div className="error">{error}</div>;
    return <div><div className="page-header"><div><div className="eyebrow">Your archive</div><h2>My trips</h2><p>Revisit plans generated from the real planner.</p></div><Link to="/plan" className="btn btn-primary">New trip</Link></div>{!trips.length ? <div className="card empty"><h3>No saved trips yet</h3><p>Your generated itineraries will appear here.</p><Link to="/plan" className="btn btn-primary">Create your first trip</Link></div> : <div className="trip-grid">{trips.map(trip => <article className="card trip-card" key={trip.trip_id}><div><div className="eyebrow">{new Date(trip.created_at).toLocaleDateString()}</div><h3>{trip.request.destination}</h3><p className="muted">{trip.request.duration} days · {trip.request.travelers} travellers</p></div><div className="actions" style={{ marginTop: 'auto' }}><button className="btn btn-secondary" onClick={() => { const result = { ...trip.result, request: trip.result.request || trip.request }; sessionStorage.setItem('last_itinerary', JSON.stringify(result)); navigate('/itinerary', { state: result }); }}>View itinerary</button></div></article>)}</div>}</div>;
}
