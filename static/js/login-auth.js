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
            loginUser(idToken);
        } catch (error) {
            console.error("Google Auth Error: ", error);
            if(errorMsgEmail) errorMsgEmail.textContent = "Google sign-in failed. Please try again.";
        }
    }

    function loginUser(idToken, isNewSignUp = false) {
        return fetch('/auth', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${idToken}`
            }
        }).then(response => {
            if (response.ok) {
                window.location.href = '/'; 
            } else {
                console.error('Server login failed');
                if(errorMsgPassword) errorMsgPassword.textContent = "Server login failed. Please try again.";
            }
        }).catch(error => {
            console.error('Fetch Error:', error);
        });
    }
    
    if (signInWithGoogleButtonEl) {
        signInWithGoogleButtonEl.addEventListener("click", handleGoogleAuth);
    }
    if (signUpWithGoogleButtonEl) {
        signUpWithGoogleButtonEl.addEventListener("click", handleGoogleAuth);
    }
});
