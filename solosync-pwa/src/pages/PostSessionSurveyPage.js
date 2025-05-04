// src/pages/PostSessionSurveyPage.js
import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
// Import API functions needed
import { getRoutineDetails, logSession } from '../services/api';

function PostSessionSurveyPage() {
    const { routineId } = useParams();
    const navigate = useNavigate();

    // State for fetching routine details
    const [routine, setRoutine] = useState(null);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState(null); // For general/fetch errors
    const [submitError, setSubmitError] = useState(null); // Specific errors during submission
    const [isSubmitting, setIsSubmitting] = useState(false); // Track submission state

    // State for form inputs
    const [difficulty, setDifficulty] = useState('');
    const [notes, setNotes] = useState('');
    const [metrics, setMetrics] = useState({});

    // useEffect for fetching routine details
    useEffect(() => {
        if (!routineId) {
            setError("Routine ID missing.");
            setIsLoading(false);
            return;
        }
        setIsLoading(true);
        setError(null);
        setRoutine(null); // Reset previous routine data
        setMetrics({}); // Reset metrics on new routine load
        setDifficulty(''); // Reset difficulty
        setNotes(''); // Reset notes

        getRoutineDetails(routineId)
            .then(response => {
                setRoutine(response.data);
                console.log('Survey Page - Fetched Routine:', response.data);
            })
            .catch(err => {
                console.error("Failed to fetch routine details for logging:", err);
                setError(err.message || "Could not load routine details for logging.");
            })
            .finally(() => setIsLoading(false));
    }, [routineId]); // Re-run if routineId changes

    // Handles changes in the dynamic metric input fields
    const handleMetricChange = (drillId, metricName, value) => {
        const key = `${drillId}_${metricName}`;
        // console.log(`Updating metric state: Key=${key}, Value=${value}`); // Debug log (optional)
        setMetrics(prev => ({
            ...prev,
            [key]: value,
        }));
    };

    // Handles the final submission of the log
    const handleSubmitLog = async (event) => {
        event.preventDefault();
        setSubmitError(null);
        setIsSubmitting(true);

        // 1. Format metrics data (only include metrics with values)
        const formattedMetrics = routine?.routine_steps
            ?.filter(step => step.metrics_to_collect && step.metrics_to_collect.length > 0)
            .flatMap(step =>
                step.metrics_to_collect
                    .map(metricName => {
                        const key = `${step.drill}_${metricName}`;
                        const value = metrics[key];
                        if (value !== undefined && value !== null && value !== '') {
                            return {
                                drill_id: step.drill,
                                metric_name: metricName,
                                metric_value: value // Use correct key for backend
                            };
                        }
                        return null;
                    })
                    .filter(metricObject => metricObject !== null)
            ) || [];

        // 2. Create payload
        const payload = {
            routine_id: parseInt(routineId, 10),
            physical_difficulty: parseInt(difficulty, 10),
            notes: notes,
            logged_metrics: formattedMetrics
        };
        // console.log("Final Payload Object:", payload); // Debug log (optional)

        // 3. Call API using try...catch
        try {
            const result = await logSession(payload);
            console.log("Session logged successfully:", result);
            alert("Session logged successfully!");
            navigate('/session-history'); // Navigate to history page after logging

        } catch (err) {
            console.error("Failed to submit session log:", err);
            let message = "Failed to save log. Please check inputs and try again.";
            if (err.data) {
                 if (typeof err.data === 'object' && err.data !== null) {
                    message = Object.entries(err.data)
                        .map(([field, errors]) => `${field}: ${Array.isArray(errors) ? errors.join(', ') : errors}`)
                        .join('\n');
                 } else if (err.data.message) { message = err.data.message; }
                 else if (typeof err.data === 'string') { message = err.data; }
            } else if (err.message) { message = err.message; }
            setSubmitError(message);

        } finally {
            setIsSubmitting(false);
        }
    };

    // --- Render Logic ---
    if (isLoading) return <div className="text-center py-10 text-gray-400">Loading survey...</div>;
    if (error) return <div className="text-center py-10 text-red-400">Error loading routine details: {error}</div>;
    if (!routine) return <div className="text-center py-10 text-gray-400">Routine details not found.</div>;

    // Filter steps that actually require metric collection for rendering that section
    const stepsWithMetrics = routine.routine_steps?.filter(
        step => step.metrics_to_collect && step.metrics_to_collect.length > 0
    ) || [];

    // --- Main Survey Form ---
    return (
        // Container with padding, max-width
        <div className="container mx-auto px-4 py-8 max-w-3xl">
            {/* Page Title */}
            <h2 className="text-3xl font-bold text-gray-100 mb-4">Log Session</h2>
            <h3 className="text-xl text-cyan-400 mb-6">{routine.name}</h3>

            {/* Form with spacing between sections */}
            <form onSubmit={handleSubmitLog} className="space-y-8">

                {/* Difficulty Section */}
                <div className="bg-gray-800 p-6 rounded-lg shadow-md">
                    <label htmlFor="difficulty" className="block text-lg font-medium text-gray-300 mb-2">
                        Physical Difficulty (1-5)
                    </label>
                    <input
                        type="number"
                        id="difficulty"
                        value={difficulty}
                        onChange={(e) => setDifficulty(e.target.value)}
                        min="1"
                        max="5"
                        required
                        disabled={isSubmitting}
                        className="appearance-none block w-full px-3 py-2 border border-gray-600 bg-gray-700 rounded-md shadow-sm placeholder-gray-400 text-gray-100 focus:outline-none focus:ring-cyan-500 focus:border-cyan-500 sm:text-sm disabled:bg-gray-600 disabled:cursor-not-allowed"
                    />
                </div>

                {/* Dynamic Metrics Section - Only show if there are metrics to collect */}
                {stepsWithMetrics.length > 0 && (
                    <div className="bg-gray-800 p-6 rounded-lg shadow-md space-y-6">
                        <h3 className="text-lg font-medium text-gray-300 border-b border-gray-700 pb-2 mb-4">Metrics</h3>
                        {stepsWithMetrics.map(step => (
                            // Card for each step with metrics
                            <div key={`${step.drill}_${step.order}`} className="bg-gray-700 p-4 rounded-md">
                                <h4 className="text-md font-semibold text-gray-200 mb-3">
                                    {step.order}. {step.drill_name}
                                </h4>
                                <div className="space-y-3">
                                    {step.metrics_to_collect.map(metricName => {
                                        const inputId = `${step.drill}_${metricName}`;
                                        return (
                                            <div key={inputId}>
                                                <label htmlFor={inputId} className="block text-sm font-medium text-gray-400 mb-1">
                                                    {metricName.replace(/_/g, ' ')}:
                                                </label>
                                                <input
                                                    type="text" // Use text for flexibility, consider number if appropriate
                                                    id={inputId}
                                                    value={metrics[inputId] || ''}
                                                    onChange={(e) => handleMetricChange(step.drill, metricName, e.target.value)}
                                                    disabled={isSubmitting}
                                                    className="appearance-none block w-full px-3 py-2 border border-gray-600 bg-gray-900 rounded-md shadow-sm placeholder-gray-500 text-gray-100 focus:outline-none focus:ring-cyan-500 focus:border-cyan-500 sm:text-sm disabled:bg-gray-800 disabled:cursor-not-allowed"
                                                />
                                            </div>
                                        );
                                    })}
                                </div>
                            </div>
                        ))}
                    </div>
                )}

                {/* Notes Section */}
                <div className="bg-gray-800 p-6 rounded-lg shadow-md">
                    <label htmlFor="notes" className="block text-lg font-medium text-gray-300 mb-2">
                        Notes (Optional)
                    </label>
                    <textarea
                        id="notes"
                        value={notes}
                        onChange={(e) => setNotes(e.target.value)}
                        rows="4" // Increased rows
                        disabled={isSubmitting}
                        className="appearance-none block w-full px-3 py-2 border border-gray-600 bg-gray-700 rounded-md shadow-sm placeholder-gray-400 text-gray-100 focus:outline-none focus:ring-cyan-500 focus:border-cyan-500 sm:text-sm disabled:bg-gray-600 disabled:cursor-not-allowed"
                    />
                </div>

                {/* Display Submission Errors */}
                {submitError && (
                    <div className="rounded-md bg-red-900 bg-opacity-50 p-4 border border-red-500/50">
                        <div className="flex">
                            <div className="ml-3">
                                <p className="text-sm font-medium text-red-300 whitespace-pre-wrap">{submitError}</p>
                            </div>
                        </div>
                    </div>
                )}

                {/* Submit Button */}
                <div>
                    <button
                        type="submit"
                        disabled={isSubmitting}
                        className="w-full flex justify-center py-3 px-4 border border-transparent rounded-md shadow-sm text-base font-medium text-white bg-cyan-600 hover:bg-cyan-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-gray-900 focus:ring-cyan-500 disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                        {isSubmitting ? 'Saving Log...' : 'Save Session Log'}
                    </button>
                </div>

            </form>
        </div>
    );
}

export default PostSessionSurveyPage;