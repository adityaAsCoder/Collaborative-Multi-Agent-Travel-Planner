import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { fetchApi } from '../lib/api';

export default function Register() {
    const navigate = useNavigate();
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [confirmPassword, setConfirmPassword] = useState('');
    const [error, setError] = useState(null);
    const [loading, setLoading] = useState(false);

    const handleSubmit = async (e) => {
        e.preventDefault();
        setError(null);
        if (password !== confirmPassword) {
            return setError('Passwords do not match');
        }
        setLoading(true);
        try {
            await fetchApi('/auth/register', {
                method: 'POST',
                body: JSON.stringify({ email, password })
            });
            navigate('/login');
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="auth-layout">
            <div className="auth-visual register-visual"><div className="auth-visual-content"><div className="eyebrow">Travel with intention</div><h1>Make room for wonder.</h1><p>Create a free account and keep every carefully planned journey in one place.</p></div></div>
            <div className="auth-card">
            <div className="eyebrow">Start planning</div><h2>Create your account</h2><p className="muted">Your plans are private to your account and saved only when you choose.</p>

            {error && <div className="error">{error}</div>}

            <form onSubmit={handleSubmit}>
                <div className="field">
                    <label htmlFor="register-email">Email</label>
                    <input
                        id="register-email"
                        type="email"
                        value={email}
                        onChange={e => setEmail(e.target.value)}
                        required
                        autoFocus
                    />
                </div>
                <div className="field">
                    <label htmlFor="register-password">Password</label>
                    <input
                        id="register-password"
                        type="password"
                        value={password}
                        onChange={e => setPassword(e.target.value)}
                        required
                        minLength={8}
                    />
                </div>
                <div className="field">
                    <label htmlFor="register-confirm-password">Confirm Password</label>
                    <input
                        id="register-confirm-password"
                        type="password"
                        value={confirmPassword}
                        onChange={e => setConfirmPassword(e.target.value)}
                        required
                        minLength={8}
                    />
                </div>
                <button type="submit" disabled={loading} className="btn btn-primary">
                    {loading ? 'Creating account...' : 'Sign Up'}
                </button>
            </form>
            <div className="auth-link">
                Already have an account? <Link to="/login">Log in</Link>
            </div>
            </div>
        </div>
    );
}
