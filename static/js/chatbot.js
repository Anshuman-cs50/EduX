document.addEventListener('DOMContentLoaded', function () {
    const chatbox = document.getElementById('chatbox');
    const userMessage = document.getElementById('userMessage');
    const sendBtn = document.getElementById('sendBtn');
    const topicInput = document.getElementById('topicInput');
    const gradeLevel = document.getElementById('gradeLevel');
    const setTopicBtn = document.getElementById('setTopicBtn');
    const backToDashboard = document.getElementById('backToDashboard');
    const quizContainer = document.getElementById('quizContainer');
    const quizQuestion = document.getElementById('quizQuestion');
    const quizOptions = document.getElementById('quizOptions');
    const submitQuizAnswer = document.getElementById('submitQuizAnswer');
    const progressFill = document.getElementById('progressFill');
    const difficultyLevel = document.getElementById('difficultyLevel');
    const correctAnswersDisplay = document.getElementById('correctAnswers');
    const incorrectAnswersDisplay = document.getElementById('incorrectAnswers');
    const onboardingForm = document.querySelector('.onboarding-form');

    // Progress modal elements
    const viewProgress = document.getElementById('viewProgress');
    const progressModal = document.getElementById('progressModal');
    const closeModal = document.querySelector('.close-modal');
    const reviewWeakAreas = document.getElementById('reviewWeakAreas');
    const getHint = document.getElementById('getHint');

    // State management
    let currentTopic = '';
    let currentGradeLevel = '';
    let chatStage = 'ask_topic';
    let difficulty = 1;
    let rapidQuizTimeout = null;
    let currentQuestion = null;
    let questionStartTime = null;
    let questionHistory = [];
    let correctAnswers = 0;
    let incorrectAnswers = 0;

    // Map grade levels to difficulty levels
    const difficultyMapping = {
        'elementary': 'beginner',
        'middle': 'intermediate',
        'high': 'advanced',
        'college': 'expert'
    };

    // Settings
    const RAPID_QUIZ_INTERVAL = 120000; // 2 minutes between rapid quizzes
    const RAPID_QUIZ_TIMER = 10000; // 10 seconds to answer rapid quiz
    const QUIZ_MIN_DELAY = 1500;
    let rapidQuizTimerDisplay = null;
    let rapidQuizCountdown = null;
    let rapidQuizStartTime = null;

    // Flag to prevent multiple API calls
    let isResponseProcessing = false;

    // Conversation state for advanced flow
    let conversationState = {
        stage: 'introduction',
        history: [],
        currentQuestion: '',
        thinkingTime: 0,
        startTime: null,
        difficulty: 'beginner'
    };

    // Debug function
    function debugQuiz(message) {
        console.log(`[Quiz Debug] ${new Date().toISOString()}: ${message}`);
    }

    // Update UI functions
    function updateProgressDisplay() {
        const difficultyLabels = {
            'beginner': 'Beginner',
            'intermediate': 'Intermediate',
            'advanced': 'Advanced',
            'expert': 'Expert'
        };

        difficultyLevel.textContent = `Difficulty: ${difficultyLabels[conversationState.difficulty]}`;
        const totalQuestions = correctAnswers + incorrectAnswers;
        const progressPercentage = totalQuestions > 0 ? (correctAnswers / totalQuestions) * 100 : 0;
        progressFill.style.width = `${progressPercentage}%`;
        correctAnswersDisplay.innerHTML = `<i class="fas fa-check"></i> ${correctAnswers}`;
        incorrectAnswersDisplay.innerHTML = `<i class="fas fa-times"></i> ${incorrectAnswers}`;
    }

    // Add a message to the chat
    function appendMessage(sender, message) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${sender}`;
        messageDiv.innerHTML = `<div class="message-content">${message}</div>`;
        chatbox.appendChild(messageDiv);
        chatbox.scrollTop = chatbox.scrollHeight;
    }

    // Markdown to HTML (basic)
    function markdownToHtml(text) {
        text = text.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
        text = text.replace(/\*(.*?)\*/g, '<em>$1</em>');
        text = text.replace(/^### (.*?)$/gm, '<h3>$1</h3>');
        text = text.replace(/^## (.*?)$/gm, '<h2>$1</h2>');
        text = text.replace(/^# (.*?)$/gm, '<h1>$1</h1>');
        text = text.replace(/^\- (.*?)$/gm, '<li>$1</li>');
        text = text.replace(/<\/li>\n<li>/g, '</li><li>');
        text = text.replace(/(<li>.*?<\/li>)/gs, '<ul>$1</ul>');
        text = text.replace(/\n/g, '<br>');
        return text;
    }

    // Replace loading message with final message
    function updateLoadingMessage(loadingElement, finalMessage) {
        const formattedMessage = markdownToHtml(finalMessage);
        loadingElement.innerHTML = `<div class="message-content">${formattedMessage}</div>`;
        chatbox.scrollTop = chatbox.scrollHeight;
    }

    function cleanupQuizTimers() {
        // Clear countdown interval
        if (rapidQuizCountdown) {
            clearInterval(rapidQuizCountdown);
            rapidQuizCountdown = null;
            debugQuiz('Cleared rapidQuizCountdown');
        }

        // Clear quiz timeout
        if (rapidQuizTimeout) {
            clearTimeout(rapidQuizTimeout);
            rapidQuizTimeout = null;
            debugQuiz('Cleared rapidQuizTimeout');
        }

        // Remove timer display from UI
        if (rapidQuizTimerDisplay) {
            try {
                rapidQuizTimerDisplay.remove();
            } catch (e) {
                // Handle case where element might already be removed
                console.warn('Timer display removal error:', e);
            }
            rapidQuizTimerDisplay = null;
            debugQuiz('Removed rapidQuizTimerDisplay');
        }

        // Reset quiz start time
        rapidQuizStartTime = null;
    }
    // Fetch bot response from API (advanced flow)
    function fetchBotResponse(requestData) {
        // Check if a response is already being processed
        if (isResponseProcessing) {
            console.log('Previous response still processing, ignoring this request');
            return;
        }

        // Set the flag to prevent multiple concurrent requests
        isResponseProcessing = true;

        // Create an AbortController to handle potential request cancellations
        const controller = new AbortController();
        const signal = controller.signal;

        // Set a timeout to abort the request if it takes too long
        const timeoutId = setTimeout(() => {
            controller.abort();
            console.log('Request timed out');
            isResponseProcessing = false;
        }, 30000); // 30 seconds timeout

        fetch('/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(requestData),
            signal: signal
        })
            .then(response => {
                if (!response.ok) {
                    throw new Error(`Server responded with status: ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                clearTimeout(timeoutId); // Clear the timeout since request succeeded

                // Remove loading indicator if exists
                const loadingMessages = chatbox.querySelectorAll('.loading-indicator');
                if (loadingMessages.length > 0) {
                    const lastLoadingMessage = loadingMessages[loadingMessages.length - 1];
                    lastLoadingMessage.parentElement.remove(); // Remove the entire message container
                }

                // Add new message
                appendMessage('system', markdownToHtml(data.response));

                // Update conversation state
                conversationState.stage = data.stage || conversationState.stage;

                // Update history without duplicates - use proper checking
                if (data.response) {
                    const isDuplicate = conversationState.history.some(
                        item => item === data.response
                    );
                    if (!isDuplicate) {
                        conversationState.history.push(data.response);
                    }
                }

                // Store the question if this is a question from the system
                if (data.has_followup) {
                    // Extract the question from the response (simplified approach)
                    const questionMatch = data.response.match(/([^.!?]+\?)/);
                    if (questionMatch) {
                        conversationState.currentQuestion = questionMatch[0].trim();
                    } else {
                        conversationState.currentQuestion = data.response;
                    }
                    conversationState.startTime = Date.now();
                    conversationState.stage = 'awaiting_answer';
                }

                isResponseProcessing = false;
                const quizDelay = data.quiz_delay || QUIZ_MIN_DELAY;
                if (conversationState.stage !== 'introduction') {
                    debugQuiz(`Scheduling rapid quiz after response with delay: ${quizDelay}ms`);
                    setTimeout(() => {
                        showRapidQuiz(() => {
                            userMessage.disabled = false;
                            userMessage.placeholder = "Type your response here...";
                            userMessage.focus();
                        });
                    }, quizDelay);
                } else {
                    setTimeout(() => {
                        userMessage.disabled = false;
                        userMessage.placeholder = "Type your response here...";
                        userMessage.focus();
                    }, 1000);
                }
            })
            .catch(error => {
                clearTimeout(timeoutId); // Clear the timeout

                // Check if this was an abort error (timeout or user navigation)
                if (error.name === 'AbortError') {
                    console.log('Request was aborted', error);
                } else {
                    console.error('Error:', error);
                    appendMessage('system', "Sorry, I encountered an error. Please try again.");
                }

                // Always reset processing flag and UI state
                isResponseProcessing = false;
                userMessage.disabled = false;
                sendBtn.disabled = false;
                cleanupQuizTimers();
            })
            .finally(() => {
                // Ensure the processing flag is reset even if there are unexpected issues
                isResponseProcessing = false;
            });

        // Handle page unload events to reset the flag
        const unloadHandler = () => {
            clearTimeout(timeoutId);
            controller.abort();
            isResponseProcessing = false;
            window.removeEventListener('beforeunload', unloadHandler);
        };

        window.addEventListener('beforeunload', unloadHandler);
    }
    function showRapidQuiz(callback) {
        debugQuiz('Starting rapid quiz');

        // Ensure any existing timers and UI elements are properly cleaned up
        cleanupQuizTimers();

        const urlParams = new URLSearchParams(window.location.search);
        const currentSubject = urlParams.get('subject') || 'gk';
        debugQuiz(`Current subject: ${currentSubject}`);

        // Show the quiz container and initialize UI
        quizContainer.style.display = 'block';
        quizQuestion.textContent = 'Loading quiz...';
        quizOptions.innerHTML = '';

        if (submitQuizAnswer) {
            submitQuizAnswer.style.display = 'none';
        }

        // Track the fetch request to handle potential cancellations
        const controller = new AbortController();
        const signal = controller.signal;

        // Set a timeout to prevent hanging on network issues
        const timeoutId = setTimeout(() => {
            controller.abort();
            debugQuiz('Quiz fetch request timed out');
            quizContainer.style.display = 'none';
            if (typeof callback === 'function') callback();
        }, 10000); // 10 second timeout

        fetch('/api/rapid_quiz', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                topic: currentTopic,
                subject: currentSubject,
                difficulty: conversationState.difficulty
            }),
            signal: signal
        })
            .then(response => {
                clearTimeout(timeoutId);
                if (!response.ok) {
                    throw new Error(`Server responded with status: ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                if (data.error) {
                    throw new Error(data.error);
                }

                // Clear any previous quiz timer
                cleanupQuizTimers();

                debugQuiz('Showing quiz with question: ' + data.question);
                appendMessage('system', '<div class="edu-question">Quick Quiz Time! 🎯</div>');

                // Make sure the quiz is visible and in a clean state
                quizContainer.style.display = 'block';
                quizQuestion.textContent = data.question;
                quizOptions.innerHTML = '';

                rapidQuizStartTime = Date.now();

                // Create timer display
                const timerDiv = document.createElement('div');
                timerDiv.className = 'rapid-quiz-timer';
                timerDiv.textContent = '10';
                quizQuestion.appendChild(timerDiv);
                rapidQuizTimerDisplay = timerDiv;

                let timeLeft = RAPID_QUIZ_TIMER / 1000;
                let currentQuizData = data;

                // Start countdown
                rapidQuizCountdown = setInterval(() => {
                    timeLeft--;
                    if (rapidQuizTimerDisplay) {
                        rapidQuizTimerDisplay.textContent = timeLeft;
                        if (timeLeft <= 3) {
                            rapidQuizTimerDisplay.classList.add('timer-urgent');
                        }
                    }
                    if (timeLeft <= 0) {
                        // Ensure we clear the interval before calling the timeout handler
                        clearInterval(rapidQuizCountdown);
                        rapidQuizCountdown = null;
                        handleRapidQuizTimeout(currentQuizData, callback);
                    }
                }, 1000);

                // Create options buttons
                data.options.forEach(option => {
                    const btn = document.createElement('button');
                    btn.className = 'quiz-option';
                    btn.textContent = option;
                    btn.onclick = function () {
                        // Prevent multiple clicks
                        quizOptions.querySelectorAll('button').forEach(b => b.disabled = true);

                        // Clean up timer to prevent race conditions
                        if (rapidQuizCountdown) {
                            clearInterval(rapidQuizCountdown);
                            rapidQuizCountdown = null;
                        }

                        const responseTime = (Date.now() - rapidQuizStartTime) / 1000;
                        const isCorrect = option === data.correct;

                        saveRapidQuizResult(data.question, option, data.correct, isCorrect, responseTime)
                            .catch(error => {
                                console.error('Error saving quiz result:', error);
                            });

                        if (isCorrect) {
                            correctAnswers++;
                            appendMessage('system', '<div class="quiz-result correct">Correct! Well done! ✨</div>');
                        } else {
                            incorrectAnswers++;
                            appendMessage('system', `<div class="quiz-result incorrect">The correct answer was: ${data.correct}</div>`);
                        }

                        updateProgressDisplay();
                        quizContainer.style.display = 'none';

                        // Clean up timer display
                        if (rapidQuizTimerDisplay) {
                            rapidQuizTimerDisplay.remove();
                            rapidQuizTimerDisplay = null;
                        }

                        if (typeof callback === 'function') {
                            setTimeout(callback, 1500);
                        }
                    };
                    quizOptions.appendChild(btn);
                });
            })
            .catch(error => {
                clearTimeout(timeoutId);
                console.error('Error showing rapid quiz:', error);
                quizContainer.style.display = 'none';
                cleanupQuizTimers();

                if (typeof callback === 'function') {
                    callback();
                }
            });
    }
    function handleRapidQuizTimeout(quizData, callback) {
        const responseTime = RAPID_QUIZ_TIMER / 1000;
        saveRapidQuizResult(quizData.question, "No answer", quizData.correct, false, responseTime);
        incorrectAnswers++;
        updateProgressDisplay();
        appendMessage('system', `<div class="quiz-result timeout">Time's up! The correct answer was: ${quizData.correct}</div>`);
        quizContainer.style.display = 'none';
        if (submitQuizAnswer) {
            submitQuizAnswer.style.display = 'none';
        }
        if (typeof callback === 'function') callback();
    }

    function saveRapidQuizResult(question, userAnswer, correctAnswer, isCorrect, responseTime) {
        return fetch('/api/save_rapid_quiz', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                topic: currentTopic,
                question: question,
                user_answer: userAnswer,
                correct_answer: correctAnswer,
                is_correct: isCorrect,
                response_time: responseTime,
                difficulty: conversationState.difficulty
            })
        })
            .then(response => {
                if (!response.ok) {
                    throw new Error(`Server responded with status: ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                console.log('Rapid quiz result saved:', data);
                return data;
            })
            .catch(error => {
                console.error('Error saving rapid quiz result:', error);
                // Continue on failure - non-critical operation
            });
    }

    // Handle user message submission (advanced flow)
    function handleUserMessage() {
        const message = userMessage.value.trim();
        if (!message || userMessage.disabled) return;

        // Disable input immediately
        userMessage.disabled = true;
        sendBtn.disabled = true;

        if (conversationState.startTime) {
            conversationState.thinkingTime = (Date.now() - conversationState.startTime) / 1000;
        }

        appendMessage('user', message);
        userMessage.value = '';
        appendMessage('system', '<div class="loading-indicator"><span class="dot"></span><span class="dot"></span><span class="dot"></span></div>');

        let nextStage = conversationState.stage;
        if (conversationState.stage === 'awaiting_answer') {
            nextStage = 'evaluate_response';
        }

        const requestData = {
            topic: currentTopic,
            stage: nextStage,
            message: message,
            history: conversationState.history,
            previous_question: conversationState.currentQuestion,
            response_time: conversationState.thinkingTime,
            difficulty: conversationState.difficulty
        };

        fetchBotResponse(requestData);
    }

    // Set topic and grade level to start chat
    setTopicBtn.addEventListener('click', function () {
        const topic = topicInput.value.trim();
        const selectedGrade = gradeLevel.value;

        if (topic) {
            currentTopic = topic;
            currentGradeLevel = selectedGrade;
            conversationState.difficulty = difficultyMapping[selectedGrade];

            appendMessage('user', `Topic: ${currentTopic} | Grade level: ${gradeLevel.options[gradeLevel.selectedIndex].text}`);

            // Hide the onboarding form
            onboardingForm.style.display = 'none';

            // Enable chat interface
            userMessage.disabled = true;
            sendBtn.disabled = false;

            // Reset conversation state
            conversationState.stage = 'introduction';
            conversationState.history = [];
            conversationState.currentQuestion = '';
            conversationState.thinkingTime = 0;
            conversationState.startTime = null;

            // Reset quiz stats
            correctAnswers = 0;
            incorrectAnswers = 0;

            // Update the difficulty display
            updateProgressDisplay();

            // Start chat with introduction
            fetchBotResponse({
                topic: currentTopic,
                stage: 'introduction',
                message: 'start',
                history: [],
                difficulty: conversationState.difficulty
            });
        } else {
            appendMessage('system', 'Please enter a valid topic.');
        }
    });

    userMessage.addEventListener('keypress', function (e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendBtn.click();
        }
    });

    backToDashboard && backToDashboard.addEventListener('click', function () {
        window.location.href = '/dashboard';
    });

    // Initialize progress display on load
    updateProgressDisplay();

    // Add summarize button
    const actionBar = document.createElement('div');
    actionBar.classList.add('action-bar');
    actionBar.innerHTML = `
        <button id="summarize-button" class="action-button">
            <i class="fas fa-book"></i> Summarize what we've learned
        </button>
    `;
    chatbox.parentElement.appendChild(actionBar);

    document.getElementById('summarize-button').addEventListener('click', function () {
        userMessage.disabled = true;
        appendMessage('system', '<div class="loading-indicator"><span class="dot"></span><span class="dot"></span><span class="dot"></span></div>');
        fetchBotResponse({
            topic: currentTopic,
            stage: 'summary',
            message: 'summarize',
            history: conversationState.history,
            difficulty: conversationState.difficulty
        });
    });

    // Implement progress modal functionality
    if (viewProgress) {
        viewProgress.addEventListener('click', function () {
            // Fetch progress data from API
            fetch('/api/user_progress', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    topic: currentTopic,
                    difficulty: conversationState.difficulty
                })
            })
                .then(response => {
                    if (!response.ok) {
                        throw new Error(`Server responded with status: ${response.status}`);
                    }
                    return response.json();
                })
                .then(data => {
                    // Update the modal with progress data
                    const topicMasteryDisplay = document.getElementById('topicMasteryDisplay');
                    const performanceChart = document.getElementById('performanceChart');
                    const learningRecommendations = document.getElementById('learningRecommendations');

                    // Fill in with placeholder content if real data not available
                    if (data.error || !data.mastery) {
                        topicMasteryDisplay.innerHTML = `
                        <div class="mastery-progress">
                            <div class="mastery-bar" style="width: ${Math.round((correctAnswers / (correctAnswers + incorrectAnswers || 1)) * 100)}%"></div>
                        </div>
                        <p>Current mastery: ${Math.round((correctAnswers / (correctAnswers + incorrectAnswers || 1)) * 100)}%</p>
                    `;

                        performanceChart.innerHTML = '<p>Performance data is being calculated...</p>';
                        learningRecommendations.innerHTML = '<p>Continue practicing to receive personalized recommendations.</p>';
                    } else {
                        // Display actual data
                        topicMasteryDisplay.innerHTML = `
                        <div class="mastery-progress">
                            <div class="mastery-bar" style="width: ${Math.round(data.mastery * 100)}%"></div>
                        </div>
                        <p>Current mastery: ${Math.round(data.mastery * 100)}%</p>
                    `;

                        // Display performance data
                        performanceChart.innerHTML = data.performance_html || '<p>Performance data is being calculated...</p>';

                        // Display recommendations
                        if (data.recommendations && data.recommendations.length > 0) {
                            const recList = data.recommendations.map(rec => `<li>${rec}</li>`).join('');
                            learningRecommendations.innerHTML = `<ul>${recList}</ul>`;
                        } else {
                            learningRecommendations.innerHTML = '<p>Continue practicing to receive personalized recommendations.</p>';
                        }
                    }

                    // Show the modal
                    progressModal.style.display = 'block';
                })
                .catch(error => {
                    console.error('Error fetching progress data:', error);
                    // Show modal with default content on error
                    document.getElementById('topicMasteryDisplay').innerHTML = '<p>Unable to load progress data. Please try again later.</p>';
                    document.getElementById('performanceChart').innerHTML = '';
                    document.getElementById('learningRecommendations').innerHTML = '';
                    progressModal.style.display = 'block';
                });
        });
    }

    // Close modal functionality
    if (closeModal) {
        closeModal.addEventListener('click', function () {
            progressModal.style.display = 'none';
        });
    }

    // Close modal when clicking outside
    window.addEventListener('click', function (event) {
        if (event.target === progressModal) {
            progressModal.style.display = 'none';
        }
    });

    // Review weak areas functionality
    if (reviewWeakAreas) {
        reviewWeakAreas.addEventListener('click', function () {
            userMessage.disabled = true;
            appendMessage('system', '<div class="loading-indicator"><span class="dot"></span><span class="dot"></span><span class="dot"></span></div>');
            fetchBotResponse({
                topic: currentTopic,
                stage: 'review_weak_areas',
                message: 'review weak areas',
                history: conversationState.history,
                difficulty: conversationState.difficulty
            });
        });
    }

    // Get hint functionality
    if (getHint) {
        getHint.addEventListener('click', function () {
            if (conversationState.stage === 'awaiting_answer' && conversationState.currentQuestion) {
                userMessage.disabled = true;
                appendMessage('system', '<div class="loading-indicator"><span class="dot"></span><span class="dot"></span><span class="dot"></span></div>');
                fetchBotResponse({
                    topic: currentTopic,
                    stage: 'provide_hint',
                    message: 'hint',
                    history: conversationState.history,
                    previous_question: conversationState.currentQuestion,
                    difficulty: conversationState.difficulty
                });
            } else {
                appendMessage('system', 'Hints are available when you are working on a specific question.');
            }
        });
    }

    topicInput.addEventListener('focus', function () {
        this.classList.add('active-input');
        // Show topic suggestions if you have them
        const topicSuggestions = document.getElementById('topicSuggestions');
        if (topicSuggestions) {
            topicSuggestions.style.display = 'block';
        }
    });

    topicInput.addEventListener('blur', function () {
        this.classList.remove('active-input');
        // Hide suggestions with delay to allow clicking
        setTimeout(() => {
            const topicSuggestions = document.getElementById('topicSuggestions');
            if (topicSuggestions) {
                topicSuggestions.style.display = 'none';
            }
        }, 200);
    });

    // Add visual feedback for grade/difficulty level selection
    gradeLevel.addEventListener('change', function () {
        // Remove all previous selection classes
        this.classList.remove('elementary-selected', 'middle-selected',
            'high-selected', 'college-selected');

        // Add class based on current selection
        this.classList.add(`${this.value}-selected`);

        // Update difficulty display immediately for immediate feedback
        conversationState.difficulty = difficultyMapping[this.value];
        updateDifficultyDisplay();
    });

    // Function to provide visual feedback on difficulty level
    function updateDifficultyDisplay() {
        const difficultyLabels = {
            'beginner': 'Beginner',
            'intermediate': 'Intermediate',
            'advanced': 'Advanced',
            'expert': 'Expert'
        };

        // Update display and add appropriate styling
        difficultyLevel.textContent = `Difficulty: ${difficultyLabels[conversationState.difficulty]}`;

        // Remove previous difficulty classes
        difficultyLevel.classList.remove('difficulty-beginner', 'difficulty-intermediate',
            'difficulty-advanced', 'difficulty-expert');

        // Add current difficulty class
        difficultyLevel.classList.add(`difficulty-${conversationState.difficulty}`);
    }

    // Add animation when setting topic
    setTopicBtn.addEventListener('mousedown', function () {
        this.classList.add('button-pressed');
    });

    setTopicBtn.addEventListener('mouseup', function () {
        this.classList.remove('button-pressed');
    });

    // Enhance the setTopicBtn click handler
    const originalSetTopicHandler = setTopicBtn._clickHandler;
    if (originalSetTopicHandler) {
        setTopicBtn.removeEventListener('click', originalSetTopicHandler);
    }

    // Define a single comprehensive click handler
    setTopicBtn._clickHandler = function (event) {
        const topic = topicInput.value.trim();
        const selectedGrade = gradeLevel.value;

        if (!topic) {
            // Add visual shake effect to topic input
            topicInput.classList.add('shake-error');
            setTimeout(() => {
                topicInput.classList.remove('shake-error');
            }, 500);
            appendMessage('system', 'Please enter a valid topic.');
            return;
        }

        // Add loading animation to button
        this.classList.add('loading');
        this.disabled = true;

        // Show visual transition effect
        document.querySelector('.onboarding-form').classList.add('fade-out');

        // Continue with existing functionality after visual effect
        setTimeout(() => {
            currentTopic = topic;
            currentGradeLevel = selectedGrade;
            conversationState.difficulty = difficultyMapping[selectedGrade];

            appendMessage('user', `Topic: ${currentTopic} | Grade level: ${gradeLevel.options[gradeLevel.selectedIndex].text}`);

            // Hide the onboarding form with smooth transition
            onboardingForm.style.display = 'none';

            // Enable chat interface
            userMessage.disabled = true;
            sendBtn.disabled = false;

            // Reset conversation state
            conversationState.stage = 'introduction';
            conversationState.history = [];
            conversationState.currentQuestion = '';
            conversationState.thinkingTime = 0;
            conversationState.startTime = null;

            // Reset quiz stats
            correctAnswers = 0;
            incorrectAnswers = 0;

            // Update the difficulty display
            updateProgressDisplay();

            // Remove loading state from button
            setTopicBtn.classList.remove('loading');
            setTopicBtn.disabled = false;

            // Start chat with introduction
            fetchBotResponse({
                topic: currentTopic,
                stage: 'introduction',
                message: 'start',
                history: [],
                difficulty: conversationState.difficulty
            });
        }, 600); // Match this with your CSS transition time
    };

    // Register the mousedown and mouseup animations
    setTopicBtn.addEventListener('mousedown', function () {
        this.classList.add('button-pressed');
    });

    setTopicBtn.addEventListener('mouseup', function () {
        this.classList.remove('button-pressed');
    });

    // Add the unified click event listener
    setTopicBtn.addEventListener('click', setTopicBtn._clickHandler);
});