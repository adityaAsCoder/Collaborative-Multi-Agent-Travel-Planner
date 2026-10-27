import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { fetchApi } from '../lib/api';

export default function Login() {
    const navigate = useNavigate();
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [error, setError] = useState(null);
    const [loading, setLoading] = useState(false);

    const handleSubmit = async (e) => {
        e.preventDefault();
        setError(null);
        setLoading(true);
        try {
            const data = await fetchApi('/auth/login', {
                method: 'POST',
                body: JSON.stringify({ email, password })
            });
            localStorage.setItem('user_email', data.email);
            const returnTo = new URLSearchParams(window.location.search).get('returnTo');
            navigate(returnTo && returnTo.startsWith('/') ? returnTo : '/dashboard');
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="auth-layout">
            <div className="auth-visual login-visual"><div className="auth-visual-content"><div className="eyebrow">Your next story starts here</div><h1>Come back to the journey.</h1><p>Pick up where you left off and turn verified places across India into a plan worth following.</p></div></div>
            <div className="auth-card">
            <div className="eyebrow">Welcome to WanderWise</div><h2>Welcome back</h2><p className="muted">Sign in to view your saved trips and plan your next escape.</p>

            {error && <div className="error">{error}</div>}

            <form onSubmit={handleSubmit}>
                <div className="field">
                    <label htmlFor="login-email">Email</label>
                    <input
                        id="login-email"
                        type="email"
                        value={email}
                        onChange={e => setEmail(e.target.value)}
                        required
                        autoFocus
                    />
                </div>
                <div className="field">
                    <label htmlFor="login-password">Password</label>
                    <input
                        id="login-password"
                        type="password"
                        value={password}
                        onChange={e => setPassword(e.target.value)}
                        required
                    />
                </div>
                <button type="submit" disabled={loading} className="btn btn-primary">
                    {loading ? 'Logging in...' : 'Log In'}
                </button>
            </form>
            <div className="auth-link">
                Don't have an account? <Link to="/register">Create an account</Link>
            </div>
            </div>
        </div>
    );
}
