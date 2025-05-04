// src/context/AuthContext.js
import React, { createContext, useState, useContext, useEffect, useCallback } from 'react';
// Import jwt-decode if you want to decode user info
import { jwtDecode } from 'jwt-decode'; // Use named import

// Create the context object
const AuthContext = createContext(null);

// Create the Provider component
export const AuthProvider = ({ children }) => {
    // Initialize state by trying to read tokens from localStorage on initial load
    const [accessToken, setAccessToken] = useState(localStorage.getItem('accessToken'));
    // *** REMOVED refreshToken state variable ***
    // const [refreshToken, setRefreshToken] = useState(localStorage.getItem('refreshToken'));
    const [user, setUser] = useState(null);
    const [isLoading, setIsLoading] = useState(true);

    // Effect to initialize user state on page load/refresh
    useEffect(() => {
        console.log("AuthContext: Initializing auth state...");
        const initialAccessToken = localStorage.getItem('accessToken');
        if (initialAccessToken) {
            try {
                const decodedToken = jwtDecode(initialAccessToken);
                const currentTime = Date.now() / 1000;

                if (decodedToken.exp < currentTime) {
                    console.log("AuthContext: Initial token expired.");
                    localStorage.removeItem('accessToken');
                    localStorage.removeItem('refreshToken'); // Still clear refresh token from storage
                    setAccessToken(null);
                    // setRefreshToken(null); // No state to set
                    setUser(null);
                } else {
                    console.log("AuthContext: Setting user from initial valid token:", decodedToken);
                    setUser({
                        id: decodedToken.user_id,
                        username: decodedToken.username
                    });
                    setAccessToken(initialAccessToken);
                    // setRefreshToken(localStorage.getItem('refreshToken')); // No state to set
                }
            } catch (error) {
                console.error("AuthContext: Error decoding initial token:", error);
                localStorage.removeItem('accessToken');
                localStorage.removeItem('refreshToken');
                setAccessToken(null);
                // setRefreshToken(null); // No state to set
                setUser(null);
            }
        } else {
             console.log("AuthContext: No initial token found.");
             setUser(null);
        }
        setIsLoading(false);
        console.log("AuthContext: Initialization complete.");
    }, []); // Run only once on initial mount

    // Login function
    const login = useCallback((access, refresh) => {
        console.log('AuthContext: login function CALLED');
        try {
            localStorage.setItem('accessToken', access);
            localStorage.setItem('refreshToken', refresh); // Still store refresh token
            const decodedToken = jwtDecode(access);
            console.log("AuthContext: Decoded token on login:", decodedToken);
            setAccessToken(access);
            // setRefreshToken(refresh); // No state to set
            setUser({
                id: decodedToken.user_id,
                username: decodedToken.username
            });
            console.log("AuthContext: Tokens stored, user state updated.");
        } catch (error) {
             console.error("AuthContext: Error during login:", error);
             localStorage.removeItem('accessToken');
             localStorage.removeItem('refreshToken');
             setAccessToken(null);
             // setRefreshToken(null); // No state to set
             setUser(null);
        }
    }, []);

    // Logout function
    const logout = useCallback(() => {
        console.log("AuthContext: logout function CALLED.");
        try {
            localStorage.removeItem('accessToken');
            localStorage.removeItem('refreshToken'); // Still clear refresh token from storage
            console.log("AuthContext: localStorage items removed.");
            setAccessToken(null);
            // setRefreshToken(null); // No state to set
            setUser(null);
            console.log("AuthContext: State cleared for logout.");
        } catch (error) {
            console.error("AuthContext: Error during logout:", error);
        }
    }, []);

    // Determine authentication status
    const isAuthenticated = !!accessToken && !!user;

    // Value provided by context
    const value = {
        isAuthenticated,
        accessToken,
        user,
        login,
        logout,
        isLoading,
        // refreshToken is no longer provided via context state
    };

    return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

// Custom hook (remains the same)
export const useAuth = () => {
    const context = useContext(AuthContext);
    if (context === undefined || context === null) {
      throw new Error('useAuth must be used within an AuthProvider');
    }
    return context;
};
