// src/components/AuthButtons.js
import React from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

export function LogoutButton({ onLogout }) { // Accept an optional callback
  const { logout } = useAuth();
  const navigate = useNavigate();

  const handleLogoutClick = () => {
    logout();
    if (onLogout) onLogout(); // Call callback if provided (e.g., to close mobile menu)
    navigate('/login'); // Redirect after logout
  };

  return (
    <button
      onClick={handleLogoutClick}
      className="text-gray-300 hover:bg-gray-700 hover:text-white px-3 py-2 rounded-md text-sm font-medium"
    >
      Logout
    </button>
  );
}

export function LoginLink() {
  return (
    <Link
      to="/login"
      className="text-gray-300 hover:bg-gray-700 hover:text-white px-3 py-2 rounded-md text-sm font-medium"
    >
      Login
    </Link>
  );
}

// You can add more auth-related buttons/links here if needed
