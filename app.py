import os
import re
import sqlite3
import logging
import time
from datetime import datetime
from difflib import SequenceMatcher
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, send_file
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.exceptions import HTTPException
import random
from modules.llm_handler import LLMHandler
import json  
from modules.summarize import Summarizer
from markupsafe import escape
import requests
import cv2
import numpy as np
import subprocess
from PIL import Image
import pytesseract
from datetime import timedelta
from skimage.metrics import structural_similarity as ssim
llm = LLMHandler()

# Logging setup
os.makedirs('logs', exist_ok=True)
os.makedirs('database', exist_ok=True)
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('logs/app.log', mode='a')
    ]
)
logger = logging.getLogger(__name__)

CONFIG = {
    'DATABASE_PATH': 'database/edu_chat.db',
    'REQUIRE_EMAIL_VERIFICATION': False,
    'PASSWORD_MIN_LENGTH': 8,
    'SESSION_TIMEOUT_MINUTES': 30,
    'SUBJECT_MODELS': {
        'math': 'wizard-math:7b',
        'science': 'dolphin-mistral:latest',
        'history': 'mistral-openorca:latest',
        'english': 'mistral:7b-instruct',
        'gk': 'mistral:7b-instruct'
    }
}

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
            templates[subject] = f"You are an expert {subject} tutor. Please provide detailed and helpful responses."
    return templates

PROMPT_TEMPLATES = load_prompt_templates()

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', os.urandom(24).hex())

USER_DB_PATH = 'database/user_data.db'
EDU_DB_PATH = 'database/edu_chat.db'

def init_db():
    """Initialize user-related tables in user_data.db"""
    try:
        db_path = USER_DB_PATH
        os.makedirs('database', exist_ok=True)
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            # Users table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    email TEXT UNIQUE,
                    password_hash TEXT NOT NULL,
                    is_verified BOOLEAN DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    last_login DATETIME
                )
            ''')
            # User progress table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS user_progress (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    topic TEXT,
                    correct_count INTEGER DEFAULT 0,
                    incorrect_count INTEGER DEFAULT 0,
                    avg_response_time REAL DEFAULT 0,
                    FOREIGN KEY(user_id) REFERENCES users(id)
                )
            ''')
            # Interactions table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS interactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    topic TEXT,
                    question TEXT,
                    answer TEXT,
                    is_correct BOOLEAN,
                    response_time REAL,
                    model_used TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(user_id) REFERENCES users(id)
                )
            ''')
            # Add a new table for rapid quiz responses
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS rapid_quiz_responses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    topic TEXT,
                    question TEXT,
                    user_answer TEXT,
                    correct_answer TEXT,
                    is_correct BOOLEAN,
                    response_time REAL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(user_id) REFERENCES users(id)
                )
            ''')
            # Add feedback table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS feedback (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    interaction_id INTEGER,
                    helpful_rating INTEGER,
                    clarity_rating INTEGER,
                    engagement_rating INTEGER,
                    comments TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(user_id) REFERENCES users(id),
                    FOREIGN KEY(interaction_id) REFERENCES interactions(id)
                )
            ''')
            # Add user preferences table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS user_preferences (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER UNIQUE,
                    interests TEXT,
                    learning_style TEXT,
                    preferred_explanation_style TEXT DEFAULT 'standard',
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(user_id) REFERENCES users(id)
                )
            ''')
            conn.commit()
            logger.info(f"Database {db_path} initialized successfully")
    except Exception as e:
        logger.critical(f"Database initialization failed for {db_path}: {str(e)}")
        raise
init_db()

def init_models():
    """Initialize/check LLM models if needed. Currently a placeholder."""
    # You can add model download/check logic here if needed.
    logger.info("init_models called (no-op placeholder).")
init_models()

summarizer = Summarizer()

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

def get_db_connection(db_path=USER_DB_PATH):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

# Authentication Routes
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'GET':
        return render_template('auth/signup.html')
    try:
        data = request.form if request.form else request.get_json()
        username = data.get('username', '').strip()
        email = data.get('email', '').strip().lower()
        password = data.get('password', '')
        confirm_password = data.get('confirm_password', '')
        if not all([username, email, password, confirm_password]):
            raise ValueError("All fields are required")
        if password != confirm_password:
            raise ValueError("Passwords do not match")
        if not validate_email(email):
            raise ValueError("Invalid email format")
        is_valid, pw_error = validate_password(password)
        if not is_valid:
            raise ValueError(pw_error)
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id FROM users WHERE username = ? OR email = ?",
                (username, email)
            )
            if cursor.fetchone():
                raise ValueError("Username or email already exists")
            password_hash = generate_password_hash(password)
            cursor.execute(
                "INSERT INTO users (username, email, password_hash, is_verified) VALUES (?, ?, ?, ?)",
                (username, email, password_hash, not CONFIG['REQUIRE_EMAIL_VERIFICATION'])
            )
            user_id = cursor.lastrowid
            conn.commit()
        if not CONFIG['REQUIRE_EMAIL_VERIFICATION']:
            session['user_id'] = user_id
            session['username'] = username
            logger.info(f"New user registered: {username}")
            return jsonify({
                'success': True,
                'message': 'Registration successful',
                'redirect': url_for('dashboard')
            })
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
            cursor.execute(
                "UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?",
                (user['id'],)
            )
            conn.commit()
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
    try:
        username = session.get('username', 'unknown')
        session.clear()
        logger.info(f"User logged out: {username}")
        return redirect(url_for('login'))
    except Exception as e:
        logger.error(f"Logout error: {str(e)}")
        return redirect(url_for('login'))

