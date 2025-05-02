from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import declarative_base
from pydantic import BaseModel, EmailStr, ConfigDict

Base = declarative_base()

# SQLAlchemy model (database)
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    name = Column(String, nullable=False)
    age = Column(Integer, nullable=True)
    subject_preferences = Column(String, nullable=True)

# Pydantic models (API schemas)
class UserCreate(BaseModel):
    email: EmailStr
    password: str
    name: str
    age: int | None = None
    subject_preferences: str | None = None

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserProfile(BaseModel):
    id: int
    email: EmailStr
    name: str
    age: int | None = None
    subject_preferences: str | None = None

    # Pydantic v2 syntax (correct)
    model_config = ConfigDict(from_attributes=True)

