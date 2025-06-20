document.addEventListener('DOMContentLoaded', function () {
    // Initialize
    let refreshTimer = null;
    let isRequestInProgress = false;
    let lastFetchTime = 0;
    const FETCH_COOLDOWN = 30000; // 30 seconds cooldown
    const REFRESH_INTERVAL = 60000; // 60 seconds refresh interval

    function initializeDashboard() {
        loadAnalytics(); // Initial load
        setupEventListeners();
        // Start auto-refresh with a longer interval
        startAutoRefresh();
    }

    function startAutoRefresh() {
        if (refreshTimer) {
            clearInterval(refreshTimer);
        }
        refreshTimer = setInterval(() => {
            if (!document.hidden) { // Only refresh if page is visible
                loadAnalytics();
            }
        }, REFRESH_INTERVAL);
    }

    function loadAnalytics() {
        // Prevent multiple simultaneous requests
        if (isRequestInProgress) {
            console.log('Analytics request already in progress');
            return;
        }

        // Add cooldown check
        const now = Date.now();
        if (now - lastFetchTime < FETCH_COOLDOWN) {
            console.log('Too soon to fetch analytics again');
            return;
        }

        isRequestInProgress = true;
        lastFetchTime = now;

        // Show loading state
        const chartsContainer = document.querySelector('.charts-container');
        const recentActivities = document.getElementById('recentActivities');

        if (chartsContainer) {
            chartsContainer.innerHTML = '<div class="loading">Loading analytics...</div>';
        }

        fetch('/api/get_analytics')
            .then(response => {
                if (!response.ok) throw new Error('Network response was not ok');
                return response.json();
            })
            .then(data => {
                if (!data) throw new Error('No data received');
                if (data.progress) {
                    renderCharts(data.progress);
                }
                if (data.recent_activities) {
                    renderRecentActivity(data.recent_activities);
                } else {
                    showNoDataMessage();
                }
            })
            .catch(error => {
                console.error('Error loading analytics:', error);
                if (chartsContainer) {
                    chartsContainer.innerHTML = `
                    <div class="error-message">
                        <p>Failed to load analytics: ${error.message}</p>
                        <button class="btn secondary-btn" onclick="loadAnalytics()">
                            Try Again
                        </button>
                    </div>
                `;
                }
            })
            .finally(() => {
                isRequestInProgress = false;
            });
    }

    // Clean up on page unload or navigation
    document.addEventListener('visibilitychange', function () {
        if (!document.hidden) {
            loadAnalytics(); // Refresh when page becomes visible
        }
    });

    // Initialize dashboard
    initializeDashboard();
    // Add this function after initializeDashboard()
    function setupEventListeners() {
        // Subject card listeners
        document.querySelectorAll('.subject-card').forEach(card => {
            card.addEventListener('click', function () {
                const subject = this.dataset.subject;
                window.location.href = `/chatbot?subject=${subject}`;
            });
        });

        // Test form submission
        const testForm = document.getElementById('testForm');
        if (testForm) {
            testForm.addEventListener('submit', function (e) {
                e.preventDefault();
                const subject = document.getElementById('testSubject').value;
                const topic = document.getElementById('testTopic').value;
                loadTestQuestions(subject, topic);
            });
        }

        // Modal close buttons
        document.querySelectorAll('.close-modal').forEach(button => {
            button.addEventListener('click', function () {
                this.closest('.modal').style.display = 'none';
            });
        });
    }
});

// Add this CSS to style.css

function showNoDataMessage() {
    const recentActivitiesElement = document.getElementById('recentActivities');
    if (recentActivitiesElement) {
        recentActivitiesElement.innerHTML = `
                <div class="no-activity-message">
                    <p>Start a learning session to see your progress!</p>
                    <button class="btn primary-btn" onclick="window.location.href='/chatbot'">
                        Start Learning
                    </button>
                </div>
            `;
    }
}

