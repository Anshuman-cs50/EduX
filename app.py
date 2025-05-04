import os
import re
import logging
import time
from datetime import datetime
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.exceptions import HTTPException
import random
from modules.llm_handler import LLMHandler
import json
from markupsafe import escape
import requests
from pymongo import MongoClient
from bson.objectid import ObjectId

# Initialize LLM handler
llm = LLMHandler()

# Ensure necessary directories exist
os.makedirs('logs', exist_ok=True)
os.makedirs('database', exist_ok=True)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('logs/app.log')
    ]
)
logger = logging.getLogger(__name__)

CONFIG = {
    'MONGO_URI': 'mongodb://localhost:27017/',
    'DATABASE_NAME': 'edu_chat',
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

PROMPT_TEMPLATES = load_prompt_templates()

def format_prompt_with_values(topic, level, user_query):
    prompt_template = PROMPT_TEMPLATES.get(topic, PROMPT_TEMPLATES['math'])
    return LLMHandler.format_prompt(
        prompt_template,
        {
            "TOPIC": topic,
            "LEVEL": level,
            "USER_QUERY": user_query
        }
    )

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', os.urandom(24).hex())

# MongoDB Setup
mongo_client = MongoClient(CONFIG['MONGO_URI'])
db = mongo_client[CONFIG['DATABASE_NAME']]

# Helper functions
def validate_email(email):
    return re.match(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$", email)

def validate_password(password):
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

        if db.users.find_one({"$or": [{"username": username}, {"email": email}]}):
            raise ValueError("Username or email already exists")

        password_hash = generate_password_hash(password)
        user_doc = {
            "username": username,
            "email": email,
            "password_hash": password_hash,
            "is_verified": not CONFIG['REQUIRE_EMAIL_VERIFICATION'],
            "created_at": datetime.utcnow(),
            "last_login": None,
            "reset_token": None,
            "reset_token_expiry": None
        }
        result = db.users.insert_one(user_doc)
        user_id = str(result.inserted_id)

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
        return jsonify({'success': False, 'error': str(e)}), 400

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

        user = db.users.find_one({"$or": [{"username": username_or_email}, {"email": username_or_email}]})
        if not user or not check_password_hash(user['password_hash'], password):
            raise ValueError("Invalid credentials")

        if CONFIG['REQUIRE_EMAIL_VERIFICATION'] and not user['is_verified']:
            raise ValueError("Please verify your email before logging in")

        db.users.update_one({"_id": user['_id']}, {"$set": {"last_login": datetime.utcnow()}})
        session['user_id'] = str(user['_id'])
        session['username'] = user['username']
        logger.info(f"User logged in: {user['username']}")

        return jsonify({
            'success': True,
            'message': 'Login successful',
            'redirect': url_for('dashboard')
        })
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 401

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
        user_id = session['user_id']
        progress_data = list(db.user_progress.find({"user_id": user_id}))
        return render_template('dashboard.html', progress_data=progress_data)
    except Exception as e:
        logger.error(f"Dashboard error: {str(e)}")
        return redirect(url_for('login'))

@app.route('/chatbot')
def chatbot():
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
