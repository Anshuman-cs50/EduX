import os
import re
import sqlite3
import logging
import time
from datetime import datetime
from difflib import SequenceMatcher
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.exceptions import HTTPException
import random
from modules.llm_handler import LLMHandler
import json  
from markupsafe import escape
import requests
llm = LLMHandler()
# First ensure required directories exist
os.makedirs('logs', exist_ok=True)
os.makedirs('database', exist_ok=True)

# Then configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('logs/app.log')
    ]
)
logger = logging.getLogger(__name__)
# Add this near your CONFIG section
# At the TOP of app.py (before any functions that use it)
CONFIG = {
    'DATABASE_PATH': 'database/edu_chat.db',
    'REQUIRE_EMAIL_VERIFICATION': False,
    'PASSWORD_MIN_LENGTH': 8,
    'SESSION_TIMEOUT_MINUTES': 30,
    'SUBJECT_MODELS': {
        'math': 'wizard-math:7b',
        'science': 'dolphin-mistral:latest',
        'history': 'mistral-openorca:latest',  # Fixed name
        'english': 'mistral:7b-instruct',      # Fixed name
        'gk': 'mistral:7b-instruct'           # Fixed name
    }
}

# Then define your prompt loading function
PROMPT_TEMPLATES_DIR = "modules/prompts"

def load_prompt_templates():
    """Load all prompt templates from files"""
    templates = {}
    for subject in CONFIG['SUBJECT_MODELS'].keys():
        try:
            with open(f"{PROMPT_TEMPLATES_DIR}/{subject}.txt", "r", encoding='utf-8') as f:
                content = f.read()
                templates[subject] = content
        except FileNotFoundError:
            logger.warning(f"No prompt template found for {subject}")
            templates[subject] = f"You are an expert {subject} tutor. Teach effectively."
    return templates

def format_prompt_with_values(topic, level, user_query):
    """Format the prompt with topic, level, and user query"""
    prompt_template = PROMPT_TEMPLATES.get(topic, PROMPT_TEMPLATES['math'])
    return LLMHandler.format_prompt(
        prompt_template,
        {
            "TOPIC": topic,
            "LEVEL": level,
            "USER_QUERY": user_query
        }
    )

def init_models():
    """Ensure all required Ollama models are available"""
    try:
        available_models_output = os.popen('ollama list').read()
        if not available_models_output:
            raise ValueError("Failed to retrieve available models from Ollama")
        
        available_models = [model.split(':')[0] for model in available_models_output.splitlines()]
        for model in set(CONFIG['SUBJECT_MODELS'].values()):
            if model.split(':')[0] not in available_models:
                logger.error(f"Model not found: {model}")
                raise ValueError(f"Model not found: {model}")
            logger.info(f"Model configured: {model}")
    except Exception as e:
        logger.error(f"Model initialization error: {str(e)}")
        raise

PROMPT_TEMPLATES = load_prompt_templates()

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', os.urandom(24).hex())

# Database Setup
def init_db():
    """Initialize database tables"""
    try:
        os.makedirs('database', exist_ok=True)
        os.makedirs('logs', exist_ok=True)
        
        with sqlite3.connect(CONFIG['DATABASE_PATH']) as conn:
            cursor = conn.cursor()
            
            # Users Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    email TEXT UNIQUE,
                    password_hash TEXT NOT NULL,
                    is_verified BOOLEAN DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    last_login DATETIME,
                    reset_token TEXT,
                    reset_token_expiry DATETIME
                )
            ''')
            
            # Sessions Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    session_token TEXT NOT NULL,
                    ip_address TEXT,
                    user_agent TEXT,
                    expires_at DATETIME NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
            ''')
            
            # Interactions Table (for chat history)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS interactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    topic TEXT NOT NULL,
                    question TEXT NOT NULL,
                    answer TEXT NOT NULL,
                    is_correct BOOLEAN NOT NULL,
                    response_time REAL NOT NULL,
                    model_used TEXT NOT NULL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
            ''')
            
            # Progress Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS user_progress (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    topic TEXT NOT NULL,
                    correct_count INTEGER DEFAULT 0,
                    incorrect_count INTEGER DEFAULT 0,
                    avg_response_time REAL DEFAULT 0,
                    last_updated DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id),
                    UNIQUE(user_id, topic)
                )
            ''')
            
            conn.commit()
            logger.info("Database initialized successfully")
            
    except Exception as e:
        logger.critical(f"Database initialization failed: {str(e)}")
        raise

