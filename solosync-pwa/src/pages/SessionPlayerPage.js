// src/pages/SessionPlayerPage.js
import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { CountdownCircleTimer } from 'react-countdown-circle-timer';
import { getRoutineDetails} from '../services/api'; // Ensure logSession is imported if using alert below

// Helper function to format time
const formatTime = (remainingTime) => {
    if (typeof remainingTime !== 'number' || remainingTime < 0) return "0:00";
    const minutes = Math.floor(remainingTime / 60);
    const seconds = remainingTime % 60;
    return `${minutes}:${seconds < 10 ? '0' : ''}${seconds}`;
};

// Color constants (keep from previous step)
const activityColorHex = '#10B981';
const restColorHex = '#3B82F6';
const trailColorHex = '#374151';
const activityBgClass = 'bg-emerald-800';
const restBgClass = 'bg-blue-800';
const pausedBgClass = 'bg-gray-800';

function SessionPlayerPage() {
    const { routineId } = useParams();
    const navigate = useNavigate();

    // State (keep all existing state)
    const [routine, setRoutine] = useState(null);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState(null);
    const [currentStepIndex, setCurrentStepIndex] = useState(0);
    const [isResting, setIsResting] = useState(false);
    const [isSessionActive, setIsSessionActive] = useState(false);
    const [currentPhaseDuration, setCurrentPhaseDuration] = useState(0);
    const [timerKey, setTimerKey] = useState(0);
    const [isTtsEnabled, setIsTtsEnabled] = useState(() => { /* ... keep localStorage logic ... */
         try { const storedValue = localStorage.getItem('ttsEnabled'); return storedValue === 'true'; }
         catch (e) { console.error("Could not read TTS setting from localStorage", e); return false; }
    });

    // Effect to save TTS preference (Keep as is)
    useEffect(() => { /* ... keep localStorage logic ... */
         try { localStorage.setItem('ttsEnabled', isTtsEnabled); }
         catch (e) { console.error("Could not save TTS setting to localStorage", e); }
    }, [isTtsEnabled]);

    // Effect 1: Fetch Routine Data (Keep as is)
    useEffect(() => { /* ... keep existing fetch logic ... */
        console.log(`SessionPlayerPage: useEffect[routineId] - Fetching routine ${routineId}`);
        if (!routineId) { setError("Routine ID is missing."); setIsLoading(false); return; }
        setIsLoading(true); setError(null); setRoutine(null);
        setCurrentStepIndex(0); setCurrentPhaseDuration(0); setIsResting(false);
        setIsSessionActive(false); setTimerKey(0);
        getRoutineDetails(routineId)
            .then(response => {
                 console.log("SessionPlayerPage: Fetched routine details:", response.data);
                 if (!response.data?.routine_steps || response.data.routine_steps.length === 0) { setError("Routine has no steps defined."); setRoutine(null); }
                 else { setRoutine(response.data); setCurrentPhaseDuration(response.data.routine_steps[0]?.duration_seconds || 0); }
             })
             .catch(err => { /* ... keep existing error handling ... */
                  console.error(`SessionPlayerPage: Failed to fetch routine ${routineId}:`, err);
                  if (err.response && err.response.status === 404) { setError(`Routine with ID ${routineId} not found or not assigned to you.`); }
                  else { setError("Failed to load session details."); }
             })
             .finally(() => setIsLoading(false));
    }, [routineId]);

    // --- Get current step details ---
    const currentStep = routine?.routine_steps?.[currentStepIndex];
    const nextStep = routine?.routine_steps?.[currentStepIndex + 1];

    // --- Text-to-Speech Helper Function (Keep as is) ---
     const speak = useCallback((text) => { /* ... keep existing speak function ... */
         if (!isTtsEnabled || !text || !window.speechSynthesis) { console.log(`TTS Skip: Enabled=${isTtsEnabled}, Text=${text ? 'OK' : 'Empty'}, API=${window.speechSynthesis ? 'OK' : 'Unavailable'}`); return; }
         window.speechSynthesis.cancel(); const utterance = new SpeechSynthesisUtterance(text); utterance.lang = 'en-US'; utterance.rate = 0.9;
         console.log(`TTS Speak: "${text}"`); window.speechSynthesis.speak(utterance);
     }, [isTtsEnabled]);

    // --- Logic Callbacks (Keep moveToNextStep, transitionToRest, handleTimerComplete as is from Message #115) ---
     const moveToNextStep = useCallback(() => { /* ... keep existing ... */
         console.log("moveToNextStep called. Current index:", currentStepIndex);
         if (!routine) return; const nextIndex = currentStepIndex + 1;
         if (nextIndex >= routine.routine_steps.length) {
             console.log("Session Finished!"); setIsSessionActive(false); setIsResting(false);
             speak("Session finished.");
             // alert("Session Finished!"); // Keep alert removed
             navigate(`/log-session/${routineId}`);
         } else {
             const nextStepDetails = routine.routine_steps[nextIndex];
             console.log("Moving to next drill:", nextStepDetails?.drill_name);
             speak(`Starting drill: ${nextStepDetails?.drill_name}`); // Speak next drill when starting it
             setCurrentStepIndex(nextIndex); setIsResting(false);
             setCurrentPhaseDuration(nextStepDetails?.duration_seconds || 0); setTimerKey(prevKey => prevKey + 1);
         }
     }, [currentStepIndex, routine, navigate, routineId, speak]);

     const transitionToRest = useCallback(() => { /* ... keep existing ... */
         if (!currentStep) return; const restDuration = currentStep.rest_after_seconds;
         if (restDuration && restDuration > 0) {
              console.log(`Drill finished. Starting ${restDuration}s rest.`);
              const stepAfterRest = routine?.routine_steps?.[currentStepIndex + 1];
              speak(`Rest. Next drill: ${stepAfterRest?.drill_name || 'Final drill'}`); // Speak next drill when rest starts
              setIsResting(true); setCurrentPhaseDuration(restDuration); setTimerKey(prevKey => prevKey + 1);
         } else {
              console.log("Drill finished. No rest period, moving to next step.");
              const stepAfterRest = routine?.routine_steps?.[currentStepIndex + 1];
              speak(`Next drill: ${stepAfterRest?.drill_name || 'Session finished'}`); // Speak next drill if no rest
              moveToNextStep();
         }
     }, [currentStep, routine, currentStepIndex, moveToNextStep, speak]);

    const handleTimerComplete = () => { /* ... keep existing ... */
        console.log("Timer complete. Step index:", currentStepIndex, "Is Resting:", isResting);
        if (!currentStep) { console.error("Cannot transition: current step data is missing."); setIsSessionActive(false); return { shouldRepeat: false }; }
        if (isResting) { moveToNextStep(); } else { transitionToRest(); }
        return { shouldRepeat: false };
    };

    // --- Event Handlers for Controls (Keep as is) ---
    const handleStartSession = () => { /* ... keep existing start logic + speak call ... */
         if (!currentStep) { setError("Cannot start: Routine has no steps."); return; }
         console.log("SessionPlayerPage: handleStartSession called."); setCurrentStepIndex(0); setIsResting(false);
         setCurrentPhaseDuration(currentStep.duration_seconds || 0); setTimerKey(prevKey => prevKey + 1); setIsSessionActive(true); setError(null);
         speak(`Starting with: ${currentStep?.drill_name}`);
     };
    const handlePauseSession = () => { /* ... keep existing pause logic + cancel speech ... */
         console.log("SessionPlayerPage: handlePauseSession called."); setIsSessionActive(false); window.speechSynthesis.cancel();
    };
    const handleResumeSession = () => { /* ... keep existing resume logic ... */
         if (currentStep && currentPhaseDuration > 0) { console.log("SessionPlayerPage: handleResumeSession called."); setIsSessionActive(true); }
    };

    // --- Calculate dynamic colors and background (Keep as is) ---
    const timerRingColor = isResting ? restColorHex : activityColorHex;
    const backgroundClass = isSessionActive
        ? (isResting ? restBgClass : activityBgClass)
        : pausedBgClass;

    // --- Render Logic ---
    if (isLoading) return <div className="text-center py-10 text-gray-400">Loading session details...</div>;
    if (error) return <div className="text-center py-10 text-red-400">Error: {error}</div>;
    if (!routine) return <div className="text-center py-10 text-gray-400">Routine data not available.</div>;
     if (!currentStep && currentStepIndex >= (routine?.routine_steps?.length || 0)) {
         return <div className="text-center py-10 text-gray-100">Session Finished! Preparing log...</div>;
     }
     if (!currentStep) {
          return <div className="text-center py-10 text-red-400">Error: Cannot find current step data (Index: {currentStepIndex}).</div>;
     }

    // --- Main Player UI ---
    return (
        <div className={`min-h-screen flex flex-col items-center justify-center p-4 transition-colors duration-500 ease-in-out ${backgroundClass} text-gray-100`}>

            {/* Title and Step Info */}
            <div className="text-center mb-6"> <h2 className="text-3xl font-bold">{routine.name}</h2> <p className="text-lg text-gray-300"> Step {currentStepIndex + 1} / {routine.routine_steps.length} </p> </div>

            {/* Timer Section */}
            <div className="my-6 md:my-8">
                <CountdownCircleTimer
                    key={timerKey}
                    isPlaying={isSessionActive}
                    duration={currentPhaseDuration || 1}
                    colors={timerRingColor}
                    strokeWidth={18}
                    size={240}
                    trailColor={trailColorHex}
                    onComplete={handleTimerComplete}
                >
                    {/* Content inside the circle */}
                    {({ remainingTime }) => (
                        <div className="flex flex-col items-center">
                             {/* Line 1: The Time */}
                            <div className="text-5xl font-bold">{formatTime(remainingTime)}</div>
                            {/* --- Line 2: TEMPORARILY COMMENTED OUT for testing number visibility --- */}
                            
                            <div className={`text-lg font-semibold uppercase ${isResting ? 'text-blue-300' : 'text-emerald-300'}`}>
                                {isResting ? 'Rest' : 'Activity'}
                            </div>
                            
                            {/* --- End commented out block --- */}
                        </div>
                    )}
                </CountdownCircleTimer>
            </div>

            {/* Drill Info Section */}
            <div className="text-center mb-6 px-4 py-4 bg-black bg-opacity-20 rounded-lg max-w-lg w-full"> <h4 className="text-2xl font-semibold mb-2 text-white"> {isResting ? `Rest` : (currentStep?.drill_name || 'N/A')} </h4> {!isResting && ( <> <p className="text-gray-300 mb-1">Notes: {currentStep?.notes || 'None'}</p> <p className="text-gray-300">Target: {currentStep?.duration_seconds ? `${currentStep.duration_seconds}s` : (currentStep?.reps_target ? `${currentStep.reps_target} reps` : 'N/A')}</p> </> )} </div>

             {/* Next Up Section */}
              <div className="text-center text-gray-400 mb-8 text-lg"> {isResting ? ( nextStep ? `Next Drill: ${nextStep.drill_name}` : 'Last Rest!' ) : ( (currentStep?.rest_after_seconds && currentStep.rest_after_seconds > 0) ? `Next: Rest (${currentStep.rest_after_seconds}s)` : (nextStep ? `Next Drill: ${nextStep.drill_name}` : 'Final Drill!') ) } </div>

            {/* TTS Toggle Switch */}
            <div className="flex items-center justify-center space-x-2 mb-8 text-sm"> <label htmlFor="tts-toggle" className="font-medium text-gray-300 cursor-pointer"> Announce Next Drill </label> <input type="checkbox" id="tts-toggle" checked={isTtsEnabled} onChange={(e) => setIsTtsEnabled(e.target.checked)} className="form-checkbox h-5 w-5 text-cyan-500 bg-gray-600 border-gray-500 rounded focus:ring-cyan-500 focus:ring-offset-gray-800 cursor-pointer" /> </div>

            {/* Controls Section */}
            <div className="flex flex-wrap justify-center gap-4">
                  {!isSessionActive && timerKey === 0 && ( <button onClick={handleStartSession} className="px-6 py-3 bg-emerald-600 text-white font-semibold rounded-lg shadow-md hover:bg-emerald-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-gray-900 focus:ring-emerald-500 min-w-[120px] text-center"> Start Session </button> )}
                  {isSessionActive && ( <button onClick={handlePauseSession} className="px-6 py-3 bg-yellow-600 text-white font-semibold rounded-lg shadow-md hover:bg-yellow-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-gray-900 focus:ring-yellow-500 min-w-[120px] text-center"> Pause </button> )}
                  {!isSessionActive && timerKey > 0 && currentStepIndex < routine.routine_steps.length && ( <button onClick={handleResumeSession} className="px-6 py-3 bg-emerald-600 text-white font-semibold rounded-lg shadow-md hover:bg-emerald-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-gray-900 focus:ring-emerald-500 min-w-[120px] text-center"> Resume </button> )}
                  {isSessionActive && ( <button onClick={isResting ? moveToNextStep : transitionToRest} className="px-6 py-3 bg-gray-600 text-white font-semibold rounded-lg shadow-md hover:bg-gray-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-gray-900 focus:ring-gray-500 min-w-[120px] text-center"> Skip {isResting ? 'Rest' : 'Drill'} </button> )}
            </div>

        </div>
    );
}

export default SessionPlayerPage;