// src/pages/RoutineListPage.js
import React, { useState, useEffect} from 'react';
import { Link} from 'react-router-dom';
import { getAssignedRoutines } from '../services/api';

const formatTime = (seconds) => {
    if (typeof seconds !== 'number' || seconds < 0 || isNaN(seconds)) return "0:00";
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs < 10 ? '0' : ''}${secs}`;
};

function RoutineListPage() {
    const [routines, setRoutines] = useState([]);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState(null);
    const [expandedRoutineId, setExpandedRoutineId] = useState(null); // State for expansion

    // useEffect for fetching data (keep as is)
    useEffect(() => {
        setIsLoading(true); setError(null);
        getAssignedRoutines()
            .then(response => {
                const routineData = Array.isArray(response.data) ? response.data : response.data?.results || [];
                setRoutines(routineData);
            })
            .catch(err => { console.error("RoutineListPage: Failed to fetch routines:", err); setError(err.message || "Could not fetch assigned routines."); setRoutines([]); })
            .finally(() => setIsLoading(false));
    }, []);

    // Handler to toggle expanded routine (keep as is)
    const handleCardClick = (routineId) => {
        setExpandedRoutineId(prevId => (prevId === routineId ? null : routineId));
    };

    // --- Render logic ---
    if (isLoading) return <div className="text-center py-10 text-gray-400">Loading routines...</div>;
    if (error) return <div className="text-center py-10 text-red-400">Error: {error}</div>;

    return (
        <div className="container mx-auto px-4 py-8 max-w-4xl">
            <h2 className="text-3xl font-bold text-gray-100 mb-6">
                Your Assigned Routines
            </h2>

            {routines.length === 0 ? (
                <p className="text-gray-400 text-center mt-6">No routines assigned yet.</p>
            ) : (
                <ul className="space-y-4">
                    {routines.map((routine) => (
                        // Routine Card container
                        <li key={routine.id} className="bg-gray-800 shadow-md rounded-lg flex flex-col">
                            {/* Clickable area for expand/collapse */}
                            <div
                                className="p-5 cursor-pointer hover:bg-gray-700 rounded-t-lg flex-grow"
                                onClick={() => handleCardClick(routine.id)}
                                role="button" tabIndex={0} onKeyPress={(e) => e.key === 'Enter' && handleCardClick(routine.id)}
                            >
                                <div className="flex justify-between items-start mb-2 gap-4">
                                    <h3 className="text-xl font-semibold text-gray-100 flex-1">{routine.name}</h3>
                                    <div className="text-sm text-gray-400 text-right space-y-1 flex-shrink-0">
                                        <div>{routine.total_duration_display || 'N/A'} min</div>
                                        <div className="flex items-center justify-end space-x-1" title={`Difficulty: ${routine.difficulty_display || 'Not set'}`}>
                                            {[1, 2, 3, 4, 5].map((level) => ( <div key={level} className={`w-3 h-3 rounded-full ${ routine.difficulty_value && level <= routine.difficulty_value ? 'bg-cyan-500' : 'bg-gray-600' }`}></div> ))}
                                        </div>
                                    </div>
                                </div>
                                <p className="text-gray-400 text-sm mt-1">{routine.description || 'No description provided.'}</p>
                                <div className="flex items-center space-x-2 mt-3" title={`Difficulty: ${routine.difficulty_display || 'Not set'}`}>
                                     <span className="text-xs font-medium text-gray-400">Difficulty:</span> {/* Changed label color */}
                                     <div className="flex space-x-1">
                                         {[1, 2, 3, 4, 5].map((level) => ( <div key={level} className={`w-3 h-3 rounded-full ${ routine.difficulty_value && level <= routine.difficulty_value ? 'bg-cyan-500' : 'bg-gray-600' }`}></div> ))}
                                     </div>
                                </div>
                            </div> {/* End of clickable area */}

                            {/* --- Conditionally Rendered Drill Details --- */}
                            {expandedRoutineId === routine.id && (
                                <div className="border-t border-gray-700 bg-gray-750 px-5 py-4 rounded-b-lg">
                                    <h4 className="text-md font-semibold text-gray-300 mb-3">Drills:</h4>
                                    {routine.routine_steps && routine.routine_steps.length > 0 ? (
                                        <ul className="space-y-3"> {/* Increased spacing */}
                                            {routine.routine_steps.map((step) => (
                                                <li key={step.order} className="text-sm border-b border-gray-700 pb-2 last:border-b-0"> {/* Added border */}
                                                    <div className="flex justify-between items-center ">
                                                        {/* Drill Name and Order */}
                                                        <span className="text-gray-200 font-medium">{step.order}. {step.drill_name}</span>
                                                        {/* Duration */}
                                                        <span className="text-gray-400 flex-shrink-0 ml-4">{formatTime(step.duration_seconds)}</span>
                                                    </div>
                                                    {/* --- Conditionally Render YouTube Link --- */}
                                                    {step.youtube_link && (
                                                        <div className="mt-1"> {/* Add margin */}
                                                            <a
                                                                href={step.youtube_link}
                                                                target="_blank" // Open in new tab
                                                                rel="noopener noreferrer" // Security best practice
                                                                title={`Watch video for ${step.drill_name}`}
                                                                className="inline-flex items-center text-xs text-cyan-400 hover:text-cyan-300 hover:underline"
                                                                onClick={(e) => e.stopPropagation()} // Prevent card collapse
                                                            >
                                                                {/* Simple YouTube Icon (SVG) - Or use text "Watch Video" */}
                                                                <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 mr-1" fill="currentColor" viewBox="0 0 24 24">
                                                                     <path d="M19.615 3.184c-3.604-.246-11.631-.245-15.23 0C.78 3.418 0 4.956 0 12c0 7.044.78 8.582 4.385 8.816 3.6.245 11.626.246 15.23 0C23.22 20.582 24 19.044 24 12c0-7.044-.78-8.582-4.385-8.816zm-10.615 12.733V8.083l6.863 3.917-6.863 3.917z"/>
                                                                </svg>
                                                                Watch Video
                                                            </a>
                                                        </div>
                                                    )}
                                                    {/* --- End YouTube Link --- */}
                                                </li>
                                            ))}
                                        </ul>
                                    ) : (
                                        <p className="text-sm text-gray-400">No specific drills listed.</p>
                                    )}
                                </div>
                            )}
                            {/* --- End Drill Details --- */}

                            {/* "Start Session" Button Area */}
                            <div className="p-5 border-t border-gray-700">
                                <Link
                                    to={`/session/${routine.id}`}
                                    className="inline-block px-5 py-2 bg-cyan-600 text-white text-sm font-medium rounded-md shadow-sm hover:bg-cyan-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-gray-800 focus:ring-cyan-500"
                                    onClick={(e) => e.stopPropagation()} // Prevent card click
                                >
                                    Start Session
                                </Link>
                            </div>
                        </li>
                    ))}
                </ul>
            )}
        </div>
    );
}

export default RoutineListPage;