from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    phone = Column(String, unique=True, index=True)
    telegram_id = Column(String, unique=True, index=True)
    full_name = Column(String)
    interests = Column(Text)  # JSON строка с интересами
    study_direction = Column(String)
    hashed_password = Column(String)
    is_active = Column(Boolean, default=True)
    is_manager = Column(Boolean, default=False)
    is_admin = Column(Boolean, default=False)
    points_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Связи
    game_results = relationship("GameResult", back_populates="user")
    rewards = relationship("RewardClaim", back_populates="user")

class Game(Base):
    __tablename__ = "games"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    description = Column(Text)
    game_type = Column(String)  # 'truth_or_lie', 'mem_vs_situation', etc.
    is_active = Column(Boolean, default=True)
    points_reward = Column(Integer, default=0)
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Связи
    questions = relationship("GameQuestion", back_populates="game")
    results = relationship("GameResult", back_populates="game")

class GameQuestion(Base):
    __tablename__ = "game_questions"

    id = Column(Integer, primary_key=True, index=True)
    game_id = Column(Integer, ForeignKey("games.id"))
    question_text = Column(Text)
    question_type = Column(String)  # 'truth_lie', 'multiple_choice', etc.
    options = Column(Text)  # JSON строка с вариантами ответов
    correct_answer = Column(String)
    explanation = Column(Text)
    order_index = Column(Integer, default=0)

    # Связи
    game = relationship("Game", back_populates="questions")

class GameResult(Base):
    __tablename__ = "game_results"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    game_id = Column(Integer, ForeignKey("games.id"))
    score = Column(Integer)
    total_points = Column(Integer)
    completed_at = Column(DateTime(timezone=True), server_default=func.now())

    # Связи
    user = relationship("User", back_populates="game_results")
    game = relationship("Game", back_populates="results")

class Reward(Base):
    __tablename__ = "rewards"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    description = Column(Text)
    points_required = Column(Integer)
    image_url = Column(String)
    is_available = Column(Boolean, default=True)
    stock_quantity = Column(Integer)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class RewardClaim(Base):
    __tablename__ = "reward_claims"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    reward_id = Column(Integer, ForeignKey("rewards.id"))
    claimed_at = Column(DateTime(timezone=True), server_default=func.now())
    status = Column(String, default="pending")  # pending, approved, rejected

    # Связи
    user = relationship("User", back_populates="rewards")
    reward = relationship("Reward")

class Internship(Base):
    __tablename__ = "internships"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    description = Column(Text)
    requirements = Column(Text)
    duration = Column(String)
    location = Column(String)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())