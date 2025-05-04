// src/services/api.js
import axios from 'axios';

// --- Configuration ---
// *** UPDATED with your current backend ngrok URL ***
const API_BASE_URL = '/api/';
console.log("Using API Base URL:", API_BASE_URL); // Verify this logs the correct URL

const REFRESH_TOKEN_ENDPOINT = 'token/refresh/'; // Path relative to base URL

// --- Axios Instance Creation ---
const apiClient = axios.create({
    baseURL: API_BASE_URL,
    headers: {
        'Content-Type': 'application/json',
    },
    xsrfCookieName: 'csrftoken',      // Name of the cookie Django uses
    xsrfHeaderName: 'X-CSRFToken',    // Name of the header Django expects
    withCredentials: true,          // Allow sending cookies (like CSRF) cross-origin
});

// --- Request Interceptor (Adds Auth Token) ---
apiClient.interceptors.request.use(
    (config) => {
        const token = localStorage.getItem('accessToken');
        // console.log(`Request Interceptor: Token for ${config.url}? -> ${token ? 'YES' : 'NO'}`);
        if (token) {
            config.headers['Authorization'] = `Bearer ${token}`;
        }
        return config;
    },
    (error) => {
        console.error("Request Interceptor Error:", error);
        return Promise.reject(error);
    }
);

// --- Response Interceptor (Handles Token Refresh) ---

let isRefreshing = false;
let failedQueue = [];

const processQueue = (error, token = null) => {
    failedQueue.forEach(prom => {
        if (error) { prom.reject(error); }
        else { prom.resolve(token); }
    });
    failedQueue = [];
};

apiClient.interceptors.response.use(
    (response) => response, // Pass through successful responses
    async (error) => {
        const originalRequest = error.config;
        console.log(`Response Interceptor: Error Status ${error.response?.status} on URL ${originalRequest.url}`); // Optional debug

        // Check if it's a 401 Unauthorized error AND not a retry attempt AND not the refresh endpoint itself
        if (error.response?.status === 401 && !originalRequest._retry && !originalRequest.url.endsWith(REFRESH_TOKEN_ENDPOINT)) {
            console.log("Response Interceptor: Detected 401, potentially expired token.");

            if (isRefreshing) {
                console.log("Response Interceptor: Refresh already in progress, adding request to queue.");
                return new Promise(function(resolve, reject) {
                    failedQueue.push({ resolve, reject });
                }).then(token => {
                    console.log("Response Interceptor: Retrying request from queue with new token.");
                    originalRequest.headers['Authorization'] = 'Bearer ' + token;
                    return apiClient(originalRequest);
                }).catch(err => Promise.reject(err));
            }

            originalRequest._retry = true;
            isRefreshing = true;
            const refreshToken = localStorage.getItem('refreshToken');
            console.log("Response Interceptor: Attempting token refresh.");

            if (!refreshToken) {
                console.log("Response Interceptor: No refresh token found. Forcing logout.");
                isRefreshing = false;
                localStorage.removeItem('accessToken'); localStorage.removeItem('refreshToken');
                window.location.href = '/login';
                return Promise.reject(error);
            }

            try {
                // Use basic axios post to avoid interceptor loop on refresh endpoint
                // Note: Uses the *updated* API_BASE_URL here
                const refreshResponse = await axios.post(`${API_BASE_URL}${REFRESH_TOKEN_ENDPOINT}`, {
                    refresh: refreshToken
                }, { headers: { 'Content-Type': 'application/json' } });

                const newAccessToken = refreshResponse.data.access;
                console.log("Response Interceptor: Token refresh successful.");
                localStorage.setItem('accessToken', newAccessToken);
                apiClient.defaults.headers.common['Authorization'] = `Bearer ${newAccessToken}`;
                originalRequest.headers['Authorization'] = `Bearer ${newAccessToken}`;
                processQueue(null, newAccessToken);
                console.log("Response Interceptor: Retrying original request.");
                return apiClient(originalRequest);

            } catch (refreshError) {
                console.error("Response Interceptor: Token refresh failed:", refreshError);
                processQueue(refreshError, null);
                localStorage.removeItem('accessToken'); localStorage.removeItem('refreshToken');
                window.location.href = '/login';
                return Promise.reject(refreshError);
            } finally {
                 isRefreshing = false;
            }
        }
        return Promise.reject(error);
    }
);

// --- API Functions ---
export const loginUser = (username, password) => {
    return apiClient.post('token/', { username, password });
};
export const getAssignedRoutines = () => {
    return apiClient.get('solo/assigned-routines/');
};
export const getRoutineDetails = (routineId) => {
    return apiClient.get(`solo/assigned-routines/${routineId}/`);
};
export const logSession = async (sessionData) => {
    const relativePath = 'solo/session-logs/';
    try {
        // Axios automatically handles CSRF via config now
        const response = await apiClient.post(relativePath, sessionData);
        return response.data;
    } catch (error) {
        // Keep existing detailed error handling
        console.error("Error in logSession API call:", error);
        if (error.response) {
            console.error("Error data:", error.response.data);
            console.error("Error status:", error.response.status);
            const apiError = new Error(
                error.response.data?.detail ||
                (error.response.data && typeof error.response.data === 'object' ? JSON.stringify(error.response.data) : null) || // Log full data if no detail
                `API Error: ${error.response.status}`
            );
            apiError.data = error.response.data;
            apiError.status = error.response.status;
            throw apiError;
        } else if (error.request) {
            console.error("Error request:", error.request);
            throw new Error('Network Error: Could not connect to server.');
        } else {
            console.error('Error message:', error.message);
            throw new Error('Request setup error.');
        }
    }
};

export const getLoggedSessions = async () => {
    const relativePath = 'solo/session-logs/';
    console.log(`API: Fetching logged sessions from ${relativePath}`);
    try {
        const response = await apiClient.get(relativePath);
        return response.data;
    } catch (error) {
        // Keep existing detailed error handling
        console.error("Error in getLoggedSessions API call:", error);
        if (error.response) {
            console.error("Error data:", error.response.data);
            console.error("Error status:", error.response.status);
            const apiError = new Error(
                error.response.data?.detail ||
                error.response.data?.message ||
                `API Error: ${error.response.status}`
            );
            apiError.data = error.response.data;
            apiError.status = error.response.status;
            throw apiError;
        } else if (error.request) {
            console.error("Error request:", error.request);
            throw new Error('Network Error: Could not connect to server.');
        } else {
            console.error('Error message:', error.message);
            throw new Error('Request setup error.');
        }
    }
};

export default apiClient; // Export the configured instance
