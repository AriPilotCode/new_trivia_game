document.addEventListener("DOMContentLoaded", () => {
    const gameSection = document.getElementById("game");
    const messageDiv = document.getElementById("message");
    let answerTimer; // Declare a timer variable

    // Fetch a question
    window.getQuestion = async () => {
        const username = getUsername();
        if (!username) {
            alert("Please login first.");
            return;
        }

        try {
            const response = await fetch(`/question?username=${encodeURIComponent(username)}`);
            if (!response.ok) {
                throw new Error('Network response was not ok.');
            }
            const data = await response.json();

            if (data.question) {
                displayQuestion(data.question);
                startAnswerTimer(); // Start the timer when a question is displayed
            } else {
                document.getElementById('question').innerHTML = data.message || "No question available.";
            }
        } catch (error) {
            console.error('Error fetching question:', error);
            document.getElementById('question').innerHTML = "Error fetching question.";
        }
    };

    // Display a question
    function displayQuestion(question) {
        const questionDiv = document.getElementById("question");
        const answersDiv = document.getElementById("answers");

        questionDiv.innerHTML = question.question;
        answersDiv.innerHTML = "";

        question.answers.forEach((answer, index) => {
            answersDiv.innerHTML += `<button class="game-button" onclick="submitAnswer(${question.key}, '${answer}')">${answer}</button><br>`;
        });
    }

    // Function to display the response from the backend
    function displayAnswer(data) {
        const messageDiv = document.getElementById('message');

        if (data.status === 'success') {
            messageDiv.innerHTML = "תשובה נכונה";
        } else if (data.status === 'error') {
            messageDiv.innerHTML = `${data.message}`;
        } else {
            messageDiv.innerHTML = "Unexpected response from the server.";
        }

        // Ensure the message is visible
        messageDiv.style.display = 'block';

        setTimeout(() => {
            location.reload();
        }, 3000);
    }

    // Function to handle submitting an answer
    window.submitAnswer = async (questionKey, answer) => {
        const username = getUsername();

        if (!username) {
            alert("Please login first.");
            return;
        }

        clearInterval(answerTimer); // Clear the timer when an answer is submitted

        try {
            const response = await fetch('/submit_answer', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username, questionKey, answer })
            });

            if (!response.ok) {
                throw new Error('Network response was not ok.');
            }

            const data = await response.json();

            // Call displayAnswer function to handle the UI update
            displayAnswer(data);

            // Disable the answer buttons after submission
            disableAnswerButtons();

        } catch (error) {
            console.error('Error submitting answer:', error);
            document.getElementById('message').style.display = 'block'; // Ensure the message is visible
            document.getElementById('message').innerHTML = "Error submitting answer.";
        }
    };

    // Start the timer for answering a question
    function startAnswerTimer() {
        const timeLimit = 30; // 30 seconds to answer
        let timeLeft = timeLimit;
        const timerDiv = document.getElementById('timer');

        timerDiv.innerHTML = `Time left: ${timeLeft} seconds`;

        // Clear any existing timer before starting a new one
        if (answerTimer) {
            clearInterval(answerTimer);
        }

        answerTimer = setInterval(() => {
            timeLeft -= 1;
            timerDiv.innerHTML = `Time left: ${timeLeft} seconds`;

            if (timeLeft <= 0) {
                clearInterval(answerTimer);
                timerDiv.innerHTML = "Time's up!";
                disableAnswerButtons();
                messageDiv.innerHTML = "Time's up! Please try the next question.";

                setTimeout(() => {
                    location.reload(); // Reload the page after 3 seconds
                }, 3000); // Delay for 3 seconds before reloading
            }
        }, 1000);
    }

    // Disable the answer buttons when time is up or after submission
    function disableAnswerButtons() {
        const answerButtons = document.querySelectorAll('#answers button');
        answerButtons.forEach(button => {
            button.disabled = true;
        });
    }

    // Get score
    window.getScore = async () => {
        const username = getUsername();
        if (!username) {
            alert("Please login first.");
            return;
        }

        try {
            const response = await fetch(`/score?username=${encodeURIComponent(username)}`);
            if (!response.ok) {
                throw new Error('Network response was not ok.');
            }
            const data = await response.json();
            const score = (data.score !== null && data.score !== undefined) ? data.score : "Score not available.";
            document.getElementById('score').innerHTML = score;

        } catch (error) {
            console.error('Error fetching score:', error);
            document.getElementById('score').innerHTML = "Error fetching score.";
        }
    };

    // Get high score
    window.getHighscore = async () => {
        try {
            const response = await fetch('/highscore');
            if (!response.ok) {
                throw new Error('Network response was not ok.');
            }
            const data = await response.json();
            document.getElementById('highscore').innerHTML = data.highscore || "Highscore not available.";
        } catch (error) {
            console.error('Error fetching highscore:', error);
            document.getElementById('highscore').innerHTML = "Error fetching highscore.";
        }
    };

    // Get logged users
    window.getLoggedUsers = async () => {
        try {
            const response = await fetch('/logged_users');
            if (!response.ok) {
                throw new Error('Network response was not ok.');
            }
            const data = await response.json();
            document.getElementById('logged_users').innerHTML = data.logged_users.join('<br>') || "No users logged in.";
        } catch (error) {
            console.error('Error fetching logged users:', error);
            document.getElementById('logged_users').innerHTML = "Error fetching logged users.";
        }
    };

    // Handle logout
    window.logout = async () => {
        try {
            await fetch('/logout', { method: 'POST' });
            window.location.href = '/'; // Navigate back to the login page
        } catch (error) {
            console.error('Error logging out:', error);
            alert("Error logging out.");
        }
    };

    // Utility function to get username from local storage
    function getUsername() {
        return localStorage.getItem('username');
    }
});