@app.route('/')
def home():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('home.html')

@app.route('/dashboard')
def dashboard():
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
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    subject = request.args.get('subject', 'math').lower()
    if subject not in CONFIG['SUBJECT_MODELS']:
        return redirect(url_for('dashboard'))
    
    initial_message = f"Welcome to the {subject.title()} learning session! Please specify a topic you'd like to learn about and select your grade level to begin."
    
    return render_template(
        'chatbot.html',
        subject=subject,
        initial_message=initial_message,
        username=session.get('username', 'User')
    )

@app.route('/api/chat', methods=['POST'])
def handle_chat():
    if not llm.server_available:
        return jsonify({'error': 'Ollama server is not available. Chat functionality is disabled.'}), 503
    
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    try:
        data = request.json
        user_id = session['user_id']
        topic = data.get('topic', 'math')
        user_message = data.get('message', '').strip()
        chat_stage = data.get('stage', 'question')
        conversation_history = data.get('history', [])
        difficulty_level = data.get('difficulty', 'beginner')
        
        # Get the subject from URL parameters
        subject = request.args.get('subject', 'math').lower()
        if subject not in CONFIG['SUBJECT_MODELS']:
            subject = 'math'  # Default to math if invalid subject
        
        # Get the appropriate model and prompt template for the subject
        model = CONFIG['SUBJECT_MODELS'].get(subject, CONFIG['SUBJECT_MODELS']['math'])
        prompt_template = PROMPT_TEMPLATES.get(subject, PROMPT_TEMPLATES['math'])
        
        # Map difficulty levels to more specific descriptions
        difficulty_mapping = {
            'beginner': 'elementary school level (grades 1-5)',
            'intermediate': 'middle school level (grades 6-8)',
            'advanced': 'high school level (grades 9-12)',
            'expert': 'college/university level'
        }
        
        student_level = difficulty_mapping.get(difficulty_level, 'beginner')
        
        # Prepare enhanced system prompt
        system_prompt = (
            f"You are an expert educational tutor specializing in {subject}. "
            f"You are teaching at a {student_level}. "
            "Your goal is to help students understand concepts deeply through Socratic dialogue, "
            "guiding questions, and constructive feedback. Emulate the style of an engaging, "
            "patient, and knowledgeable teacher who values critical thinking. "
            
            # Added more specific Socratic teaching guidelines
            "When using the Socratic method: "
            "- Ask open-ended questions that require more than yes/no answers "
            "- Respond to student answers with follow-up questions that prompt deeper thinking "
            "- Help students discover answers through guided reasoning rather than direct instruction "
            "- Acknowledge student contributions and build upon their ideas "
            "- Use strategic pauses and wait time to encourage reflection "
            
            "Use concrete examples and establish connections between concepts. "
            "Tailor your explanations to the student's level while gradually introducing more complex ideas. "
            
            # Added important guardrails
            "EXTREMELY IMPORTANT GUIDELINES: "
            "1. Write all responses directly to the student in first-person conversational tone. "
            "2. NEVER include meta text like 'Teaching approach:' or 'Step 1:' in your response. "
            "3. NEVER refer to yourself as a teacher or AI - just respond naturally. "
            "4. Keep responses brief and focused - no more than 2-3 paragraphs max. "
            "5. Use simple, clear language appropriate for the student's level. "
            "6. Do not label steps or include instructions to yourself in the response."
        )
        
        # Get user's interests and learning style if available
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT interests, learning_style FROM user_preferences WHERE user_id = ?', (user_id,))
                user_prefs = cursor.fetchone()
                
                if user_prefs:
                    interests = user_prefs[0]
                    learning_style = user_prefs[1]
                    
                    # Append personalization to the system prompt
                    if interests:
                        system_prompt += f" This student has expressed interest in {interests}. Try to connect examples to these interests when relevant."
                        
                    if learning_style:
                        system_prompt += f" This student tends to learn best through {learning_style} approaches."
        except Exception as db_error:
            # If there's an error, just continue without the personalization
            logger.error(f"Failed to fetch user preferences: {str(db_error)}")

        # Get performance data on this topic if available
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT AVG(is_correct) as success_rate 
                    FROM interactions 
                    WHERE user_id = ? AND topic LIKE ?
                    GROUP BY user_id
                ''', (user_id, f"%{topic}%"))
                
                result = cursor.fetchone()
                
                if result and result[0] is not None:
                    success_rate = result[0]
                    
                    # Customize difficulty based on past performance
                    if success_rate > 0.8:
                        system_prompt += f" The student seems to be performing well on this topic (success rate: {success_rate:.0%}). Consider introducing more challenging concepts."
                    elif success_rate < 0.4:
                        system_prompt += f" The student seems to be struggling with this topic (success rate: {success_rate:.0%}). Focus on building foundational understanding with extra examples."
        except Exception as db_error:
            # If there's an error, just continue without the performance data
            logger.error(f"Failed to fetch performance data: {str(db_error)}")
        
        # Handle different stages of the teaching conversation
        if chat_stage == 'introduction':
            formatted_prompt = LLMHandler.format_prompt(
                prompt_template,
                {
                    "TOPIC": topic,
                    "LEVEL": difficulty_level,
                    "USER_QUERY": f"Introduce the topic of {topic} briefly for a {student_level} student. Explain why this topic is important and relevant to the student. Then, outline 2-3 key concepts we'll explore together. End with a thought-provoking question that encourages the student to think about their prior knowledge of {topic}."
                }
            )
            
        elif chat_stage == 'knowledge_assessment':
            formatted_prompt = LLMHandler.format_prompt(
                prompt_template,
                {
                    "TOPIC": topic,
                    "LEVEL": difficulty_level,
                    "USER_QUERY": f"""
Create a brief diagnostic assessment with 2-3 questions to gauge the student's current understanding of {topic} at a {student_level}. 

The questions should:
- Start with easier concepts and build to more challenging ones
- Include at least one question requiring critical thinking rather than just recall
- Be presented in a friendly, non-intimidating way

Write this directly to the student in a conversational tone, explaining that you'd like to understand their current knowledge to better guide the session.
"""
                }
            )
            
        elif chat_stage == 'conceptual_question':
            formatted_prompt = LLMHandler.format_prompt(
                prompt_template,
                {
                    "TOPIC": topic,
                    "LEVEL": difficulty_level,
                    "USER_QUERY": f"Generate a thought-provoking, theoretical question about {topic} that is appropriate for a {student_level} student. The question should require understanding of core concepts rather than just facts. The question should encourage critical thinking and be answerable in a few sentences. Ask the question in a conversational, teacher-like way."
                }
            )
            
        elif chat_stage == 'evaluate_response':
            previous_question = data.get('previous_question', '')
            
            formatted_prompt = LLMHandler.format_prompt(
                prompt_template,
                {
                    "TOPIC": topic,
                    "LEVEL": difficulty_level,
                    "USER_QUERY": f"""
Student's question: "{previous_question}"
Student's response: "{user_message}"

The student is at a {student_level}.

Analyze what the student understands correctly. Identify any misconceptions or areas that need clarification. Provide constructive feedback that acknowledges their effort. Explain the correct concept if needed. End with a follow-up question that deepens understanding.

Keep your response conversational and encouraging. Write directly to the student - do NOT include instructions or steps in your response.
"""
                }
            )
            
        elif chat_stage == 'follow_up':
            formatted_prompt = LLMHandler.format_prompt(
                prompt_template,
                {
                    "TOPIC": topic,
                    "LEVEL": difficulty_level,
                    "USER_QUERY": f"""
Based on our conversation so far about {topic}, ask a follow-up question that builds on what we've discussed, introduces a related concept, encourages connections between ideas, requires critical thinking, and is appropriate for a {student_level} student.

Make your question conversational and engaging, as if you're genuinely curious about their thoughts. Write directly to the student.
"""
                }
            )
            
        elif chat_stage == 'metacognitive_reflection':
            formatted_prompt = LLMHandler.format_prompt(
                prompt_template,
                {
                    "TOPIC": topic,
                    "LEVEL": difficulty_level,
                    "USER_QUERY": f"""
Guide the student in a metacognitive reflection on their learning about {topic}. 

Ask thought-provoking questions like:
- What concepts about {topic} make sense to you now that didn't before?
- What strategies helped you understand difficult parts of {topic}?
- What connections can you make between {topic} and other things you know?
- What questions do you still have about {topic}?

Your response should encourage the student to think about their own learning process, while being appropriate for a {student_level} student. The goal is to help them develop awareness of how they learn best.

Write directly to the student in a warm, supportive tone.
"""
                }
            )
            
        elif chat_stage == 'real_world_application':
            formatted_prompt = LLMHandler.format_prompt(
                prompt_template,
                {
                    "TOPIC": topic,
                    "LEVEL": difficulty_level,
                    "USER_QUERY": f"""
Present a real-world scenario or problem where the student can apply what they've learned about {topic}.

Your scenario should:
- Be relevant and interesting to a {student_level} student
- Clearly connect to the key concepts we've discussed about {topic}
- Be presented as a challenge that invites creative problem-solving
- Include enough detail to be engaging without being overwhelming
- Provide a meaningful context that shows why this knowledge matters

Ask the student how they would approach solving this problem or analyzing this scenario using what they've learned.

Write directly to the student in an engaging, conversational tone.
"""
                }
            )
            
        elif chat_stage == 'summary':
            formatted_prompt = LLMHandler.format_prompt(
                prompt_template,
                {
                    "TOPIC": topic,
                    "LEVEL": difficulty_level,
                    "USER_QUERY": f"""
Provide a concise summary of our discussion about {topic} that is appropriate for a {student_level} student. Include key concepts covered, important insights made, areas for further exploration, and a brief preview of related topics.

Keep this summary encouraging and highlight the progress made. Write directly to the student in a conversational tone.
"""
                }
            )
            
        else:
            # General chat about the topic - conversational teaching style
            formatted_prompt = LLMHandler.format_prompt(
                prompt_template,
                {
                    "TOPIC": topic,
                    "LEVEL": difficulty_level,
                    "USER_QUERY": f"""
Student message: "{user_message}"

Respond as a knowledgeable and encouraging {subject} teacher speaking to a {student_level} student. If the student asks a question, provide a clear explanation that addresses their specific question using age-appropriate language and concepts, provides helpful context and examples, and encourages critical thinking.

Write directly to the student in a conversational tone. Do NOT include teaching instructions or steps in your response.
"""
                }
            )
        
        # Include condensed conversation history if available
        if conversation_history:
            # Limit history to prevent token overflow
            limited_history = conversation_history[-5:] if len(conversation_history) > 5 else conversation_history
            history_text = "\n\n".join([f"{'Teacher' if i%2==0 else 'Student'}: {msg}" for i, msg in enumerate(limited_history)])
            formatted_prompt = f"Previous conversation:\n{history_text}\n\n{formatted_prompt}"
        
        # Generate the LLM response
        llm_response = llm.generate_response(
            prompt=formatted_prompt,
            system_prompt=system_prompt,
            model=model
        )
        
        # Clean the response to ensure it doesn't contain teaching instructions
        llm_response = clean_teacher_instructions(llm_response)
        
        # Record interaction in database
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO interactions 
                    (user_id, topic, question, answer, is_correct, response_time, model_used)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    user_id,
                    topic,
                    user_message[:500],  # Limit length to prevent DB issues
                    llm_response[:500],   # Limit length to prevent DB issues
                    True,                 # Default to True for chat interactions
                    data.get('response_time', 0),
                    model
                ))
                conn.commit()
        except Exception as db_error:
            logger.error(f"Failed to record interaction: {str(db_error)}")
        
        # Enhanced detection for whether the response includes a follow-up question
        has_followup = any(phrase in llm_response.lower() for phrase in [
            "what do you think", "can you explain", "why do you", "how would you",
            "do you know", "can you describe", "?", "what is", "tell me about",
            "have you considered", "what might happen if", "how does", "could you share",
            "what's your understanding of", "why might", "what factors", "how can we"
        ])
        quiz_delay = 5000  # 5 seconds default delay in milliseconds
        
        return jsonify({
            'response': llm_response,
            'stage': chat_stage,
            'has_followup': has_followup,
            'difficulty': difficulty_level,
            'subject': subject,
            'quiz_delay': quiz_delay  # Add this parameter
        })
        
    except Exception as e:
        logger.error(f"Chat error: {str(e)}")
        return jsonify({
            'error': f"An error occurred while processing your request: {str(e)}"
        }), 500


def clean_teacher_instructions(text):
    """Remove any teaching instructions or step markers from response"""
    # More comprehensive list of patterns to clean
    instruction_markers = [
        "Step 1:", "Step 2:", "Step 3:", "Step 4:", "Step 5:",
        "Remember, the goal is to", 
        "== this type of response",
        "should not be seen to student",
        "Teaching approach:",
        "Note to self:",
        "Socratic approach:",
        "For this response:",
        "Remember as a teacher:",
        "[Teacher guidance:",
        "Teaching instructions:",
        "Teaching note:",
        "(Not for student to see)",
        "Student level:",
        "Teacher's thoughts:",
        "Teaching strategy:",
        "Pedagogical approach:",
        "Instructional note:",
        "This is how I'll respond:"
    ]
    
    # Remove lines that contain instruction markers
    lines = text.split('\n')
    cleaned_lines = []
    skip_section = False
    
    for line in lines:
        # Check if line starts a section to skip
        if any(line.strip().startswith(marker) for marker in ["Teaching notes:", "Instructor notes:", "NOTE:", "TEACHER NOTE:", "# Teaching"]):
            skip_section = True
            continue
        
        # Check if we're back to normal content
        if skip_section and line.strip() == "":
            skip_section = False
            continue
        
        # Skip lines in the skip section or containing instruction markers
        if not skip_section and not any(marker in line for marker in instruction_markers):
            # Filter out lines that start with "Step "
            if not re.match(r'^\s*Step\s+\d+\s*:.*', line.strip()):
                cleaned_lines.append(line)
    
    cleaned_text = '\n'.join(cleaned_lines)
    
    # Additional regex to remove more instruction patterns
    patterns_to_remove = [
        r'<teacher instructions>.*?</teacher instructions>',
        r'\[Teacher:.*?\]',
        r'\(Teacher note:.*?\)',
        r'\*\*Teaching notes\*\*:.*?(?=\n\n|\Z)',
        r'As an educator.*?(?=\n\n|\Z)',  # Remove educator self-references
        r'My approach.*?(?=\n\n|\Z)',     # Remove approach descriptions
        r'I\'ll use.*?(?=\n\n|\Z)',       # Remove method descriptions
        r'I should.*?(?=\n\n|\Z)',        # Remove self-instructions
    ]
    
    for pattern in patterns_to_remove:
        cleaned_text = re.sub(pattern, '', cleaned_text, flags=re.DOTALL)
    
    # Remove any leading or trailing whitespace from the final result
    cleaned_text = cleaned_text.strip()
    
    # Ensure text isn't empty after cleaning
    if not cleaned_text:
        return "I'm ready to help you learn more about this topic. What would you like to discuss?"
        
    return cleaned_text


@app.route('/api/feedback', methods=['POST'])
def handle_feedback():
    """Endpoint to collect student feedback on the tutoring experience"""
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    try:
        data = request.json
        user_id = session['user_id']
        interaction_id = data.get('interaction_id')
        helpful_rating = data.get('helpful_rating')  # 1-5 scale
        clarity_rating = data.get('clarity_rating')  # 1-5 scale
        engagement_rating = data.get('engagement_rating')  # 1-5 scale
        comments = data.get('comments', '').strip()
        
        if not interaction_id or not helpful_rating or not clarity_rating or not engagement_rating:
            return jsonify({'error': 'Missing required feedback fields'}), 400
        
        # Store feedback in database
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO feedback
                (user_id, interaction_id, helpful_rating, clarity_rating, engagement_rating, comments)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                user_id,
                interaction_id,
                helpful_rating,
                clarity_rating,
                engagement_rating,
                comments
            ))
            conn.commit()
        
        # Use feedback to adjust teaching approach for this student
        if helpful_rating < 3 or clarity_rating < 3:
            # If ratings are low, adjust student preferences to simplify explanations
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE user_preferences
                    SET preferred_explanation_style = 'simplified'
                    WHERE user_id = ?
                ''', (user_id,))
                conn.commit()
        
        return jsonify({'success': True, 'message': 'Feedback recorded successfully'})
        
    except Exception as e:
        logger.error(f"Feedback error: {str(e)}")
        return jsonify({
            'error': f"An error occurred while processing your feedback: {str(e)}"
        }), 500

