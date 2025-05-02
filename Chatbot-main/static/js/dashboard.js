document.addEventListener('DOMContentLoaded', function () {
    // Initialize
    loadAnalytics();

    // Event listeners
    document.querySelectorAll('.subject-card').forEach(card => {
        card.addEventListener('click', function () {
            const subject = this.dataset.subject;
            window.location.href = `/chatbot?topic=${subject}`;
        });
    });

    document.getElementById('logoutBtn').addEventListener('click', function () {
        window.location.href = '/logout';
    });

    // Load analytics
    function loadAnalytics() {
        fetch('/api/get_analytics')
            .then(response => {
                if (!response.ok) {
                    throw new Error('Network response was not ok');
                }
                return response.json();
            })
            .then(data => {
                if (data.progress && data.recent_interactions) {
                    renderCharts(data.progress);
                    renderRecentActivity(data.recent_interactions);
                } else {
                    showError('No analytics data available');
                }
            })
            .catch(error => {
                console.error('Error loading analytics:', error);
                showError('Failed to load analytics data');
            });
    }
    // Load analytics

    function loadAnalytics() {
        fetch('/api/get_analytics')
            .then(response => {
                if (!response.ok) {
                    throw new Error('Network response was not ok');
                }
                return response.json();
            })
            .then(data => {
                if (data.progress && data.recent_interactions) {
                    renderCharts(data.progress);
                    renderRecentActivity(data.recent_interactions);
                } else {
                    showError('No analytics data available');
                }
            })
            .catch(error => {
                console.error('Error loading analytics:', error);
                showError('Failed to load analytics data');
            });
    }

    function showError(message) {
        document.querySelector('.charts-container').innerHTML = `
        <div class="error-message">
            <p>${message}</p>
            <button onclick="loadAnalytics()">Retry</button>
        </div>
    `;
    }
    // Render charts
    function renderCharts(progressData) {
        if (progressData.length === 0) {
            // No data yet
            document.getElementById('performanceChart').parentNode.innerHTML = '<p>No learning data available yet. Start a session to see your progress!</p>';
            document.getElementById('timeChart').parentNode.innerHTML = '<p>No learning data available yet. Start a session to see your response times!</p>';
            return;
        }

        // Performance chart (correct vs incorrect by topic)
        const performanceCtx = document.getElementById('performanceChart').getContext('2d');

        const topics = progressData.map(item => item.topic);
        const correctData = progressData.map(item => item.correct_count);
        const incorrectData = progressData.map(item => item.incorrect_count);

        new Chart(performanceCtx, {
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
        const timeCtx = document.getElementById('timeChart').getContext('2d');

        new Chart(timeCtx, {
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
                        data: topics.map(() => 12.5), // Middle of optimal range
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
    }

    // Render recent activity
    function renderRecentActivity(activities) {
        const recentActivitiesElement = document.getElementById('recentActivities');

        if (activities.length === 0) {
            recentActivitiesElement.innerHTML = '<p>No recent activities. Start a learning session!</p>';
            return;
        }

        let activityHTML = '';

        activities.forEach(activity => {
            const date = new Date(activity.timestamp).toLocaleString();
            const statusClass = activity.is_correct ? 'activity-correct' : 'activity-incorrect';
            const statusText = activity.is_correct ? 'Correct' : 'Incorrect';
            const responseTime = activity.response_time.toFixed(1);

            activityHTML += `
                <div class="activity-item">
                    <div class="activity-info">
                        <strong>${activity.topic.charAt(0).toUpperCase() + activity.topic.slice(1)}:</strong> 
                        ${truncateText(activity.question, 40)}
                    </div>
                    <div class="activity-status ${statusClass}">
                        ${statusText} (${responseTime}s)
                    </div>
                </div>
            `;
        });

        recentActivitiesElement.innerHTML = activityHTML;
    }

    // Helper function to truncate text
    function truncateText(text, maxLength) {
        if (text.length <= maxLength) return text;
        return text.slice(0, maxLength) + '...';
    }
});