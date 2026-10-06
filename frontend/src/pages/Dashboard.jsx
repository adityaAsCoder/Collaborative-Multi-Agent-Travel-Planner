import { Link } from 'react-router-dom';
import { Compass, History, ShieldCheck, ArrowRight, MapPin, Sparkles } from 'lucide-react';

export default function Dashboard() {
    const email = localStorage.getItem('user_email') || '';
    const firstName = email.split('@')[0] || 'traveller';
    return <div className="dashboard">
        <section className="dashboard-hero">
            <div className="dashboard-hero-copy">
                <div className="eyebrow">Your travel workspace</div>
                <h1>Welcome back,<br /><span>{firstName}</span></h1>
                <p>Turn your next idea into a clear, memorable day-by-day plan built around what you love.</p>
                <div className="actions">
                    <Link to="/plan" className="btn btn-light">Plan a trip <ArrowRight size={17} /></Link>
                    <Link to="/trips" className="btn btn-outline-light">View saved trips</Link>
                </div>
            </div>
            <div className="dashboard-hero-art">
                <div className="floating-badge"><Sparkles size={15} /> Made for curious travellers</div>
                <div className="map-pin pin-one"><MapPin size={20} /></div>
                <div className="map-pin pin-two"><MapPin size={20} /></div>
                <div className="route-line" />
                <div className="hero-destination"><span>Next stop</span><strong>India awaits</strong></div>
            </div>
        </section>
        <div className="stat-grid">
            <div className="stat"><Compass color="var(--brand)" /><strong>Verified</strong><span className="muted">Real destination and attraction data</span></div>
            <div className="stat"><History color="var(--brand)" /><strong>Saved</strong><span className="muted">Your plans stay available in My Trips</span></div>
            <div className="stat"><ShieldCheck color="var(--brand)" /><strong>Transparent</strong><span className="muted">Unavailable hotel data stays unavailable</span></div>
        </div>
        <section className="dashboard-lower">
            <div className="card planning-card"><div className="eyebrow">Simple by design</div><h2>How planning works</h2><p className="muted">Tell us where you are going, how long you have, who is travelling, and what matters to you. Our specialized agents coordinate research, preferences, transport, budget, constraints, and optimization to return a grounded itinerary.</p><Link to="/plan" className="text-link">Start with your next destination <ArrowRight size={16} /></Link></div>
            <div className="dashboard-photo"><div><MapPin size={18} /><strong>Find your kind of India</strong><span>Forts, food, coastlines and stories</span></div></div>
        </section>
    </div>;
}