@app.route('/api/rapid_quiz', methods=['POST'])
def rapid_quiz():
    if not llm.server_available:
        return jsonify({'error': 'Ollama server is not available.'}), 503
    try:
        data = request.get_json() or {}
        topic = data.get('topic', '').lower()
        subject = data.get('subject', 'gk').lower()
        
        # Validate subject is in the configuration
        if subject not in CONFIG['SUBJECT_MODELS']:
            logger.warning(f"Subject '{subject}' not in configured subjects, using 'gk' instead")
            subject = 'gk'
            
        # Get the appropriate model and prompt template
        model = CONFIG['SUBJECT_MODELS'][subject]
        prompt_template = PROMPT_TEMPLATES.get(subject)
        
        # Modified prompt for more reliable JSON generation
        formatted_prompt = LLMHandler.format_prompt(
            prompt_template,
            {
                "TOPIC": topic,
                "LEVEL": "beginner",
                "USER_QUERY": f"""
Generate a single multiple choice question for quick assessment.
Return ONLY valid JSON as follows:
{{
  "question": "Write a clear, specific question about {topic} in {subject}",
  "options": ["option1", "option2", "option3", "option4"],
  "correct_answer": "exact match of the correct option"
}}

Requirements:
- Question must be specifically about {topic} in the context of {subject}
- Very easy difficulty level
- Clear, concise question with exactly 4 options
- The correct_answer must exactly match one of the options

DO NOT include any explanations, descriptions or text outside the JSON.
"""
            }
        )
        
        system_prompt = f"""You are generating educational quiz questions about {subject}.
Your job is to ONLY return valid JSON in the exact specified format with no additional text.
Ensure the correct_answer exactly matches one of the option values."""
        
        response = llm.generate_response(
            prompt=formatted_prompt,
            system_prompt=system_prompt,
            model=model
        )
        
        # Extract JSON from the response
        json_match = re.search(r'\{.*\}', response, re.DOTALL)
        if json_match:
            response = json_match.group()
        
        try:
            question_data = json.loads(response)
            
            # Validation checks
            if not isinstance(question_data, dict):
                raise ValueError("Response is not a valid JSON object")
                
            required_keys = ['question', 'options', 'correct_answer']
            for key in required_keys:
                if key not in question_data:
                    raise ValueError(f"Missing required key: {key}")
            
            if not isinstance(question_data.get('options'), list):
                question_data['options'] = [str(x) for x in range(1, 5)]
            
            if len(question_data['options']) != 4:
                while len(question_data['options']) < 4:
                    question_data['options'].append(f"Option {len(question_data['options']) + 1}")
                question_data['options'] = question_data['options'][:4]
            
            if question_data.get('correct_answer') not in question_data['options']:
                question_data['correct_answer'] = question_data['options'][0]
            
            return jsonify({
                'question': question_data.get('question', f'What is a key concept about {topic} in {subject}?'),
                'options': question_data['options'],
                'correct': question_data['correct_answer'],
                'topic': topic,
                'subject': subject
            })
            
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Invalid JSON response: {response}, Error: {str(e)}")
            # Provide a better subject-specific fallback question
            fallback_questions = {
                'math': {
                    'question': f"Which of these best describes {topic} in mathematics?",
                    'options': ["A mathematical concept", "A random guess", "Not related to math", "None of these"],
                    'correct': "A mathematical concept"
                },
                'science': {
                    'question': f"What is {topic} in science?",
                    'options': ["A scientific concept", "Not scientific", "Unrelated", "None of these"],
                    'correct': "A scientific concept"
                },
                'history': {
                    'question': f"Which best describes {topic} in history?",
                    'options': ["A historical event", "A fictional story", "Not related to history", "None of these"],
                    'correct': "A historical event"
                },
                'english': {
                    'question': f"Which best describes {topic} in English?",
                    'options': ["A language concept", "Not related to English", "A random phrase", "None of these"],
                    'correct': "A language concept"
                }
            }
            return jsonify(fallback_questions.get(subject, {
                'question': f"What is {topic}?",
                'options': ["A concept in " + subject, "Not related to " + subject, "A random term", "None of these"],
                'correct': "A concept in " + subject,
                'topic': topic,
                'subject': subject
            }))
            
    except Exception as e:
        logger.error(f"Rapid quiz error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/save_rapid_quiz', methods=['POST'])
def save_rapid_quiz():
    """Save the results of a rapid quiz to the database."""
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'status': 'error', 'message': 'User not authenticated'}), 401
            
        data = request.get_json()
        if not data:
            return jsonify({'status': 'error', 'message': 'No data provided'}), 400
            
        topic = data.get('topic')
        question = data.get('question')
        user_answer = data.get('user_answer')
        correct_answer = data.get('correct_answer')
        is_correct = data.get('is_correct', False)
        response_time = data.get('response_time', 0)
        
        if not all([topic, question, correct_answer]):
            return jsonify({'status': 'error', 'message': 'Missing required data'}), 400
            
        try:
            with get_db_connection() as conn:
                # Save to rapid quiz responses
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO rapid_quiz_responses
                    (user_id, topic, question, user_answer, correct_answer, is_correct, response_time, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ''', (
                    user_id, topic, question, user_answer, correct_answer, is_correct, response_time
                ))
                
                # Update user progress
                cursor.execute('''
                    SELECT id FROM user_progress 
                    WHERE user_id = ? AND topic = ?
                ''', (user_id, topic))
                progress = cursor.fetchone()
                
                if progress:
                    cursor.execute('''
                        UPDATE user_progress
                        SET correct_count = correct_count + ?,
                            incorrect_count = incorrect_count + ?,
                            avg_response_time = (avg_response_time + ?) / 2
                        WHERE user_id = ? AND topic = ?
                    ''', (
                        1 if is_correct else 0,
                        0 if is_correct else 1,
                        response_time,
                        user_id,
                        topic
                    ))
                else:
                    cursor.execute('''
                        INSERT INTO user_progress
                        (user_id, topic, correct_count, incorrect_count, avg_response_time)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (
                        user_id,
                        topic,
                        1 if is_correct else 0,
                        0 if is_correct else 1,
                        response_time
                    ))
                conn.commit()
                
            return jsonify({
                'status': 'success',
                'message': 'Rapid quiz result saved successfully'
            })
        except sqlite3.Error as e:
            logger.error(f"Database error saving rapid quiz: {str(e)}")
            return jsonify({'status': 'error', 'message': f'Database error: {str(e)}'}), 500
        
    except Exception as e:
        logger.error(f"Error saving rapid quiz result: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/heartbeat')
def heartbeat():
    """API endpoint to check if the server is running."""
    return jsonify({
        'status': 'ok',
        'timestamp': datetime.now().isoformat(),
        'server': 'EduChat API',
        'ollama_available': llm.server_available
    })

@app.route('/api/generate_test', methods=['POST'])
def generate_test():
    if not llm.server_available:
        return jsonify({"error": "Ollama server is not available. Test generation cannot proceed."}), 503
    try:
        if not request.is_json:
            return jsonify({"error": "Request must be JSON"}), 400
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400
        subject = data.get('subject', '').strip().lower()
        topic = data.get('topic', '').strip()
        question_count = data.get('count', 5)
        if not subject:
            return jsonify({"error": "Subject is required"}), 400
        if subject not in CONFIG['SUBJECT_MODELS']:
            valid_subjects = ', '.join(CONFIG['SUBJECT_MODELS'].keys())
            return jsonify({"error": f"Invalid subject: '{subject}'. Valid subjects are: {valid_subjects}"}), 400
        if not topic:
            return jsonify({"error": "Topic is required"}), 400
        if not isinstance(question_count, int) or question_count <= 0:
            return jsonify({"error": "Count must be a positive integer"}), 400
        model = CONFIG['SUBJECT_MODELS'].get(subject)
        prompt_template = PROMPT_TEMPLATES.get(subject)
        if not prompt_template:
            logger.error(f"No prompt template found for subject: {subject}")
            return jsonify({"error": "Configuration error"}), 500
        formatted_prompt = LLMHandler.format_prompt(
            prompt_template,
            {
                "TOPIC": topic,
                "LEVEL": "intermediate",
                "USER_QUERY": f"""
Generate {question_count} multiple choice questions about {topic} in the context of {subject}.
Each question should include:
- A clear and concise question
- Exactly 4 options (one correct)
- An explanation for the correct answer
Return the result as a JSON array with this structure:
[
  {{
    "question": "Question text",
    "options": ["Option 1", "Option 2", "Option 3", "Option 4"],
    "correct_answer": "Option X",
    "explanation": "Explanation text"
  }},
  ...
]
"""
            }
        )
        
        response = llm.generate_response(
            prompt=formatted_prompt,
            system_prompt="You are creating educational content. Provide only the JSON response.",
            model=model
        )
        logger.debug(f"Raw LLM response for subject '{subject}', topic '{topic}': {response}")
        
        # Improved JSON extraction with better error handling
        try:
            # First try direct JSON parsing
            try:
                questions_data = json.loads(response)
                if not isinstance(questions_data, list):
                    # If response is a JSON object but not a list, see if it has 'questions' key
                    if isinstance(questions_data, dict) and 'questions' in questions_data:
                        questions_data = questions_data['questions']
                    else:
                        raise ValueError("Response is not a JSON array or doesn't contain questions")
            except json.JSONDecodeError:
                # Try to extract JSON array from text/markdown
                cleaned_response = re.sub(r"```json|```", "", response, flags=re.MULTILINE).strip()
                json_match = re.search(r'\[.*\]', cleaned_response, re.DOTALL)
                if json_match:
                    json_str = json_match.group()
                    questions_data = json.loads(json_str)
                else:
                    # If no array found, try to see if there's a JSON object with a questions array
                    object_match = re.search(r'\{.*\}', cleaned_response, re.DOTALL)
                    if object_match:
                        json_obj = json.loads(object_match.group())
                        if isinstance(json_obj, dict) and 'questions' in json_obj:
                            questions_data = json_obj['questions']
                        else:
                            raise ValueError("No questions array found in JSON object")
                    else:
                        raise ValueError("No valid JSON found in the response")
            
            # Validate the questions data
            if not isinstance(questions_data, list):
                raise ValueError(f"Expected a list of questions, got {type(questions_data)}")
            
            if len(questions_data) == 0:
                raise ValueError("No questions were generated")
                
            # Validate each question
            for i, q in enumerate(questions_data):
                if not isinstance(q, dict):
                    logger.warning(f"Question {i} is not a dictionary: {q}")
                    continue
                    
                # Check for required fields
                required_keys = ['question', 'options', 'correct_answer', 'explanation']
                missing_keys = [key for key in required_keys if key not in q]
                if missing_keys:
                    logger.warning(f"Question {i} missing keys: {missing_keys}")
                    # Add missing keys with placeholder values
                    for key in missing_keys:
                        if key == 'options':
                            q[key] = ["Option A", "Option B", "Option C", "Option D"]
                        elif key == 'correct_answer':
                            q[key] = "Option A"
                        else:
                            q[key] = f"Missing {key}"
                
                # Ensure options is a list
                if 'options' in q and not isinstance(q['options'], list):
                    logger.warning(f"Question {i} options is not a list: {q['options']}")
                    q['options'] = [str(q['options'])]
                
                # Ensure exactly 4 options
                if 'options' in q:
                    while len(q['options']) < 4:
                        q['options'].append(f"Option {len(q['options']) + 1}")
                    if len(q['options']) > 4:
                        logger.warning(f"Question {i} has {len(q['options'])} options, truncating to 4")
                        q['options'] = q['options'][:4]
                
                # Ensure correct_answer is one of the options
                if 'correct_answer' in q and 'options' in q and q['correct_answer'] not in q['options']:
                    logger.warning(f"Question {i} correct answer '{q['correct_answer']}' not in options")
                    q['correct_answer'] = q['options'][0]
            
            return jsonify(questions_data)
            
        except Exception as e:
            logger.error(f"Failed to parse questions data: {str(e)}")
            # Provide fallback questions
            fallback_questions = [{
                "question": f"What is an important concept in {topic}?",
                "options": ["Concept A", "Concept B", "Concept C", "Concept D"],
                "correct_answer": "Concept A",
                "explanation": f"This is a fallback question. The AI response could not be parsed: {str(e)}"
            }]
            return jsonify(fallback_questions)
            
    except Exception as e:
        logger.error(f"Error in generate_test: {str(e)}")
        return jsonify({"error": f"Failed to generate test: {str(e)}"}), 500

@app.route('/api/get_analytics')
def get_analytics():
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    user_id = session['user_id']
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Get all subjects first
            subjects = list(CONFIG['SUBJECT_MODELS'].keys())
            
            # Get progress data with default values for subjects with no data
            progress_data = []
            for subject in subjects:
                cursor.execute("""
                    SELECT topic, correct_count, incorrect_count, avg_response_time 
                    FROM user_progress 
                    WHERE user_id = ? AND topic = ?
                """, (user_id, subject))
                row = cursor.fetchone()
                if row:
                    progress_data.append(dict(row))
                else:
                    # Add default entry for subjects with no data
                    progress_data.append({
                        'topic': subject,
                        'correct_count': 0,
                        'incorrect_count': 0,
                        'avg_response_time': 0
                    })

            # Get recent activities including both rapid quiz and regular interactions
            cursor.execute("""
                SELECT 
                    'rapid_quiz' as activity_type,
                    topic,
                    question,
                    user_answer,
                    correct_answer,
                    is_correct,
                    response_time,
                    timestamp
                FROM rapid_quiz_responses 
                WHERE user_id = ?
                UNION ALL
                SELECT 
                    'interaction' as activity_type,
                    topic,
                    question,
                    answer as user_answer,
                    '' as correct_answer,
                    is_correct,
                    response_time,
                    timestamp
                FROM interactions
                WHERE user_id = ?
                ORDER BY timestamp DESC
                LIMIT 10
            """, (user_id, user_id))
            recent_activities = [dict(row) for row in cursor.fetchall()]

            return jsonify({
                'progress': progress_data,
                'recent_activities': recent_activities,
                'subjects': subjects
            })
    except Exception as e:
        logger.error(f"Analytics error: {str(e)}")
        return jsonify({
            'progress': [],
            'recent_activities': [],
            'subjects': list(CONFIG['SUBJECT_MODELS'].keys()),
            'message': 'Start a learning session to see your progress!'
        })

@app.route('/api/summarize', methods=['POST'])
def summarize_text():
    try:
        data = request.get_json()
        text = data.get('text', '')
        max_length = data.get('length', 50)
        summary = summarizer.summarize(text, max_length)
        return jsonify({'summary': summary})
    except Exception as e:
        logger.error(f"Summarization error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/recent-activity')
def recent_activity():
    return render_template('recent_activity.html')

@app.route('/text-summarizer')
def text_summarizer():
    return render_template('text_summarizer.html')

@app.route('/youtube-extractor')
def youtube_extractor():
    return render_template('youtube_extractor.html')

@app.errorhandler(404)
def page_not_found(e):
    return render_template('errors/404.html'), 404

@app.errorhandler(500)
def internal_error(e):
    return render_template('errors/500.html'), 500

class SlideExtractor:
    def __init__(self, video_url, output_dir="static/slides", interval=5, similarity_threshold=0.9, ocr_confidence=30):
        self.video_url = video_url
        self.output_dir = output_dir
        self.interval = interval
        self.similarity_threshold = similarity_threshold
        self.ocr_confidence = ocr_confidence
        self.video_path = os.path.join(self.output_dir, "temp_video.mp4")
        self.previous_text = ""

        os.makedirs(self.output_dir, exist_ok=True)

    def download_video(self):
        """Download the YouTube video using yt-dlp"""
        try:
            command = [
                "yt-dlp",
                "-f", "best[ext=mp4]",
                "-o", self.video_path,
                self.video_url
            ]
            result = subprocess.run(command, capture_output=True, text=True)

            if result.returncode == 0:
                print(f"Video downloaded to: {self.video_path}")
                return True
            else:
                print(f"yt-dlp error:\n{result.stderr}")
                return False
        except Exception as e:
            print(f"Error downloading video: {e}")
            return False

    def extract_slides(self):
        """Process the video to extract slides"""
        if not os.path.exists(self.video_path):
            if not self.download_video():
                return False

        cap = cv2.VideoCapture(self.video_path)
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_interval = int(fps * self.interval)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = total_frames / fps

        print(f"Video duration: {timedelta(seconds=duration)}")
        print(f"Processing frames every {self.interval} seconds...")

        prev_frame = None
        slide_count = 0

        for frame_num in range(0, total_frames, frame_interval):
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_num)
            ret, frame = cap.read()

            if not ret:
                continue

            current_time = frame_num / fps
            timestamp = str(timedelta(seconds=current_time)).split(".")[0]

            if prev_frame is None:
                self._save_slide(frame, timestamp, slide_count)
                prev_frame = frame
                slide_count += 1
                continue

            if self._is_different_slide(prev_frame, frame):
                self._save_slide(frame, timestamp, slide_count)
                prev_frame = frame
                slide_count += 1

        cap.release()
        print(f"Extracted {slide_count} slides to {self.output_dir}")
        return True

    def _is_different_slide(self, frame1, frame2):
        gray1 = cv2.cvtColor(frame1, cv2.COLOR_BGR2GRAY)
        gray2 = cv2.cvtColor(frame2, cv2.COLOR_BGR2GRAY)

        similarity, _ = ssim(gray1, gray2, full=True)
        if similarity < self.similarity_threshold:
            return True

        text1 = self._extract_text(frame1)
        text2 = self._extract_text(frame2)

        if text1 and text2:
            words1 = set(text1.split())
            words2 = set(text2.split())
            common_words = words1.intersection(words2)
            diff_ratio = 1 - len(common_words) / max(len(words1), len(words2))

            if diff_ratio > 0.3:
                return True

        return False

    def _extract_text(self, frame):
        try:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            _, threshold = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY)

            temp_image_path = os.path.join(self.output_dir, "temp_ocr.png")
            cv2.imwrite(temp_image_path, threshold)

            text = pytesseract.image_to_string(Image.open(temp_image_path), config='--psm 6')
            return text.strip()
        except Exception as e:
            print(f"OCR error: {e}")
            return ""

    def _save_slide(self, frame, timestamp, count):
        filename = f"slide_{count:03d}_{timestamp.replace(':', '-')}.png"
        path = os.path.join(self.output_dir, filename)
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        pil_image = Image.fromarray(rgb_frame)
        pil_image.save(path)
        print(f"Saved slide: {filename}")

    def convert_slides_to_pdf(self, pdf_name="slides_output.pdf"):
        """Convert all extracted slides to a single PDF file."""
        image_files = sorted([
            os.path.join(self.output_dir, file)
            for file in os.listdir(self.output_dir)
            if file.lower().endswith(".png") and file.startswith("slide_")
        ])

        if not image_files:
            print("No slide images found to convert.")
            return

        images = [Image.open(img).convert("RGB") for img in image_files]
        pdf_path = os.path.join(self.output_dir, pdf_name)
        images[0].save(pdf_path, save_all=True, append_images=images[1:])
        print(f"PDF created at: {pdf_path}")
        return pdf_path