def init_models():
    """Ensure all required Ollama models are available"""
    try:
        for model in set(CONFIG['SUBJECT_MODELS'].values()):
            logger.info(f"Model configured: {model}")
            # In production, you would verify the model exists here
    except Exception as e:
        logger.error(f"Model initialization error: {str(e)}")

init_db()
init_models()

# Helper Functions
def validate_email(email):
    """Validate email format"""
    return re.match(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$", email)

def validate_password(password):
    """Validate password strength"""
    if len(password) < CONFIG['PASSWORD_MIN_LENGTH']:
        return False, f"Password must be at least {CONFIG['PASSWORD_MIN_LENGTH']} characters"
    if not re.search(r"[A-Z]", password):
        return False, "Password must contain at least one uppercase letter"
    if not re.search(r"[a-z]", password):
        return False, "Password must contain at least one lowercase letter"
    if not re.search(r"\d", password):
        return False, "Password must contain at least one number"
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
        return False, "Password must contain at least one special character"
    return True, ""

def get_db_connection():
    """Get database connection with row factory"""
    conn = sqlite3.connect(CONFIG['DATABASE_PATH'])
    conn.row_factory = sqlite3.Row
    return conn

def load_prompt_templates():
    """Load all prompt templates from files"""
    templates = {}
    for subject in CONFIG['SUBJECT_MODELS'].keys():
        try:
            with open(f"{PROMPT_TEMPLATES_DIR}/{subject}.txt", "r", encoding='utf-8') as f:
                content = f.read()
                templates[subject] = content
        except FileNotFoundError:
            logger.warning(f"No prompt template found for {subject}")
            templates[subject] = f"You are an expert {subject} tutor. Please provide detailed and helpful responses."
    return templates

# Authentication Routes
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    """User registration endpoint"""
    if request.method == 'GET':
        return render_template('auth/signup.html')
    
    try:
        data = request.form if request.form else request.get_json()
        username = data.get('username', '').strip()
        email = data.get('email', '').strip().lower()
        password = data.get('password', '')
        confirm_password = data.get('confirm_password', '')
        
        # Validation
        if not all([username, email, password, confirm_password]):
            raise ValueError("All fields are required")
        if password != confirm_password:
            raise ValueError("Passwords do not match")
        if not validate_email(email):
            raise ValueError("Invalid email format")
        
        is_valid, pw_error = validate_password(password)
        if not is_valid:
            raise ValueError(pw_error)
        
        # Check existing user
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id FROM users WHERE username = ? OR email = ?",
                (username, email)
            )
            if cursor.fetchone():
                raise ValueError("Username or email already exists")
            
            # Create user
            password_hash = generate_password_hash(password)
            cursor.execute(
                "INSERT INTO users (username, email, password_hash, is_verified) VALUES (?, ?, ?, ?)",
                (username, email, password_hash, not CONFIG['REQUIRE_EMAIL_VERIFICATION'])
            )
            user_id = cursor.lastrowid
            conn.commit()
        
        # Start session (skip if email verification required)
        if not CONFIG['REQUIRE_EMAIL_VERIFICATION']:
            session['user_id'] = user_id
            session['username'] = username
            logger.info(f"New user registered: {username}")
            return jsonify({
                'success': True,
                'message': 'Registration successful',
                'redirect': url_for('dashboard')
            })
        
        # TODO: Add email verification logic here
        return jsonify({
            'success': True,
            'message': 'Registration successful. Please check your email to verify your account.'
        })
        
    except Exception as e:
        logger.error(f"Signup error: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400

@app.route('/login', methods=['GET', 'POST'])
def login():
    """User authentication endpoint"""
    if request.method == 'GET':
        return render_template('auth/login.html')
    
    try:
        data = request.form if request.form else request.get_json()
        username_or_email = data.get('username', '').strip()
        password = data.get('password', '')
        remember_me = data.get('remember_me', False)
        
        if not username_or_email or not password:
            raise ValueError("Username/email and password are required")
        
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, username, password_hash, is_verified FROM users WHERE username = ? OR email = ?",
                (username_or_email, username_or_email)
            )
            user = cursor.fetchone()
            
            if not user or not check_password_hash(user['password_hash'], password):
                raise ValueError("Invalid credentials")
            
            if CONFIG['REQUIRE_EMAIL_VERIFICATION'] and not user['is_verified']:
                raise ValueError("Please verify your email before logging in")
            
            # Update last login
            cursor.execute(
                "UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?",
                (user['id'],)
            )
            conn.commit()
        
        # Set session
        session['user_id'] = user['id']
        session['username'] = user['username']
        
        logger.info(f"User logged in: {user['username']}")
        return jsonify({
            'success': True,
            'message': 'Login successful',
            'redirect': url_for('dashboard')
        })
        
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 401

