// src/pages/SessionPlayerPage.js
import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { CountdownCircleTimer } from 'react-countdown-circle-timer';
import { getRoutineDetails } from '../services/api';

// --- Helper: Format Time ---
const formatTime = (remainingTime) => {
    if (typeof remainingTime !== 'number' || isNaN(remainingTime) || remainingTime < 0) return "--:--";
    const minutes = Math.floor(remainingTime / 60);
    const seconds = remainingTime % 60;
    return `${minutes}:${seconds < 10 ? '0' : ''}${seconds}`;
};

// --- Helper: Web Audio Beep ---
let audioCtx = null;
function playBeep(isEnabled, frequency = 880, duration = 100, delay = 0) {
    if (!isEnabled) return;
    if (!audioCtx) { try { audioCtx = new (window.AudioContext || window.webkitAudioContext)(); } catch (e) { console.error("Web Audio API not supported"); return; } }
    if (!audioCtx) return;
    setTimeout(() => { try { const o = audioCtx.createOscillator(), g = audioCtx.createGain(); o.connect(g); g.connect(audioCtx.destination); g.gain.setValueAtTime(0, audioCtx.currentTime); g.gain.linearRampToValueAtTime(0.3, audioCtx.currentTime + 0.01); o.frequency.setValueAtTime(frequency, audioCtx.currentTime); o.type = 'sine'; o.start(audioCtx.currentTime); g.gain.setValueAtTime(0.3, audioCtx.currentTime + (duration / 1000) * 0.8); g.gain.linearRampToValueAtTime(0, audioCtx.currentTime + duration / 1000); o.stop(audioCtx.currentTime + duration / 1000); } catch (e) { console.error("Error playing beep:", e); } }, delay);
}

// --- Color Constants ---
const activityColorHex = '#10B981';
const restColorHex = '#3B82F6';
const prepColorHex = '#F59E0B';
const trailColorHex = '#374151';
const activityBgClass = 'bg-emerald-800';
const restBgClass = 'bg-blue-800';
const pausedBgClass = 'bg-gray-800';
const prepBgClass = 'bg-amber-800';

// --- Beep Frequencies ---
const warningBeepFreq = 988; // B5
const endRestBeepFreq = 1318; // E6 (higher pitch)
// const endActivityBeepFreq = 1046; // C6 - REMOVED as unused