@app.route('/api/extract_slides', methods=['POST'])
def extract_slides():
    """API endpoint to extract slides from a YouTube video"""
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401

    try:
        data = request.get_json()
        video_url = data.get('video_url')
        interval = data.get('interval', 5)
        threshold = data.get('threshold', 0.9)

        if not video_url:
            return jsonify({'error': 'Video URL is required'}), 400

        # Create output directory for this user
        user_output_dir = os.path.join('static', 'slides', str(session['user_id']))
        os.makedirs(user_output_dir, exist_ok=True)

        # Initialize and run the slide extractor
        extractor = SlideExtractor(
            video_url=video_url,
            output_dir=user_output_dir,
            interval=interval,
            similarity_threshold=threshold
        )

        if extractor.extract_slides():
            return jsonify({
                'success': True,
                'message': 'Slides extracted successfully',
                'output_dir': user_output_dir
            })
        else:
            return jsonify({'error': 'Failed to extract slides'}), 500

    except Exception as e:
        logger.error(f"Slide extraction error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/generate_slides_pdf', methods=['POST'])
def generate_slides_pdf():
    """API endpoint to generate a PDF from extracted slides"""
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401

    try:
        user_output_dir = os.path.join('static', 'slides', str(session['user_id']))
        
        if not os.path.exists(user_output_dir):
            return jsonify({'error': 'No slides found'}), 404

        extractor = SlideExtractor(output_dir=user_output_dir)
        pdf_path = extractor.convert_slides_to_pdf()

        if pdf_path and os.path.exists(pdf_path):
            return jsonify({
                'success': True,
                'message': 'PDF generated successfully',
                'pdf_url': url_for('static', filename=f'slides/{session["user_id"]}/slides_output.pdf')
            })
        else:
            return jsonify({'error': 'Failed to generate PDF'}), 500

    except Exception as e:
        logger.error(f"PDF generation error: {str(e)}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    os.makedirs('templates/auth', exist_ok=True)
    os.makedirs('templates/errors', exist_ok=True)
    os.makedirs('static/css', exist_ok=True)
    os.makedirs('static/js', exist_ok=True)
    app.run(host='0.0.0.0', port=5000, debug=True)