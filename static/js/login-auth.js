import { initializeApp } from "https://www.gstatic.com/firebasejs/9.6.1/firebase-app.js";
import { getAuth, GoogleAuthProvider, signInWithPopup } from "https://www.gstatic.com/firebasejs/9.6.1/firebase-auth.js";

// Initialize Firebase
const firebaseApp = initializeApp(window.firebaseConfig);
const auth = getAuth(firebaseApp);
const provider = new GoogleAuthProvider();

// Your DOM element variables
const googleButton = document.getElementById('sign-in-with-google-btn');
const googleSpinner = document.getElementById('google-spinner');
const completeSignupSection = document.getElementById('complete-signup-form-section');
const completeSignupBtn = document.getElementById('complete-signup-btn');
const signupSpinner = document.getElementById('signup-spinner');
const signupErrorDisplay = document.getElementById('complete-signup-error-message');
const googleErrorDisplay = document.getElementById('google-signin-error-message');

let userIdToken = null;

const errorMessages = {
    duplicate_phone: "Phone number already in use.",
    invalid_phone: "Invalid phone number format. Use +254XXXXXXXXX.",
    missing_phone: "Phone number is required.",
    already_completed: "Signup already completed.",
    unauthorized: "Please sign in again.",
    default: "An error occurred. Please try again."
};

// --- Core Logic Functions ---

async function handleGoogleAuth() {
    try {
        toggleGoogleButton(true);

        const result = await signInWithPopup(auth, provider);
        const user = result.user;
        userIdToken = await user.getIdToken(true); // Store the token globally

        const response = await fetch('/auth', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': 'Bearer ' + userIdToken
            }
        });

        const data = await response.json();
        if (response.ok) {
            if (data.needs_phone) {
                // Hide Google section, show complete signup section
                document.getElementById('google-signin-section').style.display = 'none';
                document.getElementById('complete-signup-form-section').style.display = 'block';
            } else {
                // Existing user, redirect immediately
                window.location.href = '/';
            }
        } else {
            showGoogleError(data.error || 'Login failed.');
        }
    } catch (error) {
        showGoogleError(error.message);
    } finally {
        toggleGoogleButton(false);
    }
}

async function handleCompleteSignup() {
    const phone = document.getElementById('phone-number-input').value.trim();
    const referral = document.getElementById('referral-code-input').value.trim();

    try {
        toggleSignupButton(true);
        const response = await fetch('/auth/complete-signup', {
            method: 'POST',
            headers: { 
                'Content-Type': 'application/json',
                'Authorization': 'Bearer ' + userIdToken // Pass the stored token
            },
            body: JSON.stringify({ phone_number: phone, referral_code: referral })
        });

        const data = await response.json();

        if (response.ok) {
            window.location.href = '/';
        } else {
            const message = errorMessages[data.error] || errorMessages.default;
            signupErrorDisplay.textContent = message;
        }
    } catch (error) {
        signupErrorDisplay.textContent = errorMessages.default;
    } finally {
        toggleSignupButton(false);
    }
}

// --- Helper Functions for UI State ---

function toggleGoogleButton(loading) {
    if (loading) {
        googleButton.disabled = true;
        // googleSpinner.classList.remove('hidden'); // Assuming you have a spinner
    } else {
        googleButton.disabled = false;
        // googleSpinner.classList.add('hidden'); // Assuming you have a spinner
    }
}

function toggleSignupButton(loading) {
    if (loading) {
        completeSignupBtn.disabled = true;
        // signupSpinner.classList.remove('hidden'); // Assuming you have a spinner
    } else {
        completeSignupBtn.disabled = false;
        // signupSpinner.classList.add('hidden'); // Assuming you have a spinner
    }
}

function showGoogleError(msg) {
    const googleErrorDisplay = document.getElementById('google-signin-error-message');
    googleErrorDisplay.textContent = msg;
}

// --- Event Listeners ---

document.addEventListener('DOMContentLoaded', () => {
    if (googleButton) {
        googleButton.addEventListener('click', handleGoogleAuth);
    }
    if (completeSignupBtn) {
        completeSignupBtn.addEventListener('click', handleCompleteSignup);
    }
});
