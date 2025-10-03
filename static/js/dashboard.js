document.addEventListener('DOMContentLoaded', function() {
    // Only add listeners if user is not logged in
    if (!window.isLoggedIn) {
        // Redirect function
        const redirectToLogin = (e) => {
            e.preventDefault();
            window.location.href = window.signInUrl;
        };

        // Add listeners to required elements
        document.querySelector('#input_text').addEventListener('focus', redirectToLogin);
        document.querySelector('#openPaymentModalBtn').addEventListener('click', redirectToLogin);

        // Optional: Add listeners to all form controls
        const formControls = document.querySelectorAll('.form-control, select, button');
        formControls.forEach(control => {
            control.addEventListener('click', redirectToLogin);
        });
    }
});
