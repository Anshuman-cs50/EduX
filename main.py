# main.py
from fastapi import FastAPI, HTTPException, Depends, status, HTTPException
from sqlalchemy.orm import Session
from jose import JWTError, jwt
import auth
from pydantic import BaseModel
from typing import List, Optional
import httpx
import os
from db import engine
import model
from model import User, UserCreate, UserLogin, UserProfile
model.Base.metadata.create_all(bind=engine)

from db import get_db  # Import the function


# ========== CONFIG ==========

LLM_API_URL = "https://api-inference.huggingface.co/models/meta-llama/Llama-3-70b-chat-hf"
HUGGINGFACE_API_KEY = os.getenv("HUGGINGFACE_API_KEY", "")

# ========== FASTAPI APP ==========
app = FastAPI(
    title="AI-Enhanced Learning Platform",
    description="Deliberate practice, scaffolding, and mastery-based progression with AI feedback.",
    version="0.1.0"
)

# ========== DATA MODELS ==========

class Message(BaseModel):
    role: str  # "user" or "assistant"
    content: str

class ChatRequest(BaseModel):
    user_id: str
    subject: str
    topic: str
    messages: List[Message]
    attempts: int

class ChatResponse(BaseModel):
    reply: str
    system: str  # "system2_enforced", "scaffolding_hint", "llm_guided_hint", etc.

# ========== CORE CHAT ENDPOINT ==========

@app.post("/chat/", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    """
    Main chat endpoint for deliberate practice and AI feedback.
    Enforces effortful reasoning, scaffolding, and mastery logic.
    """
    user_message = request.messages[-1].content if request.messages else ""
    attempts = request.attempts

    # 1. Enforce effortful practice (System 2): Require reasoning before help
    if attempts < 2 and len(user_message) < 30:
        return ChatResponse(
            reply="Please explain your reasoning in detail before I can help. Try to break down your thought process step by step.",
            system="system2_enforced"
        )

    # 2. Provide scaffolding/hints after initial attempts
    if attempts < 3:
        return ChatResponse(
            reply="You're making progress! What principle or formula could apply here? Think aloud about your next step.",
            system="scaffolding_hint"
        )

    # 3. After multiple attempts, call LLM for a guided hint or answer
    prompt = build_llm_prompt(request)
    llm_reply = await call_llm(prompt)
    return ChatResponse(
        reply=llm_reply,
        system="llm_guided_hint"
    )

# ========== LLM INTEGRATION ==========

def build_llm_prompt(request: ChatRequest) -> str:
    """
    Builds a prompt for the LLM based on chat history, subject, and topic.
    """
    history = "\n".join([f"{m.role.capitalize()}: {m.content}" for m in request.messages])
    prompt = (
        f"You are a helpful study mentor for high-school students learning {request.subject} (topic: {request.topic}).\n"
        "Your job is to provide scaffolded hints, not just answers. If the student is struggling, give a step-by-step nudge.\n"
        "Here is the conversation so far:\n"
        f"{history}\n"
        "Respond with a hint or a worked step, not the full solution unless the student has made several attempts."
    )
    return prompt

async def call_llm(prompt: str) -> str:
    """
    Calls the Hugging Face Inference API (Llama 3) and returns the model's reply.
    """
    headers = {
        "Authorization": f"Bearer {HUGGINGFACE_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "inputs": prompt,
        "parameters": {"max_new_tokens": 150}
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(LLM_API_URL, headers=headers, json=payload, timeout=20)
        if response.status_code == 200:
            data = response.json()
            # Hugging Face returns a list of generated texts
            if isinstance(data, list) and data and "generated_text" in data[0]:
                return data[0]["generated_text"]
            elif "generated_text" in data:
                return data["generated_text"]
            elif "error" in data:
                return "Sorry, the AI service is temporarily unavailable. Try again later."
            else:
                return "Sorry, I couldn't generate a hint right now."
        else:
            return "Sorry, there was an error contacting the AI service."

# ========== HEALTH CHECK ==========
@app.post("/register", response_model=UserProfile)
def register(user: UserCreate, db: Session = Depends(get_db)):
    # 1. Check for existing user
    db_user = db.query(User).filter(User.email == user.email).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    # 2. Hash password
    hashed_pw = auth.hash_password(user.password)
    # 3. Create new user
    new_user = User(
        email=user.email,
        hashed_password=hashed_pw,
        name=user.name,
        age=user.age,
        subject_preferences=user.subject_preferences,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    # 4. Return profile (no password)
    return new_user


@app.post("/login")
def login(user: UserLogin, db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.email == user.email).first()
    if not db_user or not auth.verify_password(user.password, db_user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    # Generate JWT token
    token = auth.create_access_token({"sub": db_user.email})
    return {"access_token": token, "token_type": "bearer"}


def get_current_user(token: str = Depends(auth.oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, auth.SECRET_KEY, algorithms=[auth.ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    user = db.query(User).filter(User.email == email).first()
    if user is None:
        raise credentials_exception
    return user

@app.get("/profile", response_model=UserProfile)
def profile(current_user: User = Depends(get_current_user)):
    return current_user

@app.get("/")
def root():
    return {"message": "AI-Enhanced Learning Platform backend is running."}

import uvicorn

if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
