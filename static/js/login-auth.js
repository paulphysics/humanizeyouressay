import { auth, provider } from "./firebase-config.js";
import {
    // ✅ FIX: Added the missing GoogleAuthProvider import
    GoogleAuthProvider,
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
        // This provider is now correctly defined thanks to the import
        const provider = new GoogleAuthProvider();
        provider.setCustomParameters({ 'prompt': 'select_account' });
        try {
            const result = await signInWithPopup(auth, provider);
            const user = result.user;
            const idToken = await user.getIdToken();
            const referralCodeInput = document.getElementById('referral-code-input');
            const referralCode = referralCodeInput ? referralCodeInput.value.trim() : null;
            
            loginUser(idToken, referralCode);
        } catch (error) {
            console.error("Google Auth Error: ", error);
            if(errorMsgEmail) errorMsgEmail.textContent = "Google sign-in failed. Please try again.";
        }
    }

    function loginUser(idToken, referralCode = null) {
        return fetch('/auth', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${idToken}`
            },
            body: JSON.stringify({
                referral_code: referralCode
            })
        })
        .then(response => {
            if (!response.ok) {
                throw new Error('Server returned an error');
            }
            return response.json();
        })
        .then(data => {
            if (data.is_admin) {
                window.location.href = '/admin/dashboard';
            } else {
                window.location.href = '/playground';
            }
        })
        .catch(error => {
            console.error('Fetch Error:', error);
            if(errorMsgPassword) errorMsgPassword.textContent = "Server login failed. Please try again.";
        });
    }
    
    if (signInWithGoogleButtonEl) {
        signInWithGoogleButtonEl.addEventListener("click", handleGoogleAuth);
    }
    if (signUpWithGoogleButtonEl) {
        signUpWithGoogleButtonEl.addEventListener("click", handleGoogleAuth);
    }
});
