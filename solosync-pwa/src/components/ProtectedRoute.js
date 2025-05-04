// src/components/ProtectedRoute.js
import React from 'react';
// Navigate and useLocation are not needed for this temporary version
// import { Navigate, useLocation, Outlet } from 'react-router-dom';
import { Outlet } from 'react-router-dom'; // Still need Outlet if using it
import { useAuth } from '../context/AuthContext';

function ProtectedRoute({ children }) {
    const { isAuthenticated, isLoading } = useAuth();

    // *** TEMPORARILY BYPASS ALL CHECKS AND RENDERING LOGIC ***
    console.log("ProtectedRoute TEMPORARY: Bypassing auth check, rendering children/outlet.");
    console.log(`(Current state: isLoading=${isLoading}, isAuthenticated=${isAuthenticated})`);

    // Always render the content for this test
    return children ? children : <Outlet />;
    // *** END TEMPORARY CODE ***


    /* // --- Original Logic (Commented out for test) ---
    if (isLoading) {
        console.log("ProtectedRoute: Auth state is loading...");
        return <div>Loading...</div>;
    }

    if (!isAuthenticated) {
        console.log("ProtectedRoute: Not authenticated (after load), redirecting to login.");
        return <Navigate to="/login" state={{ from: location }} replace />;
    }

    console.log("ProtectedRoute: Authenticated, rendering route.");
    return children ? children : <Outlet />;
    */ // --- End Original Logic ---
}

export default ProtectedRoute;