// Render charts
// Modify the renderCharts function
function renderCharts(progressData) {
    const chartsContainer = document.querySelector('.charts-container');
    if (!chartsContainer) return;

    // Show no data message if no progress data
    if (!progressData || progressData.length === 0) {
        chartsContainer.innerHTML = `
            <div class="no-data-message">
                <p>No learning data available yet.</p>
                <p>Start a learning session to see your progress!</p>
                <button class="btn primary-btn" onclick="window.location.href='/chatbot'">
                    Start Learning
                </button>
            </div>
        `;
        return;
    }

    // Create canvas elements
    chartsContainer.innerHTML = `
        <div class="chart-wrapper">
            <canvas id="performanceChart"></canvas>
        </div>
        <div class="chart-wrapper">
            <canvas id="timeChart"></canvas>
        </div>
    `;

    const performanceCtx = document.getElementById('performanceChart');
    const timeCtx = document.getElementById('timeChart');

    if (!performanceCtx || !timeCtx) {
        console.error('Chart canvas elements not found');
        return;
    }

    const topics = progressData.map(item => item.topic);
    const correctData = progressData.map(item => item.correct_count);
    const incorrectData = progressData.map(item => item.incorrect_count);

    // Performance chart
    const performanceChart = new Chart(performanceCtx, {
        type: 'bar',
        data: {
            labels: topics.map(t => t.charAt(0).toUpperCase() + t.slice(1)),
            datasets: [
                {
                    label: 'Correct',
                    data: correctData,
                    backgroundColor: '#4caf50',
                    borderColor: '#388e3c',
                    borderWidth: 1
                },
                {
                    label: 'Incorrect',
                    data: incorrectData,
                    backgroundColor: '#f44336',
                    borderColor: '#d32f2f',
                    borderWidth: 1
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: {
                    beginAtZero: true,
                    title: {
                        display: true,
                        text: 'Number of Answers'
                    }
                },
                x: {
                    title: {
                        display: true,
                        text: 'Subject'
                    }
                }
            },
            plugins: {
                legend: {
                    position: 'bottom'
                },
                title: {
                    display: true,
                    text: 'Performance by Subject'
                }
            }
        }
    });

    // Response time chart
    const timeChart = new Chart(timeCtx, {
        type: 'line',
        data: {
            labels: topics.map(t => t.charAt(0).toUpperCase() + t.slice(1)),
            datasets: [
                {
                    label: 'Average Response Time (seconds)',
                    data: progressData.map(item => item.avg_response_time),
                    backgroundColor: 'rgba(93, 64, 55, 0.2)',
                    borderColor: '#5d4037',
                    borderWidth: 2,
                    tension: 0.3
                },
                {
                    label: 'Optimal Range (5-20s)',
                    data: topics.map(() => 12.5),
                    backgroundColor: 'rgba(76, 175, 80, 0.1)',
                    borderColor: '#4caf50',
                    borderWidth: 1,
                    borderDash: [5, 5],
                    pointRadius: 0
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: {
                    beginAtZero: true,
                    title: {
                        display: true,
                        text: 'Time (seconds)'
                    }
                },
                x: {
                    title: {
                        display: true,
                        text: 'Subject'
                    }
                }
            },
            plugins: {
                legend: {
                    position: 'bottom'
                },
                title: {
                    display: true,
                    text: 'Response Time Analysis'
                }
            }
        }
    });

    // Store charts in window.charts object
    window.charts = {
        performance: performanceChart,
        time: timeChart
    };
}

// Render recent activity
function renderRecentActivity(activities) {
    const recentActivitiesElement = document.getElementById('recentActivities');
    if (!recentActivitiesElement) return;

    if (!activities || activities.length === 0) {
        showNoDataMessage();
        return;
    }

    const activityHTML = activities.map(activity => {
        const date = new Date(activity.timestamp).toLocaleString();
        const statusClass = activity.is_correct ? 'correct' : 'incorrect';
        return `
                <div class="activity-card ${statusClass}">
                    <div class="activity-header">
                        <span class="activity-type">${activity.topic.toUpperCase()}</span>
                        <span class="activity-time">${date}</span>
                    </div>
                    <div class="activity-content">
                        <p class="activity-question">${activity.question}</p>
                        <div class="activity-answers">
                            <p>Your answer: ${activity.user_answer || 'No answer provided'}</p>
                            <p>Correct answer: ${activity.correct_answer}</p>
                        </div>
                        <div class="activity-footer">
                            <span class="response-time">Response time: ${parseFloat(activity.response_time || 0).toFixed(1)}s</span>
                            <span class="result-badge ${statusClass}">
                                ${activity.is_correct ? 'Correct' : 'Incorrect'}
                            </span>
                        </div>
                    </div>
                </div>
            `;
    }).join('');

    recentActivitiesElement.innerHTML = activityHTML;
}

function loadTestQuestions(subject, topic) {
    const loadingElement = document.getElementById('loadingQuestions');
    const contentElement = document.getElementById('questionContent');

    if (loadingElement) loadingElement.style.display = 'block';
    if (contentElement) contentElement.style.display = 'none';

    fetch('/api/generate_test', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ subject, topic })
    })
        .then(response => {
            if (!response.ok) {
                throw new Error(`Network response was not ok: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            if (data.questions?.length > 0) {
                sessionStorage.setItem('testQuestions', JSON.stringify(data.questions));
                displayQuestion(0);
                if (loadingElement) loadingElement.style.display = 'none';
                if (contentElement) contentElement.style.display = 'block';
            } else {
                throw new Error('No questions received');
            }
        })
        .catch(error => {
            console.error('Error loading test questions:', error);
            if (loadingElement) {
                loadingElement.innerHTML = `
                        <p>Error loading questions. Please try again.</p>
                        <button class="btn secondary-btn" onclick="document.getElementById('testInterface').style.display = 'none'">
                            Back to Dashboard
                        </button>
                    `;
            }
        });
}

// This function appears to be referenced but not implemented in the original code
function displayQuestion(index) {
    const testQuestions = JSON.parse(sessionStorage.getItem('testQuestions') || '[]');
    const questionElement = document.getElementById('questionContent');

    if (!questionElement || !testQuestions || index >= testQuestions.length) {
        console.error('Cannot display question: missing elements or invalid index');
        return;
    }

    const question = testQuestions[index];
    // Implement question display logic here
    questionElement.innerHTML = `
            <div class="question">
                <h3>Question ${index + 1} of ${testQuestions.length}</h3>
                <p>${question.question}</p>
                <div class="options">
                    ${question.options.map((option, i) => `
                        <div class="option">
                            <input type="radio" name="answer" id="option${i}" value="${option}">
                            <label for="option${i}">${option}</label>
                        </div>
                    `).join('')}
                </div>
                <div class="test-controls">
                    ${index > 0 ? '<button class="btn secondary-btn" onclick="displayQuestion(' + (index - 1) + ')">Previous</button>' : ''}
                    ${index < testQuestions.length - 1 ?
            '<button class="btn primary-btn" onclick="displayQuestion(' + (index + 1) + ')">Next</button>' :
            '<button class="btn primary-btn" onclick="submitTest()">Submit</button>'}
                </div>
            </div>
        `;
}

function handleSummarize() {
    const text = document.getElementById('textInput')?.value;
    const difficulty = document.getElementById('difficulty')?.value || 'medium';
    const length = parseInt(document.getElementById('length')?.value || 3);
    const outputElement = document.getElementById('summaryOutput');

    if (!text || !outputElement) {
        if (outputElement) outputElement.innerText = 'Please enter some text to summarize.';
        return;
    }

    if (text.trim() === '') {
        outputElement.innerText = 'Please enter some text to summarize.';
        return;
    }

    // Show loading state
    outputElement.innerText = 'Generating summary...';
    outputElement.classList.add('loading');

    fetch('/api/summarize', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text, difficulty, length })
    })
        .then(response => {
            if (!response.ok) {
                return response.json().then(data => {
                    throw new Error(data.error || `Request failed with status ${response.status}`);
                });
            }
            return response.json();
        })
        .then(data => {
            outputElement.classList.remove('loading');
            if (data.summary) {
                outputElement.innerHTML = `<div class="summary-content">${data.summary}</div>`;
            } else {
                outputElement.innerHTML = '<div class="error-message">Error: Could not generate summary.</div>';
            }
        })
        .catch(error => {
            console.error('Error:', error);
            outputElement.classList.remove('loading');
            outputElement.innerHTML = `<div class="error-message">Error: ${error.message || 'Failed to process the text. Please try again later.'}</div>`;
        });
}

// Make sure the function is accessible globally if needed
window.handleSummarize = handleSummarize;

// Add event listener for the summarize button when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    const summarizeBtn = document.getElementById('summarizeBtn');
    if (summarizeBtn) {
        summarizeBtn.addEventListener('click', handleSummarize);
    }
});
// Expose required functions to global scope for event handlers
window.displayQuestion = displayQuestion;

// Function for test submission (referenced in displayQuestion but not implemented)
// Replace the existing submitTest function
window.submitTest = function () {
    const testQuestions = JSON.parse(sessionStorage.getItem('testQuestions') || '[]');
    const answers = [];
    const radioButtons = document.querySelectorAll('input[name="answer"]:checked');

    radioButtons.forEach((radio, index) => {
        answers.push({
            question: testQuestions[index].question,
            user_answer: radio.value,
            correct_answer: testQuestions[index].correct_answer
        });
    });

    fetch('/api/submit_test', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ answers })
    })
        .then(response => response.json())
        .then(data => {
            document.getElementById('testInterface').style.display = 'none';
            loadAnalytics(); // Refresh analytics after test submission
            alert('Test submitted successfully!');
        })
        .catch(error => {
            console.error('Error submitting test:', error);
            alert('Error submitting test. Please try again.');
        });
};

// Cleanup on page unload
window.addEventListener('beforeunload', function () {
    if (refreshTimer) {
        clearInterval(refreshTimer);
    }
});