// Test Functionality

document.addEventListener('DOMContentLoaded', function() {
    // Elements
    const takeTestBtn = document.getElementById('takeTestBtn');
    const testModal = document.getElementById('testModal');
    const closeModal = document.querySelector('.close-modal');
    const testForm = document.getElementById('testForm');
    const testInterface = document.getElementById('testInterface');
    const testTitle = document.getElementById('testTitle');
    const closeTestBtn = document.getElementById('closeTestBtn');
    const loadingQuestions = document.getElementById('loadingQuestions');
    const questionContent = document.getElementById('questionContent');
    const questionText = document.getElementById('questionText');
    const optionsContainer = document.getElementById('optionsContainer');
    const prevQuestionBtn = document.getElementById('prevQuestionBtn');
    const nextQuestionBtn = document.getElementById('nextQuestionBtn');
    const submitTestBtn = document.getElementById('submitTestBtn');
    const questionCounter = document.getElementById('questionCounter');
    const timer = document.getElementById('timer');
    const testResults = document.getElementById('testResults');
    const finalScore = document.getElementById('finalScore');
    const scorePercentage = document.getElementById('scorePercentage');
    const timeTaken = document.getElementById('timeTaken');
    const questionsReview = document.getElementById('questionsReview');
    const retakeTestBtn = document.getElementById('retakeTestBtn');
    const backToDashboardBtn = document.getElementById('backToDashboardBtn');

    // Test state
    let questions = [];
    let currentQuestionIndex = 0;
    let userAnswers = [];
    let startTime;
    let timerInterval;
    let secondsElapsed = 0;
    let testActive = false;
    let currentSubject = '';
    let currentTopic = '';

    // Modal event listeners
    takeTestBtn.addEventListener('click', openTestModal);
    closeModal.addEventListener('click', closeTestModal);
    testForm.addEventListener('submit', handleTestFormSubmit);
    
    // Test interface event listeners
    closeTestBtn.addEventListener('click', confirmCloseTest);
    prevQuestionBtn.addEventListener('click', goToPreviousQuestion);
    nextQuestionBtn.addEventListener('click', goToNextQuestion);
    submitTestBtn.addEventListener('click', submitTest);
    retakeTestBtn.addEventListener('click', retakeTest);
    backToDashboardBtn.addEventListener('click', closeTestInterface);

    // Close modal when clicking outside
    window.addEventListener('click', function(event) {
        if (event.target === testModal) {
            closeTestModal();
        }
    });

    // Functions
    function openTestModal() {
        testModal.style.display = 'block';
    }

    function closeTestModal() {
        testModal.style.display = 'none';
        testForm.reset();
    }

    function handleTestFormSubmit(e) {
        e.preventDefault();
        
        // Get form values
        const subject = document.getElementById('testSubject').value;
        const topic = document.getElementById('testTopic').value;
        
        // Start test with these values
        startTest(subject, topic);
        
        // Close modal
        closeTestModal();
    }

    function startTest(subject, topic) {
        // Set current subject and topic
        currentSubject = subject;
        currentTopic = topic;
        
        // Update test title
        const subjectDisplay = getSubjectDisplayName(subject);
        testTitle.textContent = `${subjectDisplay} - ${topic}`;
        
        // Reset test state
        questions = [];
        currentQuestionIndex = 0;
        userAnswers = [];
        secondsElapsed = 0;
        testActive = true;
        
        // Show test interface
        testInterface.style.display = 'block';
        
        // Show loading, hide question content and results
        loadingQuestions.style.display = 'block';
        questionContent.style.display = 'none';
        testResults.style.display = 'none';
        
        // Generate questions
        generateQuestions(subject, topic)
            .then(generatedQuestions => {
                // Save questions
                questions = generatedQuestions;
                
                // Initialize user answers array
                userAnswers = new Array(questions.length).fill(null);
                
                // Start timer
                startTimer();
                
                // Hide loading
                loadingQuestions.style.display = 'none';
                
                // Show first question
                showQuestion(0);
                
                // Show question content
                questionContent.style.display = 'block';
            })
            .catch(error => {
                console.error('Error generating questions:', error);
                alert('Failed to generate questions. Please try again.');
                closeTestInterface();
            });
    }

    function getSubjectDisplayName(subjectCode) {
        const subjects = {
            'math': 'Mathematics',
            'science': 'Science',
            'history': 'History',
            'english': 'English',
            'gk': 'General Knowledge'
        };
        
        return subjects[subjectCode] || subjectCode;
    }

    async function generateQuestions(subject, topic) {
        try {
            const response = await fetch('/api/generate_test', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    subject: subject,
                    topic: topic,
                    count: 10,
                }),
            });
    
            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || 'Failed to generate questions');
            }
    
            const data = await response.json();
            return data;
        } catch (error) {
            console.error('Error generating questions:', error);
            alert(`Error: ${error.message}`);
            throw error;
        }
    }
    function createMockQuestions(subject, topic) {
        // Create mock questions based on subject and topic
        const mockQuestions = [];
        
        const questionTemplates = {
            'math': [
                'Calculate the derivative of {expr}',
                'Solve for x: {equation}',
                'Find the area of a circle with radius {r}',
                'What is {a} + {b} × {c}?',
                'Simplify the expression: {expr}'
            ],
            'science': [
                'What is the chemical formula for {compound}?',
                'Describe the process of {process}',
                'Which scientist discovered {discovery}?',
                'What is the difference between {term1} and {term2}?',
                'How does {phenomenon} work?'
            ],
            'history': [
                'When did {event} occur?',
                'Who was the leader of {country} during {period}?',
                'What caused {event}?',
                'What was the significance of {event}?',
                'Compare and contrast {event1} and {event2}'
            ],
            'english': [
                'What is the meaning of {word}?',
                'Identify the part of speech of {word} in the sentence: {sentence}',
                'Who wrote {book}?',
                'What is the main theme of {book}?',
                'Correct the grammar in the sentence: {sentence}'
            ],
            'gk': [
                'What is the capital of {country}?',
                'Who is {person} famous for?',
                'When was {invention} invented?',
                'What does the acronym {acronym} stand for?',
                'Which country is known for {thing}?'
            ]
        };
        
        // Use the topic to generate relevant questions
        for (let i = 0; i < 10; i++) {
            const templateList = questionTemplates[subject] || questionTemplates['gk'];
            const template = templateList[i % templateList.length];
            
            // Replace placeholders with topic-related content
            let questionText = template.replace(/{[^}]+}/g, match => {
                const placeholder = match.substring(1, match.length - 1);
                
                // Simple placeholder substitution
                if (placeholder === 'topic') return topic;
                
                // Subject-specific placeholders
                switch (subject) {
                    case 'math':
                        if (placeholder === 'expr') return `${topic} expression`;
                        if (placeholder === 'equation') return `2x + ${i} = ${i*2}`;
                        if (placeholder === 'r') return i + 1;
                        if (placeholder === 'a') return i;
                        if (placeholder === 'b') return i + 1;
                        if (placeholder === 'c') return i + 2;
                        break;
                    case 'science':
                        if (placeholder === 'compound') return `${topic} compound`;
                        if (placeholder === 'process') return `${topic} process`;
                        if (placeholder === 'discovery') return `${topic}`;
                        if (placeholder === 'term1') return `${topic} A`;
                        if (placeholder === 'term2') return `${topic} B`;
                        if (placeholder === 'phenomenon') return topic;
                        break;
                    case 'history':
                        if (placeholder === 'event') return `the ${topic} event`;
                        if (placeholder === 'country') return `the ${topic} region`;
                        if (placeholder === 'period') return `the ${topic} period`;
                        if (placeholder === 'event1') return `early ${topic}`;
                        if (placeholder === 'event2') return `late ${topic}`;
                        break;
                    case 'english':
                        if (placeholder === 'word') return topic;
                        if (placeholder === 'sentence') return `The ${topic} was interesting.`;
                        if (placeholder === 'book') return `${topic} Stories`;
                        break;
                    case 'gk':
                        if (placeholder === 'country') return topic;
                        if (placeholder === 'person') return topic;
                        if (placeholder === 'invention') return topic;
                        if (placeholder === 'acronym') return topic.toUpperCase();
                        if (placeholder === 'thing') return topic;
                        break;
                }
                
                return topic;
            });
            
            // Generate options
            const options = [];
            const correctIndex = Math.floor(Math.random() * 4);
            
            for (let j = 0; j < 4; j++) {
                if (j === correctIndex) {
                    options.push(`Correct answer for ${questionText}`);
                } else {
                    options.push(`Incorrect option ${j+1} for ${questionText}`);
                }
            }
            
            mockQuestions.push({
                question: questionText,
                options: options,
                correctIndex: correctIndex,
                explanation: `Explanation for ${questionText}: The correct answer is option ${correctIndex + 1}.`
            });
        }
        
        return mockQuestions;
    }

    function showQuestion(index) {
        const question = questions[index];
        
        // Update question counter
        questionCounter.textContent = `Question ${index + 1}/${questions.length}`;
        
        // Set question text
        questionText.textContent = question.question;
        
        // Clear options container
        optionsContainer.innerHTML = '';
        
        // Add options
        question.options.forEach((option, optIndex) => {
            const optionElement = document.createElement('div');
            optionElement.className = 'option-item';
            
            // Check if this option was previously selected
            if (userAnswers[index] === optIndex) {
                optionElement.classList.add('selected');
            }
            
            // Create radio input
            const radioInput = document.createElement('input');
            radioInput.type = 'radio';
            radioInput.name = 'question-option';
            radioInput.id = `option-${optIndex}`;
            radioInput.value = optIndex;
            radioInput.checked = userAnswers[index] === optIndex;
            
            // Create label
            const label = document.createElement('label');
            label.htmlFor = `option-${optIndex}`;
            label.textContent = option;
            
            // Add to option element
            optionElement.appendChild(radioInput);
            optionElement.appendChild(label);
            
            // Add click event
            optionElement.addEventListener('click', () => {
                // Update user answers
                userAnswers[currentQuestionIndex] = optIndex;
                
                // Update selected state
                document.querySelectorAll('.option-item').forEach(item => {
                    item.classList.remove('selected');
                });
                optionElement.classList.add('selected');
                
                // Check radio button
                radioInput.checked = true;
            });
            
            // Add to options container
            optionsContainer.appendChild(optionElement);
        });
        
        // Update navigation buttons
        prevQuestionBtn.disabled = index === 0;
        
        if (index === questions.length - 1) {
            nextQuestionBtn.style.display = 'none';
            submitTestBtn.style.display = 'block';
        } else {
            nextQuestionBtn.style.display = 'block';
            submitTestBtn.style.display = 'none';
        }
        
        // Update current question index
        currentQuestionIndex = index;
    }

    function goToPreviousQuestion() {
        if (currentQuestionIndex > 0) {
            showQuestion(currentQuestionIndex - 1);
        }
    }

    function goToNextQuestion() {
        if (currentQuestionIndex < questions.length - 1) {
            showQuestion(currentQuestionIndex + 1);
        }
    }

    function startTimer() {
        // Reset timer
        secondsElapsed = 0;
        updateTimerDisplay();
        
        // Start timer
        startTime = new Date();
        timerInterval = setInterval(function() {
            secondsElapsed = Math.floor((new Date() - startTime) / 1000);
            updateTimerDisplay();
        }, 1000);
    }

    function updateTimerDisplay() {
        const minutes = Math.floor(secondsElapsed / 60);
        const seconds = secondsElapsed % 60;
        timer.textContent = `Time: ${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
    }

    function stopTimer() {
        clearInterval(timerInterval);
    }

    function submitTest() {
        // Stop timer
        stopTimer();
        
        // Calculate score
        const score = calculateScore();
        
        // Show results
        showResults(score);
        
        // Test is no longer active
        testActive = false;
    }

    function calculateScore() {
        let correctCount = 0;
        
        for (let i = 0; i < questions.length; i++) {
            if (userAnswers[i] === questions[i].correctIndex) {
                correctCount++;
            }
        }
        
        return correctCount;
    }

    function showResults(score) {
        // Hide question content
        questionContent.style.display = 'none';
        
        // Update results
        finalScore.textContent = `${score}/${questions.length}`;
        scorePercentage.textContent = `${Math.round((score / questions.length) * 100)}%`;
        
        // Format time taken
        const minutes = Math.floor(secondsElapsed / 60);
        const seconds = secondsElapsed % 60;
        timeTaken.textContent = `${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
        
        // Generate detailed review
        generateReview();
        
        // Show results
        testResults.style.display = 'block';
    }

    function generateReview() {
        // Clear previous review
        questionsReview.innerHTML = '';
        
        // Generate review for each question
        questions.forEach((question, index) => {
            const userAnswer = userAnswers[index];
            const isCorrect = userAnswer === question.correctIndex;
            
            // Create review item
            const reviewItem = document.createElement('div');
            reviewItem.className = `review-item ${isCorrect ? 'correct' : 'incorrect'}`;
            
            // Question number and text
            const reviewQuestion = document.createElement('div');
            reviewQuestion.className = 'review-question';
            reviewQuestion.textContent = `Q${index + 1}: ${question.question}`;
            reviewItem.appendChild(reviewQuestion);
            
            // Options with highlights
            const reviewOptions = document.createElement('div');
            reviewOptions.className = 'review-options';
            
            question.options.forEach((option, optIndex) => {
                const reviewOption = document.createElement('div');
                reviewOption.className = 'review-option';
                
                // Highlight user answer
                if (userAnswer === optIndex) {
                    reviewOption.classList.add('user-answer');
                }
                
                // Highlight correct answer
                if (question.correctIndex === optIndex) {
                    reviewOption.classList.add('correct-answer');
                }
                
                reviewOption.textContent = `${String.fromCharCode(65 + optIndex)}. ${option}`;
                reviewOptions.appendChild(reviewOption);
            });
            
            reviewItem.appendChild(reviewOptions);
            
            // Add explanation
            const reviewExplanation = document.createElement('div');
            reviewExplanation.className = 'review-explanation';
            reviewExplanation.textContent = question.explanation || 'No explanation available.';
            reviewItem.appendChild(reviewExplanation);
            
            // Add to review container
            questionsReview.appendChild(reviewItem);
        });
    }

    function confirmCloseTest() {
        if (testActive && confirm('Are you sure you want to exit the test? Your progress will be lost.')) {
            closeTestInterface();
        } else if (!testActive) {
            closeTestInterface();
        }
    }

    function closeTestInterface() {
        // Stop timer if running
        stopTimer();
        
        // Hide test interface
        testInterface.style.display = 'none';
        
        // Reset state
        testActive = false;
    }

    function retakeTest() {
        // Start test with same subject and topic
        startTest(currentSubject, currentTopic);
    }

    // Close test interface when ESC key is pressed
    document.addEventListener('keydown', function(event) {
        if (event.key === 'Escape' && testInterface.style.display === 'block') {
            confirmCloseTest();
        }
    });
});