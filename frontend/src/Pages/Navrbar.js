import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import './Navbar.css';

export default function Navbar() {
  const location = useLocation();

  return (
    <nav className="navbar">
      <div className="navbar-container">
        <Link to="/" className="navbar-logo">
          <span className="logo-icon">📊</span>
          <span className="logo-text">Feedback Prioritizer</span>
        </Link>
        
        <div className="navbar-links">
          <Link 
            to="/" 
            className={`nav-link ${location.pathname === '/' ? 'active' : ''}`}
          >
            Dashboard
          </Link>
          <Link 
            to="/sources" 
            className={`nav-link ${location.pathname === '/sources' ? 'active' : ''}`}
          >
            Data Sources
          </Link>
        </div>
      </div>
    </nav>
  );
}