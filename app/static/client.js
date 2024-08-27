document.addEventListener("DOMContentLoaded", () => {
    const loginForm = document.getElementById("login-form");
    const messageDiv = document.getElementById("message");

    // Handle login
    window.login = async () => {
        const username = document.getElementById("username").value;
        const password = document.getElementById("password").value;

        try {
            const response = await fetch('/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username, password })
            });

            const data = await response.json();
            if (data.status === 'success') {
                // Save the username in localStorage and redirect to the select page
                localStorage.setItem('username', username);
                window.location.href = '/select';  // Update this with the correct URL for your select page
            } else {
                messageDiv.classList.remove("hidden");
                messageDiv.innerHTML = data.message;
            }
        } catch (error) {
            console.error('Error during login:', error);
            messageDiv.classList.remove("hidden");
            messageDiv.innerHTML = "An error occurred. Please try again.";
        }
    };
});