@app.route('/logout')
def logout():
    """Terminate user session"""
    try:
        username = session.get('username', 'unknown')
        session.clear()
        logger.info(f"User logged out: {username}")
        return redirect(url_for('login'))
    except Exception as e:
        logger.error(f"Logout error: {str(e)}")
        return redirect(url_for('login'))

# Main Application Routes
@app.route('/')
def home():
    """Landing page"""
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('home.html')

@app.route('/dashboard')
def dashboard():
    """User dashboard"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT topic, correct_count, incorrect_count, avg_response_time FROM user_progress WHERE user_id = ?",
                (session['user_id'],)
            )
            progress_data = cursor.fetchall()
        
        return render_template('dashboard.html', progress_data=progress_data)
    except Exception as e:
        logger.error(f"Dashboard error: {str(e)}")
        return redirect(url_for('login'))

@app.route('/chatbot')
def chatbot():
    """Chatbot interface for different subjects"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    topic = request.args.get('topic', 'math').lower()
    if topic not in CONFIG['SUBJECT_MODELS']:
        logger.warning(f"Invalid topic requested: {topic}")
        return redirect(url_for('dashboard'))
    
    try:
        return render_template('chatbot.html', 
                             topic=escape(topic),
                             username=escape(session.get('username', 'User')))
    except Exception as e:
        logger.error(f"Chatbot error: {str(e)}")
        return redirect(url_for('dashboard'))

@app.route('/api/get_questions', methods=['POST'])
def get_questions():
    try:
        # Validate input
        if not request.is_json:
            return jsonify({"error": "Request must be JSON"}), 400
            
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400
            
        topic = data.get('topic', 'math').lower()
        level = data.get('level', 'beginner').lower()
        
        # Validate topic exists
        if topic not in CONFIG['SUBJECT_MODELS']:
            return jsonify({"error": f"Invalid topic: {topic}"}), 400
            
        # Get the appropriate prompt template
        prompt_template = PROMPT_TEMPLATES.get(topic)
        if not prompt_template:
            logger.error(f"No prompt template found for topic: {topic}")
            return jsonify({"error": "Configuration error"}), 500
            
        # Format the prompt
        try:
            formatted_prompt = LLMHandler.format_prompt(
                prompt_template,
                {
                    "TOPIC": topic,
                    "LEVEL": level,
                    "USER_QUERY": """Generate a multiple choice question with:
- A clear question
- 4 options (1 correct)
- Explanation
Format as JSON with these exact keys: question, options, correct_answer, explanation"""
                }
            )
        except Exception as e:
            logger.error(f"Prompt formatting failed: {str(e)}")
            return jsonify({"error": "Prompt generation failed"}), 500
            
        # Get model for this topic
        model = CONFIG['SUBJECT_MODELS'].get(topic)
        
        # Call LLM with timeout
        try:
            response = llm.generate_response(
                prompt=formatted_prompt,
                system_prompt="You are creating educational content. Provide only the JSON response.",
                model=model
            )
            
            # Debug logging (remove in production)
            logger.debug(f"Raw LLM response for topic '{topic}': {response}")
            
            # Extract the first JSON block from the response
            try:
                json_match = re.search(r'\{.*?\}', response, re.DOTALL)
                if not json_match:
                    raise ValueError("No JSON block found in the response")
                
                clean_response = json_match.group()
                question = json.loads(clean_response)
                
                # Validate response structure
                required_keys = {'question', 'options', 'correct_answer', 'explanation'}
                if not all(key in question for key in required_keys):
                    missing = required_keys - question.keys()
                    raise ValueError(f"Missing required fields: {missing}")
                    
                if not isinstance(question['options'], list) or len(question['options']) != 4:
                    raise ValueError("Options must be a list of 4 items")
                    
                if question['correct_answer'] not in question['options']:
                    logger.warning("Correct answer not in options. Adjusting response.")
                    question['correct_answer'] = question['options'][0]  # Default to the first option
                    
                return jsonify([question])
                
            except json.JSONDecodeError as e:
                logger.error(f"JSON parse error: {str(e)}. Response: {response}")
                return jsonify({
                    "error": "The AI returned an invalid format",
                    "fallback_question": {
                        'question': "Explain the key concepts of " + topic,
                        'options': ['Concept 1', 'Concept 2', 'Concept 3', 'Concept 4'],
                        'correct_answer': 'Concept 1',
                        'explanation': 'The AI response could not be parsed'
                    }
                }), 502
                
        except requests.exceptions.Timeout:
            logger.error("LLM request timed out")
            return jsonify({"error": "The AI is taking too long to respond"}), 504
        except Exception as e:
            logger.error(f"LLM request failed: {str(e)}")
            return jsonify({"error": "Failed to generate question"}), 500
            
    except Exception as e:
        logger.error(f"Unexpected error in question generation: {str(e)}")
        return jsonify({"error": "An unexpected error occurred"}), 500

