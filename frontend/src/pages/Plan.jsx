import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { fetchApi } from '../lib/api';

const interests = ['History', 'Forts', 'Food', 'Nature', 'Religious', 'Culture', 'Adventure', 'Beach'];
const locationImages = [
    ['Jaipur', 'https://images.unsplash.com/photo-1477587458883-47145ed94245?auto=format&fit=crop&w=700&q=80'],
    ['Varanasi', 'https://images.unsplash.com/photo-1561361058-c24cecae35ca?auto=format&fit=crop&w=700&q=80'],
    ['Kerala', 'https://images.unsplash.com/photo-1602216056096-3b40cc0c9944?auto=format&fit=crop&w=700&q=80'],
];

export default function Plan() {
    const navigate = useNavigate();
    const [destinations, setDestinations] = useState([]);
    const [form, setForm] = useState({ destination: '', duration: 3, travelers: 2, budget: 20000, currency: 'INR', interests: ['History'], accommodation_preference: 'any', max_daily_travel_time: '' });
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');
    useEffect(() => { fetchApi('/destinations').then(setDestinations).catch(e => setError(e.message)); }, []);
    const update = (key, value) => setForm(prev => ({ ...prev, [key]: value }));
    const toggleInterest = interest => update('interests', form.interests.includes(interest) ? form.interests.filter(item => item !== interest) : [...form.interests, interest]);
    async function submit(event) {
        event.preventDefault(); setError('');
        if (!form.destination || !form.interests.length) { setError('Choose a destination and at least one interest.'); return; }
        setLoading(true);
        try {
            const result = await fetchApi('/plan', { method: 'POST', body: JSON.stringify({ ...form, duration: Number(form.duration), travelers: Number(form.travelers), budget: Number(form.budget), max_daily_travel_time: form.max_daily_travel_time ? Number(form.max_daily_travel_time) : null }) });
            sessionStorage.setItem('last_itinerary', JSON.stringify(result));
            navigate('/itinerary', { state: result });
        } catch (e) { setError(e.message); } finally { setLoading(false); }
    }
    return <div className="form-card"><div className="page-header"><div><div className="eyebrow">Create a plan</div><h2>Where will you go?</h2><p>Demo destinations include illustrative accommodation and attraction details, clearly labeled for demonstration.</p></div></div><div className="location-strip">{locationImages.map(([name, image]) => <div className="location-card" key={name} style={{ backgroundImage: `url(${image})` }}><span>{name}</span></div>)}</div><div className="card">
        {error && <div className="error">{error}</div>}
        <form onSubmit={submit}><div className="form-grid">
            <div className="field full"><label htmlFor="destination">Destination</label><select id="destination" value={form.destination} onChange={e => update('destination', e.target.value)} required><option value="">Select a destination</option>{destinations.map(d => <option key={d.id} value={d.name}>{d.name}{d.state ? `, ${d.state}` : ''}</option>)}</select></div>
            <div className="field"><label htmlFor="duration">Duration (days)</label><input id="duration" type="number" min="1" value={form.duration} onChange={e => update('duration', e.target.value)} /></div>
            <div className="field"><label htmlFor="travelers">Travellers</label><input id="travelers" type="number" min="1" value={form.travelers} onChange={e => update('travelers', e.target.value)} /></div>
            <div className="field"><label htmlFor="budget">Total budget</label><input id="budget" type="number" min="0" step="100" value={form.budget} onChange={e => update('budget', e.target.value)} /></div>
            <div className="field"><label htmlFor="accommodation">Accommodation</label><select id="accommodation" value={form.accommodation_preference} onChange={e => update('accommodation_preference', e.target.value)}><option value="any">Any</option><option value="budget">Budget</option><option value="standard">Standard</option><option value="luxury">Luxury</option></select></div>
            <div className="field full"><label>Interests</label><div className="check-grid">{interests.map(item => <button type="button" key={item} className={`check ${form.interests.includes(item) ? 'selected' : ''}`} onClick={() => toggleInterest(item)}>{item}</button>)}</div></div>
            <div className="field full"><label htmlFor="travel-time">Maximum daily travel time (optional, minutes)</label><input id="travel-time" type="number" min="1" value={form.max_daily_travel_time} onChange={e => update('max_daily_travel_time', e.target.value)} placeholder="Leave blank for planner default" /></div>
        </div><div className="actions"><button className="btn btn-primary" disabled={loading}>{loading ? 'Planning your trip…' : 'Build my itinerary'}</button></div></form>
    </div></div>;
}
