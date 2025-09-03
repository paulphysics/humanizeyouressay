import { initializeApp } from "https://www.gstatic.com/firebasejs/9.6.1/firebase-app.js";
import { getAuth, GoogleAuthProvider, signInWithPopup } from "https://www.gstatic.com/firebasejs/9.6.1/firebase-auth.js";

// Initialize Firebase
const firebaseApp = initializeApp(window.firebaseConfig);
const auth = getAuth(firebaseApp);
const provider = new GoogleAuthProvider();

let idToken = null;

async function handleGoogleAuth() {
    try {
        const result = await signInWithPopup(auth, provider);
        const user = result.user;
        idToken = await user.getIdToken(true);

        // Hide Google button, show extra fields section
        document.getElementById('google-signin-section').classList.add('hidden');
        document.getElementById('extra-fields-section').classList.remove('hidden');

    } catch (error) {
        const errorDisplay = document.getElementById('google-signin-error-message');
        if (errorDisplay) {
            errorDisplay.textContent = `Error: ${error.message}`;
        }
        console.error("Google Sign-In Error: ", error);
    }
}

async function completeSignup() {
    const phoneInput = document.getElementById('phone-number-input');
    const referralInput = document.getElementById('referral-code-input');
    const phoneNumber = phoneInput ? phoneInput.value.trim() : '';
    const referralCode = referralInput ? referralInput.value.trim() : '';

    if (!phoneNumber) {
        document.getElementById('signup-error-message').textContent = 'Phone number is required.';
        return;
    }

    try {
        const response = await fetch('/auth/complete-signup', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                token: idToken,
                phone_number: phoneNumber,
                referral_code: referralCode
            })
        });

        const data = await response.json();
        if (data.success) {
            window.location.href = '/';
        } else {
            document.getElementById('signup-error-message').textContent = data.message || 'Signup failed.';
        }
    } catch (error) {
        console.error('Error completing signup:', error);
        document.getElementById('signup-error-message').textContent = 'An error occurred. Please try again.';
    }
}

// Attach event listeners
document.addEventListener('DOMContentLoaded', () => {
    const googleSignInButton = document.getElementById('sign-in-with-google-btn');
    const completeSignupButton = document.getElementById('complete-signup-btn');

    if (googleSignInButton) {
        googleSignInButton.addEventListener('click', handleGoogleAuth);
    }
    if (completeSignupButton) {
        completeSignupButton.addEventListener('click', completeSignup);
    }
});
