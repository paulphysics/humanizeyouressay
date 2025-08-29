import { initializeApp } from "https://www.gstatic.com/firebasejs/9.6.1/firebase-app.js";
import { getAuth, GoogleAuthProvider, signInWithPopup } from "https://www.gstatic.com/firebasejs/9.6.1/firebase-auth.js";

// Initialize Firebase
const firebaseApp = initializeApp(window.firebaseConfig);
const auth = getAuth(firebaseApp);
const provider = new GoogleAuthProvider();

// Function to handle the entire Google Auth flow
async function handleGoogleAuth() {
    try {
        const result = await signInWithPopup(auth, provider);
        const user = result.user;
        const idToken = await user.getIdToken(true);
        const referralCodeInput = document.getElementById('referral-code-input');
        const referralCode = referralCodeInput ? referralCodeInput.value : null;

        const response = await fetch('/auth', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': 'Bearer ' + idToken
            },
            body: JSON.stringify({
                'referral_code': referralCode
            })
        });

        if (response.ok) {
            window.location.href = '/'; // Redirect to home on success
        } else {
            const errorMessage = await response.text();
            const errorDisplay = document.getElementById('google-signin-error-message');
            if (errorDisplay) {
                errorDisplay.textContent = `Error: ${errorMessage}`;
            }
            console.error('Server auth error:', errorMessage);
        }
    } catch (error) {
        const errorDisplay = document.getElementById('google-signin-error-message');
        if (errorDisplay) {
            errorDisplay.textContent = `Error: ${error.message}`;
        }
        console.error("Google Sign-In Error: ", error);
    }
}

// Attach event listener to the button on the new auth page
document.addEventListener('DOMContentLoaded', () => {
    const googleSignInButton = document.getElementById('sign-in-with-google-btn');
    if (googleSignInButton) {
        googleSignInButton.addEventListener('click', handleGoogleAuth);
    }
});
