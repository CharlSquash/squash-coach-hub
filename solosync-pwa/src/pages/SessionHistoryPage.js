// src/pages/SessionHistoryPage.js
import React, { useState, useEffect, useMemo } from 'react';
import Calendar from 'react-calendar';
import 'react-calendar/dist/Calendar.css'; // Default styles
// *** Import date-fns functions ***
import {
    format,
    startOfDay,
    isSameDay,
    parseISO, // To handle ISO date strings from API
    // getWeek, // REMOVED - Not used in current logic
    startOfWeek, // Get the start of a week (e.g., Sunday/Monday)
    // endOfWeek, // REMOVED - Not used in current logic
    isSameWeek, // Check if two dates are in the same week
    // differenceInWeeks, // REMOVED - Not used in current logic
    compareDesc // For sorting dates descending
} from 'date-fns';
// Optional: Import locale if needed for week start definition
// import { enZA } from 'date-fns/locale'; // Example for South Africa (Monday start)
import { getLoggedSessions } from '../services/api';
import './CalendarOverride.css'; // Keep custom CSS import

// Define week options (which day the week starts on)
const weekStartsOn = 1; // Explicitly set to Monday for this example

function SessionHistoryPage() {
    // Existing State
    const [sessions, setSessions] = useState([]);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState(null);
    const [completedDates, setCompletedDates] = useState(new Set());
    const [selectedDate, setSelectedDate] = useState(null);

    // Gamification Stats State
    const [currentStreak, setCurrentStreak] = useState(0);
    const [sessionsThisWeek, setSessionsThisWeek] = useState(0);

    // Fetch data on component mount
    useEffect(() => {
        setIsLoading(true);
        setError(null);
        console.log("SessionHistoryPage: Fetching logged sessions...");

        getLoggedSessions()
            .then(response => {
                console.log("SessionHistoryPage: API response received:", response);
                const sessionData = Array.isArray(response) ? response : response?.results || [];
                setSessions(sessionData); // Keep original sessions

                // --- Process data for Calendar and Gamification ---
                const datesWithSessions = new Set();
                const sortedSessions = sessionData
                    .map(s => ({ ...s, completed_at_date: s.completed_at ? parseISO(s.completed_at) : null }))
                    .filter(s => s.completed_at_date)
                    .sort((a, b) => compareDesc(a.completed_at_date, b.completed_at_date));

                sortedSessions.forEach(session => {
                    const sessionDateStr = format(startOfDay(session.completed_at_date), 'yyyy-MM-dd');
                    datesWithSessions.add(sessionDateStr);
                });
                setCompletedDates(datesWithSessions);

                // --- Calculate Gamification Stats ---
                if (sortedSessions.length > 0) {
                    const today = new Date();
                    const currentWeekSessions = sortedSessions.filter(s =>
                        isSameWeek(today, s.completed_at_date, { weekStartsOn })
                    ).length;
                    setSessionsThisWeek(currentWeekSessions);

                    let streak = 0;
                    let expectedWeekStartDate = startOfWeek(sortedSessions[0].completed_at_date, { weekStartsOn });

                    const uniqueWeeks = [...new Set(
                        sortedSessions.map(s => startOfWeek(s.completed_at_date, { weekStartsOn }).toISOString())
                    )].sort().reverse();

                    for (const weekStartDateStr of uniqueWeeks) {
                        const weekStartDate = parseISO(weekStartDateStr);
                        if (isSameDay(weekStartDate, expectedWeekStartDate)) {
                            streak++;
                            expectedWeekStartDate = new Date(expectedWeekStartDate.setDate(expectedWeekStartDate.getDate() - 7));
                        } else {
                            break;
                        }
                    }
                    setCurrentStreak(streak);
                    console.log(`Gamification: Streak=${streak}, ThisWeek=${currentWeekSessions}`);

                } else {
                    setSessionsThisWeek(0);
                    setCurrentStreak(0);
                }
                setError(null);
            })
            .catch(err => {
                 console.error("SessionHistoryPage: Failed to fetch sessions:", err);
                 setError(err.message || "Could not fetch session history."); setSessions([]);
                 setCompletedDates(new Set()); setSessionsThisWeek(0); setCurrentStreak(0);
            })
            .finally(() => setIsLoading(false));
    }, []); // Run only on mount

    // Filter sessions for the selected date (keep as is)
    const sessionsForSelectedDay = useMemo(() => {
        if (!selectedDate) return [];
        // Ensure comparison uses parsed dates
        return sessions.filter(session =>
            session.completed_at && isSameDay(startOfDay(parseISO(session.completed_at)), selectedDate)
        );
     }, [selectedDate, sessions]);

    // Function to add star marker (keep as is)
    const tileContent = ({ date, view }) => {
         if (view === 'month') { const dateStr = format(startOfDay(date), 'yyyy-MM-dd'); if (completedDates.has(dateStr)) { return <span className="absolute top-1 right-1 text-yellow-400 text-xs">⭐</span>; } } return null;
     };

    // Handle Day Click (keep as is)
    const handleDayClick = (date) => {
         const clickedDate = startOfDay(date); const clickedDateStr = format(clickedDate, 'yyyy-MM-dd');
         if (completedDates.has(clickedDateStr)) { if (selectedDate && isSameDay(selectedDate, clickedDate)) { setSelectedDate(null); } else { setSelectedDate(clickedDate); } }
         else { setSelectedDate(null); }
     };

    // --- Render Logic ---
    if (isLoading) return <div className="text-center py-10 text-gray-400">Loading session history...</div>;
    if (error) return <div className="text-center py-10 text-red-400">Error loading session history: {error}</div>;

    return (
        <div className="container mx-auto px-4 py-8 max-w-4xl">
            <h2 className="text-3xl font-bold text-gray-100 mb-6">Session History</h2>

            {/* Gamification Stats Display */}
            <div className="flex justify-around items-center bg-gray-800 p-4 rounded-lg shadow-md mb-6 text-center">
                <div>
                    <div className="text-3xl font-bold text-cyan-400">{sessionsThisWeek}</div>
                    <div className="text-sm text-gray-400">Sessions This Week</div>
                </div>
                <div>
                    <div className="text-3xl font-bold text-orange-400">🔥 {currentStreak}</div>
                    <div className="text-sm text-gray-400">Weekly Streak</div>
                </div>
            </div>

            {/* Calendar Component */}
            <div className="calendar-container bg-gray-800 p-4 rounded-lg shadow-md">
                <Calendar
                    onChange={handleDayClick}
                    value={selectedDate}
                    tileContent={tileContent}
                    calendarType="gregory"
                    locale="en-ZA" // Optional: use locale for formatting/week start
                />
            </div>

            {/* Details Section */}
            {selectedDate && (
                <div className="mt-8">
                    <h3 className="text-2xl font-semibold text-gray-100 mb-4">
                        Logs for {format(selectedDate, 'MMMM d, yyyy')}
                    </h3>
                    {sessionsForSelectedDay.length === 0 ? (
                        <p className="text-gray-400">No sessions found for this date.</p>
                    ) : (
                        <ul className="space-y-4">
                            {sessionsForSelectedDay.map(session => (
                                <li key={session.id} className="bg-gray-800 shadow-md rounded-lg p-5">
                                     <div className="flex justify-between items-center mb-2"> <span className="text-lg font-semibold text-gray-200">{session.routine_name || 'N/A'}</span> <span className="text-sm text-gray-400">{parseISO(session.completed_at).toLocaleTimeString('en-ZA', { hour: '2-digit', minute: '2-digit' })}</span> </div>
                                     <p className="text-sm text-gray-400 mb-1">Player: {session.player_username || 'N/A'}</p>
                                     <p className="text-sm text-gray-400 mb-3">Difficulty: {session.physical_difficulty || 'N/A'}</p>
                                     {session.notes && <p className="text-sm text-gray-300 bg-gray-700 p-2 rounded mb-3">Notes: {session.notes}</p>}
                                     {session.logged_metrics && session.logged_metrics.length > 0 && ( <div> <h5 className="text-sm font-medium text-gray-400 mb-1">Metrics Recorded:</h5> <ul className="list-disc list-inside pl-2 space-y-1"> {session.logged_metrics.map((metric, index) => ( <li key={index} className="text-sm text-gray-300"> {metric.drill_name || 'Unknown Drill'} - {metric.metric_name}: {metric.metric_value} </li> ))} </ul> </div> )}
                                </li>
                            ))}
                        </ul>
                    )}
                </div>
            )}
        </div>
    );
}

export default SessionHistoryPage;
