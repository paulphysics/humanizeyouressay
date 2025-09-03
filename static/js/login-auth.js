import { initializeApp } from "https://www.gstatic.com/firebasejs/9.6.1/firebase-app.js";
import { getAuth, GoogleAuthProvider, signInWithPopup } from "https://www.gstatic.com/firebasejs/9.6.1/firebase-auth.js";

const firebaseApp = initializeApp(window.firebaseConfig);
const auth = getAuth(firebaseApp);
const provider = new GoogleAuthProvider();

const googleButton = document.getElementById('sign-in-with-google-btn');
const completeSignupSection = document.getElementById('complete-signup-section');
const completeSignupBtn = document.getElementById('complete-signup-btn');
const signupErrorDisplay = document.getElementById('signup-error-message');

let userIdToken = null; // Store token for second request

const errorMessages = {
    duplicate_phone: "Phone number already in use.",
    invalid_phone: "Invalid phone number format. Use +254XXXXXXXXX.",
    missing_phone: "Phone number is required.",
    already_completed: "Signup is already completed.",
    unauthorized: "Please sign in again.",
    default: "An error occurred. Please try again."
};

async function handleGoogleAuth() {
    try {
        const result = await signInWithPopup(auth, provider);
        const user = result.user;
        userIdToken = await user.getIdToken(true);

        const referralInput = document.getElementById('referral-code-input');
        const referralCode = referralInput ? referralInput.value : null;

        const response = await fetch('/auth', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': 'Bearer ' + userIdToken
            },
            body: JSON.stringify({ referral_code: referralCode })
        });

        const data = await response.json();

        if (response.ok) {
            if (data.needs_phone) {
                // Show complete signup UI
                completeSignupSection.classList.remove('hidden');
                googleButton.classList.add('hidden');
            } else {
                window.location.href = '/'; // No phone needed → redirect
            }
        } else {
            showGoogleError(data.error || 'Login failed.');
        }
    } catch (error) {
        showGoogleError(error.message);
    }
}

async function handleCompleteSignup() {
    const phone = document.getElementById('phone-number-input').value.trim();
    const referral = document.getElementById('referral-code-input').value.trim();

    try {
        const response = await fetch('/auth/complete-signup', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                phone_number: phone,
                referral_code: referral
            })
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
    }
}

function showGoogleError(msg) {
    const googleErrorDisplay = document.getElementById('google-signin-error-message');
    googleErrorDisplay.textContent = msg;
}

if (googleButton) {
    googleButton.addEventListener('click', handleGoogleAuth);
}
if (completeSignupBtn) {
    completeSignupBtn.addEventListener('click', handleCompleteSignup);
}
