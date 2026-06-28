// Vercel Speed Insights initialization
// This script loads and initializes Speed Insights for the application
(function() {
    // Inline the minimal Speed Insights tracking code
    // This approach works without requiring a build step for the Flask app
    window.si = window.si || function () { 
        (window.siq = window.siq || []).push(arguments); 
    };
})();
