// src/pages/LoginPage.js
import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { loginUser } from '../services/api';
import { useAuth } from '../context/AuthContext';
// Removed apiClient import as test button is gone
// import apiClient from '../services/api';

function LoginPage() {
    const [username, setUsername] = useState('');
    const [password, setPassword] = useState('');
    const [error, setError] = useState('');
    const [isLoading, setIsLoading] = useState(false);

    const { login } = useAuth();
    const navigate = useNavigate();

    const handleSubmit = async (event) => {
        event.preventDefault();
        setError('');
        setIsLoading(true);

        try {
            console.log('Attempting login via API for user:', username); // Keep this log
            const response = await loginUser(username, password);
            console.log('Login successful response data:', response.data); // Keep this log
            const { access, refresh } = response.data;
            if (access && refresh) {
                login(access, refresh);
                navigate('/'); // Navigate to routines/home page
            } else {
                setError('Login successful, but token data missing.');
                setIsLoading(false);
            }
        } catch (err) {
            // Keep the detailed error logging in catch block
            console.error("Login failed - ERROR OBJECT:", err);
            console.error("err.message:", err?.message);
            console.error("err.response:", err?.response);
            console.error("err.response.data:", err?.response?.data);

            let errorMessage = 'Login failed. Please check credentials or server status.';
            if (err.response && err.response.data) {
                errorMessage = err.response.data.detail ||
                               (Array.isArray(err.response.data.non_field_errors) ? err.response.data.non_field_errors.join(', ') : null) ||
                               'Invalid username or password.';
            } else if (err.message) { // Handle Network Error specifically
                 if (err.code === 'ERR_NETWORK') {
                    errorMessage = 'Login failed: Network Error. Cannot connect to server.';
                 } else {
                    errorMessage = `Login failed: ${err.message}`;
                 }
            }
            setError(errorMessage);
            setIsLoading(false);
        }
    };

    // --- Render the Login Form using Tailwind CSS ---
    return (
        // Full screen container
        <div className="min-h-screen flex flex-col justify-center py-12 sm:px-6 lg:px-8">
            {/* Heading Container */}
            <div className="sm:mx-auto sm:w-full sm:max-w-md">
                 <h2 className="mt-6 text-center text-3xl font-extrabold text-gray-100">
                    Sign in to SoloSync
                 </h2>
            </div>

            {/* Form Card Container */}
            <div className="mt-8 sm:mx-auto sm:w-full sm:max-w-md">
                <div className="bg-gray-800 py-8 px-4 shadow-lg sm:rounded-lg sm:px-10">
                    <form className="space-y-6" onSubmit={handleSubmit}>
                        {/* Username Field */}
                        <div>
                            <label
                                htmlFor="username"
                                className="block text-sm font-medium text-gray-400"
                            >
                                Username
                            </label>
                            <div className="mt-1">
                                <input
                                    id="username"
                                    name="username"
                                    type="text"
                                    autoComplete="username"
                                    required
                                    value={username}
                                    onChange={(e) => setUsername(e.target.value)}
                                    disabled={isLoading}
                                    className="appearance-none block w-full px-3 py-2 border border-gray-600 bg-gray-700 rounded-md shadow-sm placeholder-gray-400 text-gray-100 focus:outline-none focus:ring-cyan-500 focus:border-cyan-500 sm:text-sm disabled:bg-gray-600 disabled:cursor-not-allowed"
                                />
                            </div>
                        </div>

                        {/* Password Field */}
                        <div>
                            <label
                                htmlFor="password"
                                className="block text-sm font-medium text-gray-400"
                            >
                                Password
                            </label>
                            <div className="mt-1">
                                <input
                                    id="password"
                                    name="password"
                                    type="password"
                                    autoComplete="current-password"
                                    required
                                    value={password}
                                    onChange={(e) => setPassword(e.target.value)}
                                    disabled={isLoading}
                                    className="appearance-none block w-full px-3 py-2 border border-gray-600 bg-gray-700 rounded-md shadow-sm placeholder-gray-400 text-gray-100 focus:outline-none focus:ring-cyan-500 focus:border-cyan-500 sm:text-sm disabled:bg-gray-600 disabled:cursor-not-allowed"
                                />
                            </div>
                        </div>

                        {/* Display error message */}
                        {error && (
                             <div className="rounded-md bg-red-900 bg-opacity-50 p-4 mt-4 border border-red-500/50">
                                 <div className="flex">
                                     <div className="ml-3">
                                         <p className="text-sm font-medium text-red-400">{error}</p>
                                     </div>
                                 </div>
                             </div>
                        )}

                        {/* Submit Button */}
                        <div>
                            <button
                                type="submit"
                                disabled={isLoading}
                                className="w-full flex justify-center py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-cyan-600 hover:bg-cyan-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-gray-800 focus:ring-cyan-500 disabled:opacity-50 disabled:cursor-not-allowed"
                            >
                                {isLoading ? 'Signing in...' : 'Sign in'}
                            </button>
                        </div>
                    </form>
                </div>
            </div>

            {/* --- TEST BUTTON REMOVED --- */}

        </div> // End of main returned div
    ); // End of return statement
} // End of LoginPage function

export default LoginPage;
