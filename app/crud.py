from sqlalchemy.orm import Session
from sqlalchemy import func, desc, select
from typing import List, Optional
import json

from . import models, schemas


# User CRUD operations
def get_user(db: Session, user_id: int):
    return db.query(models.User).filter(models.User.id == user_id).first()


def get_user_by_email(db: Session, email: str):
    return db.query(models.User).filter(models.User.email == email).first()


def get_user_by_phone(db: Session, phone: str):
    return db.query(models.User).filter(models.User.phone == phone).first()


def get_user_by_telegram(db: Session, telegram_id: str):
    return db.query(models.User).filter(models.User.telegram_id == telegram_id).first()


def get_users(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.User).offset(skip).limit(limit).all()


def create_user(db: Session, user: schemas.UserCreate):
    from .auth import get_password_hash

    hashed_password = get_password_hash(user.password)
    db_user = models.User(
        email=user.email,
        phone=user.phone,
        telegram_id=user.telegram_id,
        full_name=user.full_name,
        interests=user.interests,
        study_direction=user.study_direction,
        hashed_password=hashed_password
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


def update_user(db: Session, user_id: int, user_update: schemas.UserBase):
    db_user = get_user(db, user_id)
    if db_user:
        for field, value in user_update.dict().items():
            setattr(db_user, field, value)
        db.commit()
        db.refresh(db_user)
    return db_user


# Game CRUD operations
def get_game(db: Session, game_id: int):
    return db.query(models.Game).filter(models.Game.id == game_id).first()


def get_games(db: Session, skip: int = 0, limit: int = 100, active_only: bool = True):
    query = db.query(models.Game)
    if active_only:
        query = query.filter(models.Game.is_active == True)
    return query.offset(skip).limit(limit).all()


def create_game(db: Session, game: schemas.GameCreate, user_id: int):
    # Умножаем базовые баллы награды на 5
    points_reward = game.points_reward * 5

    db_game = models.Game(
        title=game.title,
        description=game.description,
        game_type=game.game_type,
        points_reward=points_reward,  # Уже умноженные баллы
        created_by=user_id
    )
    db.add(db_game)
    db.commit()
    db.refresh(db_game)

    # Create questions for the game
    for i, question_data in enumerate(game.questions):
        db_question = models.GameQuestion(
            game_id=db_game.id,
            question_text=question_data.question_text,
            question_type=question_data.question_type,
            options=json.dumps(question_data.options) if question_data.options else None,
            correct_answer=question_data.correct_answer,
            explanation=question_data.explanation,
            order_index=i
        )
        db.add(db_question)

    db.commit()
    db.refresh(db_game)
    return db_game


def get_game_questions(db: Session, game_id: int):
    return db.query(models.GameQuestion).filter(
        models.GameQuestion.game_id == game_id
    ).order_by(models.GameQuestion.order_index).all()


# Game Results CRUD operations
def get_user_game_results(db: Session, user_id: int, game_id: int):
    return db.query(models.GameResult).filter(
        models.GameResult.user_id == user_id,
        models.GameResult.game_id == game_id
    ).first()


def create_game_result(db: Session, user_id: int, game_id: int, score: int, total_points: int):
    db_result = models.GameResult(
        user_id=user_id,
        game_id=game_id,
        score=score,
        total_points=total_points  # Здесь уже будут баллы, умноженные на 5
    )
    db.add(db_result)
    db.commit()
    db.refresh(db_result)
    return db_result


def get_user_total_points(db: Session, user_id: int):
    result = db.query(func.sum(models.GameResult.total_points)).filter(
        models.GameResult.user_id == user_id
    ).scalar()
    return result or 0


def get_user_games_played(db: Session, user_id: int):
    return db.query(models.GameResult).filter(
        models.GameResult.user_id == user_id
    ).count()


# Game submission and scoring
def submit_game_answers(db: Session, game_id: int, user_id: int, answers: dict):
    game = get_game(db, game_id)
    if not game:
        return None

    questions = get_game_questions(db, game_id)
    if not questions:
        return None

    # Check if user already played this game
    existing_result = get_user_game_results(db, user_id, game_id)
    if existing_result:
        return existing_result

    # Calculate score
    correct_answers = 0
    for question in questions:
        user_answer = answers.get(str(question.id))
        if user_answer and user_answer == question.correct_answer:
            correct_answers += 1

    score_percentage = (correct_answers / len(questions)) * 100
    # Умножаем набранные баллы на 5
    points_earned = int((score_percentage / 100) * game.points_reward)

    # Save result
    return create_game_result(db, user_id, game_id, score_percentage, points_earned)


# Leaderboard operations
def get_leaderboard(db: Session, limit: int = 50):
    # Подзапрос для подсчета очков каждого пользователя
    points_subquery = (
        select(
            models.GameResult.user_id,
            func.sum(models.GameResult.total_points).label('total_points'),
            func.count(models.GameResult.id).label('games_played')
        )
        .group_by(models.GameResult.user_id)
        .subquery()
    )

    # Основной запрос с ранжированием
    leaderboard_data = db.query(
        models.User.id,
        models.User.full_name,
        func.coalesce(points_subquery.c.total_points, 0).label('total_points'),
        func.coalesce(points_subquery.c.games_played, 0).label('games_played')
    ).outerjoin(
        points_subquery, models.User.id == points_subquery.c.user_id
    ).order_by(
        desc('total_points')
    ).limit(limit).all()

    # Добавляем ранги
    leaderboard = []
    for rank, (user_id, full_name, total_points, games_played) in enumerate(leaderboard_data, 1):
        leaderboard.append({
            'rank': rank,
            'user_id': user_id,
            'full_name': full_name,
            'total_points': total_points or 0,
            'games_played': games_played or 0
        })

    return leaderboard


# Reward CRUD operations
def get_reward(db: Session, reward_id: int):
    return db.query(models.Reward).filter(models.Reward.id == reward_id).first()


def get_rewards(db: Session, skip: int = 0, limit: int = 100, available_only: bool = True):
    query = db.query(models.Reward)
    if available_only:
        query = query.filter(
            models.Reward.is_available == True,
            models.Reward.stock_quantity > 0
        )
    return query.offset(skip).limit(limit).all()


def create_reward(db: Session, reward: schemas.RewardCreate):
    db_reward = models.Reward(
        name=reward.name,
        description=reward.description,
        points_required=reward.points_required,
        image_url=reward.image_url,
        stock_quantity=reward.stock_quantity
    )
    db.add(db_reward)
    db.commit()
    db.refresh(db_reward)
    return db_reward


def update_reward_stock(db: Session, reward_id: int, new_stock: int):
    db_reward = get_reward(db, reward_id)
    if db_reward:
        db_reward.stock_quantity = new_stock
        if new_stock <= 0:
            db_reward.is_available = False
        db.commit()
        db.refresh(db_reward)
    return db_reward


# Reward Claim operations
def create_reward_claim(db: Session, user_id: int, reward_id: int):
    db_claim = models.RewardClaim(
        user_id=user_id,
        reward_id=reward_id,
        status="pending"
    )
    db.add(db_claim)

    # Update reward stock
    reward = get_reward(db, reward_id)
    if reward and reward.stock_quantity > 0:
        reward.stock_quantity -= 1
        if reward.stock_quantity <= 0:
            reward.is_available = False

    db.commit()
    db.refresh(db_claim)
    return db_claim


def get_user_reward_claims(db: Session, user_id: int):
    return db.query(models.RewardClaim).filter(
        models.RewardClaim.user_id == user_id
    ).all()


def update_reward_claim_status(db: Session, claim_id: int, status: str):
    db_claim = db.query(models.RewardClaim).filter(models.RewardClaim.id == claim_id).first()
    if db_claim:
        db_claim.status = status
        db.commit()
        db.refresh(db_claim)
    return db_claim


# Internship CRUD operations
def get_internship(db: Session, internship_id: int):
    return db.query(models.Internship).filter(models.Internship.id == internship_id).first()


def get_internships(db: Session, skip: int = 0, limit: int = 100, active_only: bool = True):
    query = db.query(models.Internship)
    if active_only:
        query = query.filter(models.Internship.is_active == True)
    return query.offset(skip).limit(limit).all()


def create_internship(db: Session, internship: schemas.InternshipCreate):
    db_internship = models.Internship(
        title=internship.title,
        description=internship.description,
        requirements=internship.requirements,
        duration=internship.duration,
        location=internship.location
    )
    db.add(db_internship)
    db.commit()
    db.refresh(db_internship)
    return db_internship


# Admin operations
def get_all_users_count(db: Session):
    return db.query(models.User).count()


def get_all_games_count(db: Session):
    return db.query(models.Game).count()


def get_all_rewards_count(db: Session):
    return db.query(models.Reward).count()


def get_pending_reward_claims(db: Session):
    return db.query(models.RewardClaim).filter(
        models.RewardClaim.status == "pending"
    ).all()


# Utility functions
def can_user_claim_reward(db: Session, user_id: int, reward_id: int):
    user_points = get_user_total_points(db, user_id)
    reward = get_reward(db, reward_id)

    if not reward or not reward.is_available or reward.stock_quantity <= 0:
        return False

    return user_points >= reward.points_required


def get_user_rank(db: Session, user_id: int):
    leaderboard = get_leaderboard(db, limit=1000)  # Get large enough list to find user
    for entry in leaderboard:
        if entry['user_id'] == user_id:
            return entry['rank']
    return None


def get_user_stats(db: Session, user_id: int):
    total_points = get_user_total_points(db, user_id)
    games_played = get_user_games_played(db, user_id)
    rank = get_user_rank(db, user_id)

    return {
        'total_points': total_points,
        'games_played': games_played,
        'rank': rank,
        'average_score': total_points / games_played if games_played > 0 else 0
    }


# Additional utility function to get game results with multiplier info
def get_user_game_results_with_multiplier(db: Session, user_id: int, game_id: int):
    """
    Возвращает результаты игры с информацией о множителе баллов
    """
    result = get_user_game_results(db, user_id, game_id)
    if result:
        game = get_game(db, game_id)
        base_points = game.points_reward if game else 0
        return {
            'result': result,
            'multiplier_applied': True,
            'base_points': base_points // 5,  # Исходные баллы без множителя
            'multiplied_points': result.total_points,
            'multiplier_value': 5
        }
    return None


# Function to calculate points with multiplier for display
def calculate_points_with_multiplier(base_points: int, multiplier: int = 5):
    """
    Рассчитывает баллы с применением множителя
    """
    return base_points * multiplier