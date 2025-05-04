// src/App.js
import React, { useState } from 'react';
// *** REMOVED BrowserRouter as Router from import ***
import { Routes, Route, Link } from 'react-router-dom';
import './App.css';

// Import Page Components
import LoginPage from './pages/LoginPage';
import RoutineListPage from './pages/RoutineListPage';
import SessionPlayerPage from './pages/SessionPlayerPage';
import PostSessionSurveyPage from './pages/PostSessionSurveyPage';
import ProtectedRoute from './components/ProtectedRoute';
import SessionHistoryPage from './pages/SessionHistoryPage';
// Keep SessionDetailPage import commented out
// import SessionDetailPage from './pages/SessionDetailPage';

// Import useAuth hook
import { useAuth } from './context/AuthContext'; // Assuming path is correct
// Import new button components
import { LogoutButton, LoginLink } from './components/AuthButtons'; // Adjust path if needed

function App() {
  // Only need isAuthenticated from context here
  const { isAuthenticated } = useAuth();
  // Removed useNavigate and handleLogout from App component level

  // State for mobile menu visibility
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);

  // Helper function to close mobile menu on link click
  const handleMobileLinkClick = () => {
    setIsMobileMenuOpen(false);
  };

  // Define handleLogout specifically for the mobile button callback
  const handleMobileLogout = () => {
    setIsMobileMenuOpen(false);
    // The actual logout logic and navigation is handled within LogoutButton
  };


  return (
    // *** REMOVED <Router> wrapper from here ***
    // The Router is now provided by index.js
      <div className="App">

        {/* --- Styled Navigation Bar --- */}
        <nav className="bg-gray-800 shadow-md">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="flex items-center justify-between h-16">
              {/* Left side: Brand/Logo Link - points to / */}
              <div className="flex-shrink-0">
                <Link to="/" className="text-2xl font-bold text-white hover:text-gray-200">
                  SoloSync
                </Link>
              </div>

              {/* Right side: Links */}
              <div className="hidden md:block">
                <div className="ml-10 flex items-baseline space-x-4">
                  {isAuthenticated && (
                    <>
                      <Link to="/" className="text-gray-300 hover:bg-gray-700 hover:text-white px-3 py-2 rounded-md text-sm font-medium">
                        Routines
                      </Link>
                      <Link to="/session-history" className="text-gray-300 hover:bg-gray-700 hover:text-white px-3 py-2 rounded-md text-sm font-medium">
                        Session History
                      </Link>
                    </>
                  )}
                  {/* Use new components for Login/Logout */}
                  {isAuthenticated ? <LogoutButton /> : <LoginLink />}
                </div>
              </div>

              {/* Mobile Menu Button */}
              <div className="-mr-2 flex md:hidden">
                 <button onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)} type="button" className="bg-gray-800 inline-flex items-center justify-center p-2 rounded-md text-gray-400 hover:text-white hover:bg-gray-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-gray-800 focus:ring-white" aria-controls="mobile-menu" aria-expanded={isMobileMenuOpen} >
                   <span className="sr-only">Open main menu</span>
                   {isMobileMenuOpen ? ( <svg className="block h-6 w-6" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true"> <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" /> </svg> ) : ( <svg className="block h-6 w-6" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true"> <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 6h16M4 12h16M4 18h16" /> </svg> )}
                 </button>
              </div>
            </div>
          </div>

          {/* Mobile Menu Dropdown */}
          <div className={`${isMobileMenuOpen ? 'block' : 'hidden'} md:hidden`} id="mobile-menu">
            <div className="px-2 pt-2 pb-3 space-y-1 sm:px-3">
              {isAuthenticated && (
                <>
                  <Link to="/" onClick={handleMobileLinkClick} className="text-gray-300 hover:bg-gray-700 hover:text-white block px-3 py-2 rounded-md text-base font-medium"> Routines </Link>
                  <Link to="/session-history" onClick={handleMobileLinkClick} className="text-gray-300 hover:bg-gray-700 hover:text-white block px-3 py-2 rounded-md text-base font-medium"> Session History </Link>
                </>
              )}
              {/* Use new components for Login/Logout */}
              {/* Pass handleMobileLogout to LogoutButton so it closes the menu */}
              {isAuthenticated ? <LogoutButton onLogout={handleMobileLogout} /> : <Link to="/login" onClick={handleMobileLinkClick} className="text-gray-300 hover:bg-gray-700 hover:text-white block px-3 py-2 rounded-md text-base font-medium"> Login </Link>}
            </div>
          </div>
        </nav>
        {/* --- End Navigation Bar --- */}


        {/* --- Main Content Area --- */}
        <main>
          {/* Routes component MUST be a child/descendant of the Router in index.js */}
          <Routes>
             {/* Routes defined relative to the root */}
             <Route path="/login" element={<LoginPage />} />
             <Route path="/" element={<ProtectedRoute><RoutineListPage /></ProtectedRoute>} />
             <Route path="/routines" element={<ProtectedRoute><RoutineListPage /></ProtectedRoute>} />
             <Route path="/log-session/:routineId" element={<ProtectedRoute><PostSessionSurveyPage /></ProtectedRoute>} />
             <Route path="/session/:routineId" element={<ProtectedRoute><SessionPlayerPage /></ProtectedRoute>} />
             <Route path="/session-history" element={<ProtectedRoute><SessionHistoryPage /></ProtectedRoute>} />
             {/* <Route path="/session-history/:logId" element={<ProtectedRoute><SessionDetailPage /></ProtectedRoute>} /> */}
             <Route path="*" element={<div className="text-center py-10"><h2 className="text-xl text-gray-300">Page Not Found</h2></div>} />
          </Routes>
        </main>
        {/* --- End Routes --- */}

      </div>
    // *** REMOVED closing </Router> tag ***
  );
}

export default App;
