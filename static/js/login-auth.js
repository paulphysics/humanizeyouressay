import { initializeApp } from "https://www.gstatic.com/firebasejs/9.6.1/firebase-app.js";
import { getAuth, GoogleAuthProvider, signInWithPopup } from "https://www.gstatic.com/firebasejs/9.6.1/firebase-auth.js";

// Initialize Firebase
const firebaseApp = initializeApp(window.firebaseConfig);
const auth = getAuth(firebaseApp);
const provider = new GoogleAuthProvider();

// --- Handle Google Auth Flow (First Step) ---
async function handleGoogleAuth() {
    try {
        // Show a loading state if you have one
        // signInButton.disabled = true;

        const result = await signInWithPopup(auth, provider);
        const user = result.user;
        const idToken = await user.getIdToken(true);

        const response = await fetch('/auth', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': 'Bearer ' + idToken
            }
        });

        if (response.ok) {
            const data = await response.json();
            
            // --- NEW LOGIC HERE ---
            if (data.needs_phone) {
                // User is new. Show the hidden form and hide the Google button.
                document.getElementById('google-signin-section').style.display = 'none';
                document.getElementById('complete-signup-form-section').style.display = 'block';
            } else {
                // User is existing. Redirect immediately.
                window.location.href = '/'; 
            }
        } else {
            const errorMessage = await response.text();
            document.getElementById('google-signin-error-message').textContent = `Error: ${errorMessage}`;
            console.error('Server auth error:', errorMessage);
        }
    } catch (error) {
        document.getElementById('google-signin-error-message').textContent = `Error: ${error.message}`;
        console.error("Google Sign-In Error: ", error);
    } finally {
        // Hide loading state
        // signInButton.disabled = false;
    }
}

// --- Handle Phone/Referral Form Submission (Second Step) ---
async function handleCompleteSignup(event) {
    event.preventDefault(); // Prevent the default form submission

    const completeSignupBtn = document.getElementById('complete-signup-btn');
    // Show loading state
    completeSignupBtn.disabled = true;
    completeSignupBtn.textContent = 'Submitting...';

    const phone_number = document.getElementById('phone-number-input').value.trim();
    const referral_code = document.getElementById('referral-code-input').value.trim();

    try {
        const response = await fetch('/auth/complete-signup', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                phone_number,
                referral_code: referral_code || null
            })
        });

        const data = await response.json();

        if (response.ok) {
            // Success! Redirect to the main landing page
            window.location.href = '/';
        } else {
            // Handle specific backend errors
            let errorMessage = data.error || "An unknown error occurred.";
            document.getElementById('complete-signup-error-message').textContent = `Error: ${errorMessage}`;
            console.error('Complete signup failed:', errorMessage);
        }
    } catch (error) {
        document.getElementById('complete-signup-error-message').textContent = `Error: ${error.message}`;
        console.error("Complete Signup Error: ", error);
    } finally {
        // Hide loading state
        completeSignupBtn.disabled = false;
        completeSignupBtn.textContent = 'Complete Sign Up';
    }
}

// --- Event Listeners ---
document.addEventListener('DOMContentLoaded', () => {
    // Attach listener for the Google sign-in button
    const googleSignInButton = document.getElementById('sign-in-with-google-btn');
    if (googleSignInButton) {
        googleSignInButton.addEventListener('click', handleGoogleAuth);
    }

    // Attach listener for the phone/referral form submission button
    const completeSignupBtn = document.getElementById('complete-signup-btn');
    if (completeSignupBtn) {
        completeSignupBtn.addEventListener('click', handleCompleteSignup);
    }
});
