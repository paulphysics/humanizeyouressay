// static/js/firebase-config.js
import { initializeApp } from "https://www.gstatic.com/firebasejs/11.10.0/firebase-app.js";
import { getAuth, GoogleAuthProvider } from "https://www.gstatic.com/firebasejs/11.10.0/firebase-auth.js";

// --- THIS IS THE PRODUCTION-READY HEROKU CODE ---

// Directly use the config object injected by Flask into the template
const firebaseConfig = window.firebaseConfig;

let app;
let auth;
let provider;

if (firebaseConfig && firebaseConfig.apiKey) {
    // Initialize Firebase with the config from the window object
    app = initializeApp(firebaseConfig);
    
    // Initialize Firebase Authentication
    auth = getAuth(app);
    
    // Initialize the Google Auth provider
    provider = new GoogleAuthProvider();
} else {
    console.error("Firebase configuration is missing or invalid. Please check your environment variables and template setup.");
}

// Export the auth and provider objects so they can be imported elsewhere
export { auth, provider };
