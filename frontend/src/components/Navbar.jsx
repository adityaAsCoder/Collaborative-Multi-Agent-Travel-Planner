import React from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Plane, Home, Map, ClipboardList, LogOut, User } from 'lucide-react';

export default function Navbar() {
    const navigate = useNavigate();
    const user = localStorage.getItem('user_email');

    const handleLogout = () => {
        localStorage.removeItem('user_email');
        navigate('/');
    };

    return (
        <nav className="nav">
            <div className="container nav-inner">
                    <Link to="/" className="brand">
                        <Plane size={22} />
                        <span>WanderWise</span>
                    </Link>

                    <div className="nav-links">
                        {user ? (
                            <>
                                <Link to="/dashboard">
                                    <Home size={18} /> Home
                                </Link>
                                <Link to="/plan">
                                    <Map size={18} /> Plan Trip
                                </Link>
                                <Link to="/trips">
                                    <ClipboardList size={18} /> My Trips
                                </Link>

                                <div className="h-6 w-px bg-slate-200 mx-2"></div>

                                <span className="user-pill">
                                    <User size={18} />
                                    {user.split('@')[0]}
                                </span>

                                <button onClick={handleLogout} className="btn btn-ghost">
                                    <LogOut size={18} /> Logout
                                </button>
                            </>
                        ) : (
                            <>
                                <Link to="/login">Login</Link>
                                <Link to="/register" className="btn btn-primary">
                                    Register
                                </Link>
                            </>
                        )}
                    </div>
            </div>
        </nav>
    );
}
