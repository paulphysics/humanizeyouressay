import { initializeApp } from "https://www.gstatic.com/firebasejs/9.6.1/firebase-app.js";
import { getAuth, GoogleAuthProvider, signInWithPopup } from "https://www.gstatic.com/firebasejs/9.6.1/firebase-auth.js";

const firebaseApp = initializeApp(window.firebaseConfig);
const auth = getAuth(firebaseApp);
const provider = new GoogleAuthProvider();

let firebaseIdToken = null;

// Google Sign-In
async function handleGoogleAuth() {
    try {
        const result = await signInWithPopup(auth, provider);
        firebaseIdToken = await result.user.getIdToken(true);

        document.getElementById('google-signin-section').classList.add('hidden');
        document.getElementById('extra-fields-section').classList.remove('hidden');

    } catch (error) {
        const errorDisplay = document.getElementById('google-signin-error-message');
        if (errorDisplay) errorDisplay.textContent = `Error: ${error.message}`;
        console.error("Google Sign-In Error:", error);
    }
}

// Validate Kenyan phone number format
function isValidKenyaPhone(phone) {
    const regex = /^\+2547\d{8}$/;
    return regex.test(phone);
}

// Complete Signup
async function handleCompleteSignup() {
    const phoneNumber = document.getElementById('phone-number-input').value.trim();
    const referralCode = document.getElementById('referral-code-input').value.trim();
    const errorDisplay = document.getElementById('signup-error-message');
    const button = document.getElementById('complete-signup-btn');
    const spinner = document.getElementById('signup-btn-spinner');
    const buttonText = document.getElementById('signup-btn-text');

    errorDisplay.textContent = '';

    if (!phoneNumber) {
        errorDisplay.textContent = "Phone number is required.";
        return;
    }
    if (!isValidKenyaPhone(phoneNumber)) {
        errorDisplay.textContent = "Enter a valid Kenyan number (e.g., +254700123456).";
        return;
    }

    // Disable button and show spinner
    button.disabled = true;
    spinner.classList.remove('hidden');
    buttonText.textContent = "Processing...";

    try {
        const response = await fetch('/auth/complete-signup', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': 'Bearer ' + firebaseIdToken
            },
            body: JSON.stringify({
                phone_number: phoneNumber,
                referral_code: referralCode || null
            })
        });

        const data = await response.json();

        if (response.ok) {
            window.location.href = '/';
        } else {
            errorDisplay.textContent = data.message || "Signup failed.";
            button.disabled = false;
            spinner.classList.add('hidden');
            buttonText.textContent = "Complete Signup";
        }
    } catch (error) {
        errorDisplay.textContent = `Error: ${error.message}`;
        button.disabled = false;
        spinner.classList.add('hidden');
        buttonText.textContent = "Complete Signup";
        console.error("Complete Signup Error:", error);
    }
}

document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('sign-in-with-google-btn')?.addEventListener('click', handleGoogleAuth);
    document.getElementById('complete-signup-btn')?.addEventListener('click', handleCompleteSignup);
});