@app.route('/api/chat', methods=['POST'])
def handle_chat():
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    try:
        data = request.json
        user_id = session['user_id']
        topic = data.get('topic', 'math')
        user_answer = data.get('message', '').strip().lower()
        question = data.get('question', '')
        expected_answer = data.get('expected_answer', '').strip().lower()
        start_time = data.get('start_time', time.time())
        
        # Calculate response time
        response_time = time.time() - float(start_time)
        
        # Determine correctness
        is_correct = user_answer == expected_answer
        
        # Get the appropriate prompt template
        prompt_template = PROMPT_TEMPLATES.get(topic, PROMPT_TEMPLATES['math'])
        
        # Format the prompt with actual values
        formatted_prompt = LLMHandler.format_prompt(
            prompt_template,
            {
                "TOPIC": topic,
                "LEVEL": "beginner",
                "USER_QUERY": f"Student answered: '{user_answer}'\n"
                             f"Original question: '{question}'\n"
                             f"Response time: {response_time:.1f} seconds\n"
                             f"Provide feedback and next steps:"
            }
        )
        
        # Get model for this topic
        model = CONFIG['SUBJECT_MODELS'].get(topic, 'mistral-7b-instruct')
        
        # Call LLM for feedback
        llm_response = llm.generate_response(
            prompt=formatted_prompt,
            system_prompt="You are an expert educational assistant.",
            model=model
        )
        
        # Log interaction
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO interactions 
                (user_id, topic, question, answer, is_correct, response_time, model_used)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                user_id,
                topic,
                question,
                user_answer,
                is_correct,
                response_time,
                model
            ))
            conn.commit()
        
        return jsonify({
            'response': llm_response,
            'response_time': response_time,
            'is_correct': is_correct
        })
        
    except Exception as e:
        logger.error(f"Chat error: {str(e)}")
        return jsonify({'error': str(e)}), 500
        
@app.route('/api/get_analytics')
def get_analytics():
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    try:
        with get_db_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Get progress data by subject
            cursor.execute('''
                SELECT topic, 
                       SUM(correct_count) as correct_count,
                       SUM(incorrect_count) as incorrect_count,
                       AVG(avg_response_time) as avg_response_time
                FROM user_progress
                WHERE user_id = ?
                GROUP BY topic
            ''', (session['user_id'],))
            progress_data = [dict(row) for row in cursor.fetchall()]
            
            # Get recent interactions
            cursor.execute('''
                SELECT topic, question, answer, is_correct, response_time, timestamp
                FROM interactions
                WHERE user_id = ?
                ORDER BY timestamp DESC
                LIMIT 10
            ''', (session['user_id'],))
            recent_interactions = [dict(row) for row in cursor.fetchall()]
        
        return jsonify({
            'progress': progress_data,
            'recent_interactions': recent_interactions
        })
        
    except Exception as e:
        logger.error(f"Analytics error: {str(e)}")
        return jsonify({'error': str(e)}), 500
      
# Error Handlers
@app.errorhandler(404)
def page_not_found(e):
    return render_template('errors/404.html'), 404

@app.errorhandler(403)
def forbidden(e):
    return render_template('errors/403.html'), 403

@app.errorhandler(500)
def internal_error(e):
    return render_template('errors/500.html'), 500

@app.errorhandler(HTTPException)
def handle_exception(e):
    return render_template('errors/generic.html', error=e), e.code

# Main Execution
if __name__ == '__main__':
    # Create required directories
    os.makedirs('templates/auth', exist_ok=True)
    os.makedirs('templates/errors', exist_ok=True)
    os.makedirs('static/css', exist_ok=True)
    os.makedirs('static/js', exist_ok=True)
    
    # Run application
    app.run(host='0.0.0.0', port=5000, debug=True)