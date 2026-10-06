import React from 'react';
import { Link } from 'react-router-dom';
import { MapPin, Landmark, GitBranch, ArrowRight, Workflow, Sparkles, ShieldCheck, WalletCards } from 'lucide-react';

export default function Home() {
    return (
        <div>
            <section className="hero">
                <div>
                    <div className="eyebrow">Real data. Thoughtful planning.</div>
                    <h1>Plan smarter.<br />Travel better.</h1>
                    <p className="lead">Build a personalized, budget-aware itinerary from verified Indian tourism data, with every recommendation grounded in the planner you already trust.</p>
                    <div className="actions">
                        <Link to="/register" className="btn btn-primary">Plan my trip <ArrowRight size={17} /></Link>
                        <Link to="/login" className="btn btn-secondary">Sign in</Link>
                    </div>
                </div>
                <div className="hero-art">
                    <div><Workflow size={34} /><h3 style={{ marginTop: 18 }}>One request, many specialists.</h3><p style={{ color: '#d8f3f6', lineHeight: 1.5 }}>Research, preference, accommodation, transport, budget, constraints, and optimization work together.</p></div>
                    <div className="route"><span>Jaipur</span><ArrowRight size={16} /><span>3 days</span><ArrowRight size={16} /><span>Ready</span></div>
                </div>
            </section>

            <section className="home-showcase">
                <div className="showcase-copy"><div className="eyebrow">Made for India</div><h2>From first idea to a trip you can actually follow.</h2><p className="lead">Choose a destination, share what you enjoy, and get a clear plan built from the attractions our data can verify.</p><Link to="/register" className="btn btn-primary">Start exploring <ArrowRight size={17} /></Link></div>
                <div className="showcase-images"><div className="showcase-image image-jaipur"><span>Jaipur</span></div><div className="showcase-image image-varanasi"><span>Varanasi</span></div><div className="showcase-image image-kerala"><span>Kerala</span></div></div>
            </section>

            <section className="feature-grid">
                <div className="feature">
                    <MapPin color="var(--brand)" size={30} />
                    <h3>93 destinations</h3>
                    <p>Explore verified places from the existing travel database.</p>
                </div>
                <div className="feature">
                    <Landmark color="var(--brand)" size={30} />
                    <h3>378 attractions</h3>
                    <p>Use real entry costs, durations, ratings, and locations.</p>
                </div>
                <div className="feature">
                    <GitBranch color="var(--brand)" size={30} />
                    <h3>Multi-agent planning</h3>
                    <p>Specialized agents collaborate without inventing unavailable facts.</p>
                </div>
            </section>
            <section className="home-benefits"><div><Sparkles color="var(--brand)" /><strong>Personalized</strong><span>Interests guide the ranking.</span></div><div><ShieldCheck color="var(--brand)" /><strong>Grounded</strong><span>Unavailable facts stay visible.</span></div><div><WalletCards color="var(--brand)" /><strong>Budget-aware</strong><span>Costs are calculated from the itinerary.</span></div></section>
        </div>
    );
}
