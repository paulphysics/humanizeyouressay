import { auth, provider } from "./firebase-config.js";
import {
    signInWithPopup,
    sendEmailVerification,
    updateProfile
} from "https://www.gstatic.com/firebasejs/11.10.0/firebase-auth.js";

document.addEventListener('DOMContentLoaded', () => {
    const signInWithGoogleButtonEl = document.getElementById("sign-in-with-google-btn");
    const signUpWithGoogleButtonEl = document.getElementById("sign-up-with-google-btn");
    const errorMsgEmail = document.getElementById("email-error-message");
    const errorMsgPassword = document.getElementById("password-error-message");

    async function handleGoogleAuth() {
        provider.setCustomParameters({ 'prompt': 'select_account' });
        try {
            const result = await signInWithPopup(auth, provider);
            const user = result.user;
            const idToken = await user.getIdToken();

            // --- MODIFICATION START ---
            // Get the referral code from the input field
            const referralCodeInput = document.getElementById('referral-code-input');
            const referralCode = referralCodeInput ? referralCodeInput.value.trim() : null;
            
            // Pass the token and code to the login function
            loginUser(idToken, referralCode);
            // --- MODIFICATION END ---

        } catch (error) {
            console.error("Google Auth Error: ", error);
            if(errorMsgEmail) errorMsgEmail.textContent = "Google sign-in failed. Please try again.";
        }
    }

    // --- MODIFICATION START ---
    // The function now accepts a referralCode
    function loginUser(idToken, referralCode = null) {
        return fetch('/auth', {
            method: 'POST',
            headers: {
                // This header is essential for the backend to understand the request
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${idToken}`
            },
            // The body is now a JSON string containing the referral code
            body: JSON.stringify({
                referral_code: referralCode
            })
        }).then(response => {
            if (response.ok) {
                window.location.href = '/playground'; // Redirect to playground on success
            } else {
                response.text().then(text => { // Get more detailed error from server
                    console.error('Server login failed:', text);
                    if(errorMsgPassword) errorMsgPassword.textContent = "Server login failed. Please try again.";
                });
            }
        }).catch(error => {
            console.error('Fetch Error:', error);
        });
    }
    // --- MODIFICATION END ---
    
    if (signInWithGoogleButtonEl) {
        signInWithGoogleButtonEl.addEventListener("click", handleGoogleAuth);
    }
    if (signUpWithGoogleButtonEl) {
        signUpWithGoogleButtonEl.addEventListener("click", handleGoogleAuth);
    }
});
