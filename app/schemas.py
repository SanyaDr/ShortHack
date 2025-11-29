from pydantic import BaseModel, EmailStr
from datetime import datetime
from typing import Optional, List, Dict, Any

# User Schemas
class UserBase(BaseModel):
    email: EmailStr
    phone: str
    telegram_id: str
    full_name: str
    interests: Optional[str] = None
    study_direction: Optional[str] = None

class UserCreate(UserBase):
    password: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class User(UserBase):
    id: int
    is_active: bool
    is_manager: bool
    is_admin: bool
    total_points: Optional[int] = 0
    created_at: datetime

    class Config:
        from_attributes = True

# Game Schemas
class GameQuestionBase(BaseModel):
    question_text: str
    question_type: str
    options: Optional[Dict[str, Any]] = None
    correct_answer: str
    explanation: Optional[str] = None
    order_index: int = 0

class GameQuestionCreate(GameQuestionBase):
    pass

class GameQuestion(GameQuestionBase):
    id: int
    game_id: int

    class Config:
        from_attributes = True

class GameBase(BaseModel):
    title: str
    description: str
    game_type: str
    points_reward: int = 0

class GameCreate(GameBase):
    questions: List[GameQuestionCreate]

class Game(GameBase):
    id: int
    is_active: bool
    created_by: int
    created_at: datetime
    questions: List[GameQuestion] = []

    class Config:
        from_attributes = True

# Reward Schemas
class RewardBase(BaseModel):
    name: str
    description: str
    points_required: int
    image_url: Optional[str] = None
    stock_quantity: int

class RewardCreate(RewardBase):
    pass

class Reward(RewardBase):
    id: int
    is_available: bool
    created_at: datetime

    class Config:
        from_attributes = True

# Internship Schemas
class InternshipBase(BaseModel):
    title: str
    description: str
    requirements: str
    duration: str
    location: str

class InternshipCreate(InternshipBase):
    pass

class Internship(InternshipBase):
    id: int
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True

# Response Schemas
class LeaderboardUser(BaseModel):
    rank: int
    user_id: int
    full_name: str
    total_points: int
    games_played: int

class GameSubmission(BaseModel):
    answers: Dict[str, str]  # question_id -> answer