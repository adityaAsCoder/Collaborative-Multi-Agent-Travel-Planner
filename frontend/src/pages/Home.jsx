import React from 'react';
import { Link } from 'react-router-dom';
import { MapPin, Landmark, GitBranch, ArrowRight, Workflow, Sparkles, ShieldCheck, WalletCards } from 'lucide-react';

export default function Home() {
    return (
        <div>
            <section className="hero">
                <div>
                    <div className="eyebrow">Demonstration-ready travel planning</div>
                    <h1>Plan smarter.<br />Travel better.</h1>
                    <p className="lead">Build a personalized itinerary with attractions, sample stays, illustrative entry fees, and a budget for 20 configured destinations. Demonstration values are clearly labeled.</p>
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
                <div className="showcase-copy"><div className="eyebrow">Made for India</div><h2>From first idea to a trip you can actually follow.</h2><p className="lead">Choose a destination and share what you enjoy. Twenty demo destinations include clearly labeled illustrative attraction details and sample accommodation.</p><Link to="/register" className="btn btn-primary">Start exploring <ArrowRight size={17} /></Link></div>
                <div className="showcase-images"><div className="showcase-image image-jaipur"><span>Jaipur</span></div><div className="showcase-image image-varanasi"><span>Varanasi</span></div><div className="showcase-image image-kerala"><span>Kerala</span></div></div>
            </section>

            <section className="feature-grid">
                <div className="feature">
                    <MapPin color="var(--brand)" size={30} />
                    <h3>93 destinations</h3>
                    <p>Explore the India destination catalog; 20 places have full illustrative demo plans.</p>
                </div>
                <div className="feature">
                    <Landmark color="var(--brand)" size={30} />
                    <h3>378 attractions</h3>
                    <p>Three recommendations per demo destination include illustrative fees and durations.</p>
                </div>
                <div className="feature">
                    <GitBranch color="var(--brand)" size={30} />
                    <h3>Multi-agent planning</h3>
                    <p>Research, preferences, accommodation, routing, and budget agents build each itinerary.</p>
                </div>
            </section>
            <section className="home-benefits"><div><Sparkles color="var(--brand)" /><strong>Personalized</strong><span>Interests guide the ranking.</span></div><div><ShieldCheck color="var(--brand)" /><strong>Transparent</strong><span>Demo fees, stays, and estimates are labeled.</span></div><div><WalletCards color="var(--brand)" /><strong>Budget-aware</strong><span>Illustrative costs are totaled for the plan.</span></div></section>
        </div>
    );
}