function SessionPlayerPage() {
    const { routineId } = useParams();
    const navigate = useNavigate();

    // --- State ---
    const [routine, setRoutine] = useState(null);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState(null);
    const [currentStepIndex, setCurrentStepIndex] = useState(-1); // -1 = ready/prep phase
    const [isResting, setIsResting] = useState(false);
    const [isSessionActive, setIsSessionActive] = useState(false);
    const [currentPhaseDuration, setCurrentPhaseDuration] = useState(0);
    const [timerKey, setTimerKey] = useState(0);
    const [isTtsEnabled, setIsTtsEnabled] = useState(() => localStorage.getItem('ttsEnabled') === 'true');
    const [isBeepEnabled, setIsBeepEnabled] = useState(() => localStorage.getItem('beepEnabled') === 'true');
    const wakeLockSentinel = useRef(null);

    // --- Get current step details ---
    const currentStep = (currentStepIndex >= 0) ? routine?.routine_steps?.[currentStepIndex] : null;
    const nextStep = (currentStepIndex >= -1) ? routine?.routine_steps?.[currentStepIndex + 1] : null;
    const firstStep = routine?.routine_steps?.[0];

    // --- Wake Lock Functions ---
    const requestWakeLock = useCallback(async () => {
        if ('wakeLock' in navigator && !wakeLockSentinel.current) { try { wakeLockSentinel.current = await navigator.wakeLock.request('screen'); wakeLockSentinel.current.addEventListener('release', () => { wakeLockSentinel.current = null; }); console.log('Wake Lock requested'); } catch (err) { console.error(`Wake Lock failed: ${err.name}, ${err.message}`); wakeLockSentinel.current = null; } }
    }, []);
    const releaseWakeLock = useCallback(async () => {
        if (wakeLockSentinel.current) { try { await wakeLockSentinel.current.release(); console.log('Wake Lock released'); } catch (err) { console.error(`Wake Lock release failed: ${err.name}, ${err.message}`); } finally { wakeLockSentinel.current = null; } }
    }, []);

    // --- Text-to-Speech Function ---
    const speak = useCallback((text, delay = 0) => {
        if (!isTtsEnabled || !text || !window.speechSynthesis) return; window.speechSynthesis.cancel(); setTimeout(() => { const u = new SpeechSynthesisUtterance(text); u.lang = 'en-US'; u.rate = 0.9; console.log(`TTS Speak: "${text}"`); window.speechSynthesis.speak(u); }, delay);
    }, [isTtsEnabled]);

    // --- Effect: Fetch Routine Data ---
    useEffect(() => {
        console.log(`Fetching routine ${routineId}`);
        if (!routineId) { setError("Routine ID missing."); setIsLoading(false); return; }
        setIsLoading(true); setError(null); setRoutine(null);
        setCurrentStepIndex(-1); setCurrentPhaseDuration(0); setIsResting(false);
        setIsSessionActive(false); setTimerKey(0);
        releaseWakeLock(); // Release lock on new routine load

        getRoutineDetails(routineId)
            // *** Removed extra whitespace before .then, .catch, .finally ***
            .then(response => {
                 if (!response.data?.routine_steps || response.data.routine_steps.length === 0) { setError("Routine has no steps defined."); setRoutine(null); }
                 else { setRoutine(response.data); }
            })
            .catch(err => {
                  console.error(`Failed fetch: ${err}`);
                  if (err.response && err.response.status === 404) { setError(`Routine with ID ${routineId} not found or not assigned to you.`); }
                  else { setError("Failed to load session details."); }
            })
            .finally(() => setIsLoading(false));
    }, [routineId, releaseWakeLock]); // Added releaseWakeLock dependency

    // --- Effect: Save Toggle Preferences ---
    useEffect(() => { try { localStorage.setItem('ttsEnabled', isTtsEnabled); } catch (e) { console.error("Could not save TTS setting", e); } }, [isTtsEnabled]);
    useEffect(() => { try { localStorage.setItem('beepEnabled', isBeepEnabled); } catch (e) { console.error("Could not save Beep setting", e); } }, [isBeepEnabled]);

    // --- Logic Callbacks ---
     const moveToNextStep = useCallback(() => {
         console.log("moveToNextStep called. Current index:", currentStepIndex);
         if (!routine) return;
         const nextIndex = currentStepIndex + 1;
         if (nextIndex >= routine.routine_steps.length) {
             console.log("Session Finished!"); setIsSessionActive(false); setIsResting(false);
             speak("Session finished."); releaseWakeLock(); navigate(`/log-session/${routineId}`);
         } else {
             const nextStepDetails = routine.routine_steps[nextIndex];
             console.log("Moving to next drill:", nextStepDetails?.drill_name);
             speak(nextStepDetails?.drill_name || 'Next Drill', 300);
             setCurrentStepIndex(nextIndex); setIsResting(false);
             setCurrentPhaseDuration(nextStepDetails?.duration_seconds || 1);
             setTimerKey(prevKey => prevKey + 1);
         }
     }, [currentStepIndex, routine, navigate, routineId, speak, releaseWakeLock]);

     const transitionToRest = useCallback(() => {
         if (!currentStep || currentStepIndex < 0) return;
         const restDuration = currentStep.rest_after_seconds;
         const stepAfterRest = nextStep;
         if (restDuration && restDuration > 0) {
              console.log(`Drill finished. Starting ${restDuration}s rest.`);
              speak(`Rest. Next: ${stepAfterRest?.drill_name || 'Session finished'}`, 500);
              setIsResting(true); setCurrentPhaseDuration(restDuration); setTimerKey(prevKey => prevKey + 1);
         } else {
              console.log("Drill finished. No rest period, moving to next step.");
              speak(stepAfterRest?.drill_name || 'Session finished', 300);
              moveToNextStep();
         }
     }, [currentStep, currentStepIndex, nextStep, moveToNextStep, speak]);

    // --- Called when the countdown timer completes ---
    const handleTimerComplete = () => {
        console.log("Timer complete. Phase:", currentStepIndex === -1 ? "Prep" : (isResting ? "Rest" : "Activity"));
        const isPrepPhaseFinished = currentStepIndex === -1;

        if (isPrepPhaseFinished) {
            playBeep(isBeepEnabled, endRestBeepFreq, 150); // Signal start of first drill
            if (firstStep) {
                console.log("Starting first drill:", firstStep.drill_name);
                speak(firstStep.drill_name, 200);
                setCurrentStepIndex(0); setIsResting(false);
                setCurrentPhaseDuration(firstStep.duration_seconds || 1);
                setTimerKey(prevKey => prevKey + 1);
            } else { setIsSessionActive(false); releaseWakeLock(); }
        } else { // Normal activity or rest phase finished
            // Beeps handled in onUpdate
            if (isResting) { moveToNextStep(); } else { transitionToRest(); }
        }
        return { shouldRepeat: false };
    };

    // --- Event Handlers for Controls ---
    const handleStartSession = () => {
        if (!firstStep) { setError("Cannot start: Routine has no steps."); return; }
        console.log("Starting Prep Countdown.");
        setCurrentStepIndex(-1); setIsResting(false);
        setCurrentPhaseDuration(3);
        setTimerKey(prevKey => prevKey + 1);
        setIsSessionActive(true);
        setError(null);
        requestWakeLock();
    };
    const handlePauseSession = () => {
        console.log("Pausing session."); setIsSessionActive(false); window.speechSynthesis.cancel(); releaseWakeLock();
    };
    const handleResumeSession = () => {
         const isFinished = currentStepIndex >= (routine?.routine_steps?.length || 0);
         if (!isFinished && timerKey > 0) { console.log("Resuming session."); requestWakeLock(); setIsSessionActive(true); }
    };

    // --- Calculate dynamic colors and background ---
    const isPrepPhase = currentStepIndex === -1;
    const timerRingColor = isPrepPhase ? prepColorHex : (isResting ? restColorHex : activityColorHex);
    const backgroundClass = isSessionActive
        ? (isPrepPhase ? prepBgClass : (isResting ? restBgClass : activityBgClass))
        : pausedBgClass;

    // --- Render Logic ---
    if (isLoading) return <div className="text-center py-10 text-gray-400">Loading...</div>;
    if (error) return <div className="text-center py-10 text-red-400">Error: {error}</div>;
    if (!routine) return <div className="text-center py-10 text-gray-400">Routine data unavailable.</div>;

     const displayStep = isPrepPhase ? firstStep : currentStep;
     const sessionEffectivelyFinished = !isPrepPhase && !displayStep && currentStepIndex >= routine.routine_steps.length;
     if (sessionEffectivelyFinished) { return <div className="text-center py-10 text-gray-100">Session Finished!</div>; }
     if (!displayStep && !isPrepPhase) { return <div className="text-center py-10 text-red-400">Error: Step data missing.</div>; }

    // --- Main Player UI ---
    return (
        <div className={`min-h-screen flex flex-col items-center justify-center p-4 transition-colors duration-500 ease-in-out ${backgroundClass} text-gray-100`}>

            {/* Title and Step Info */}
            <div className="text-center mb-6"> <h2 className="text-3xl font-bold">{routine.name}</h2> <p className="text-lg text-gray-300"> {isPrepPhase ? "Get Ready!" : `Step ${currentStepIndex + 1} / ${routine.routine_steps.length}: ${isResting ? 'Rest' : 'Drill'}`} </p> </div>

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
                    onUpdate={(remainingTime) => {
                        if (!isBeepEnabled || isPrepPhase) return; // Skip beeps if disabled or during prep
                        if (!isResting && (remainingTime === 3 || remainingTime === 2 || remainingTime === 1)) { playBeep(isBeepEnabled, warningBeepFreq, 150); }
                        if (isResting && (remainingTime === 3 || remainingTime === 2)) { playBeep(isBeepEnabled, warningBeepFreq, 150); }
                        if (isResting && remainingTime === 1) { playBeep(isBeepEnabled, endRestBeepFreq, 150); }
                    }}
                >
                    {({ remainingTime }) => (
                        <div className="flex flex-col items-center justify-center h-full">
                             <div className="text-5xl font-bold">
                                 {isSessionActive ? formatTime(remainingTime) : formatTime(firstStep?.duration_seconds)}
                             </div>
                            <div className={`text-lg font-semibold uppercase ${isPrepPhase ? 'text-amber-300' : (isResting ? 'text-blue-300' : 'text-emerald-300')}`}>
                                {!isSessionActive && currentStepIndex === -1 ? 'Ready' : (isPrepPhase ? 'Starting...' : (isResting ? 'Rest' : 'Activity'))}
                            </div>
                        </div>
                    )}
                </CountdownCircleTimer>
            </div>

            {/* Drill Info Section */}
            <div className="text-center mb-6 px-4 py-4 bg-black bg-opacity-20 rounded-lg max-w-lg w-full min-h-[100px]">
                 <h4 className="text-2xl font-semibold mb-2 text-white">
                     {isPrepPhase || !isSessionActive ? "First Drill" : (isResting ? `Rest` : (displayStep?.drill_name || 'N/A'))}
                 </h4>
                 {!isResting && !isPrepPhase && displayStep && (
                     <>
                         {displayStep.notes && displayStep.notes.trim() !== '' && ( <p className="text-gray-300 mb-1">Notes: {displayStep.notes}</p> )}
                         <p className="text-gray-300">Target: {displayStep?.duration_seconds ? `${displayStep.duration_seconds}s` : (displayStep?.reps_target ? `${displayStep.reps_target} reps` : 'N/A')}</p>
                     </>
                 )}
                  {(isPrepPhase || (!isSessionActive && currentStepIndex === -1)) && (
                      <p className="text-gray-300 mt-2">{firstStep?.drill_name || 'N/A'}</p>
                  )}
            </div>

             {/* Next Up Section */}
             <div className="text-center text-gray-400 mb-8 text-lg min-h-[1.5em]">
                 {!isPrepPhase && ( isResting ? ( nextStep ? `Next Drill: ${nextStep.drill_name}` : 'Last Rest!' ) : ( (currentStep?.rest_after_seconds && currentStep.rest_after_seconds > 0) ? `Next: Rest (${currentStep.rest_after_seconds}s)` : (nextStep ? `Next Drill: ${nextStep.drill_name}` : 'Final Drill!') ) )}
             </div>

            {/* Toggle Switches */}
            <div className="flex items-center justify-center space-x-6 mb-8 text-sm">
                 {/* TTS Toggle */}
                 <div className="flex items-center space-x-2">
                    <input type="checkbox" id="tts-toggle" checked={isTtsEnabled} onChange={(e) => setIsTtsEnabled(e.target.checked)} className="form-checkbox h-5 w-5 text-cyan-500 bg-gray-600 border-gray-500 rounded focus:ring-cyan-500 focus:ring-offset-gray-800 cursor-pointer"/>
                    <label htmlFor="tts-toggle" className="font-medium text-gray-300 cursor-pointer"> Announce Drill </label>
                 </div>
                 {/* Beep Toggle */}
                 <div className="flex items-center space-x-2">
                     <input type="checkbox" id="beep-toggle" checked={isBeepEnabled} onChange={(e) => setIsBeepEnabled(e.target.checked)} className="form-checkbox h-5 w-5 text-cyan-500 bg-gray-600 border-gray-500 rounded focus:ring-cyan-500 focus:ring-offset-gray-800 cursor-pointer"/>
                     <label htmlFor="beep-toggle" className="font-medium text-gray-300 cursor-pointer"> Audio Cues </label>
                 </div>
            </div>

            {/* Controls Section */}
            <div className="flex flex-wrap justify-center gap-4">
                  {!isSessionActive && currentStepIndex === -1 && ( <button onClick={handleStartSession} className="px-6 py-3 bg-emerald-600 text-white font-semibold rounded-lg shadow-md hover:bg-emerald-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-gray-900 focus:ring-emerald-500 min-w-[120px] text-center"> Start Session </button> )}
                  {isSessionActive && ( <button onClick={handlePauseSession} className="px-6 py-3 bg-yellow-600 text-white font-semibold rounded-lg shadow-md hover:bg-yellow-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-gray-900 focus:ring-yellow-500 min-w-[120px] text-center"> Pause </button> )}
                  {!isSessionActive && currentStepIndex !== -1 && !sessionEffectivelyFinished && ( <button onClick={handleResumeSession} className="px-6 py-3 bg-emerald-600 text-white font-semibold rounded-lg shadow-md hover:bg-emerald-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-gray-900 focus:ring-emerald-500 min-w-[120px] text-center"> Resume </button> )}
                  {isSessionActive && ( <button onClick={isResting ? moveToNextStep : transitionToRest} className="px-6 py-3 bg-gray-600 text-white font-semibold rounded-lg shadow-md hover:bg-gray-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-gray-900 focus:ring-gray-500 min-w-[120px] text-center"> Skip {isResting ? 'Rest' : 'Drill'} </button> )}
            </div>

        </div>
    );
}

export default SessionPlayerPage;
