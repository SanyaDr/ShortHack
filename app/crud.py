from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from . import models, schemas, auth

# User CRUD
def get_user(db: Session, user_id: int):
    return db.query(models.User).filter(models.User.id == user_id).first()

def get_user_by_email(db: Session, email: str):
    return db.query(models.User).filter(models.User.email == email).first()

def get_user_by_phone(db: Session, phone: str):
    return db.query(models.User).filter(models.User.phone == phone).first()

def get_users(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.User).offset(skip).limit(limit).all()

def create_user(db: Session, user: schemas.UserCreate):
    hashed_password = auth.get_password_hash(user.password)
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

def get_leaderboard(db: Session, limit: int = 50):
    # Подзапрос для подсчета очков каждого пользователя
    from sqlalchemy import select, func
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
    leaderboard = db.query(
        models.User.id,
        models.User.full_name,
        func.coalesce(points_subquery.c.total_points, 0).label('total_points'),
        func.coalesce(points_subquery.c.games_played, 0).label('games_played'),
        func.rank().over(
            order_by=func.coalesce(points_subquery.c.total_points, 0).desc()
        ).label('rank')
    ).outerjoin(
        points_subquery, models.User.id == points_subquery.c.user_id
    ).order_by(
        desc('total_points')
    ).limit(limit).all()

    return leaderboard

# Game CRUD
def get_game(db: Session, game_id: int):
    return db.query(models.Game).filter(models.Game.id == game_id).first()

def get_games(db: Session, skip: int = 0, limit: int = 100, active_only: bool = True):
    query = db.query(models.Game)
    if active_only:
        query = query.filter(models.Game.is_active == True)
    return query.offset(skip).limit(limit).all()

def create_game(db: Session, game: schemas.GameCreate, user_id: int):
    db_game = models.Game(
        title=game.title,
        description=game.description,
        game_type=game.game_type,
        points_reward=game.points_reward,
        created_by=user_id
    )
    db.add(db_game)
    db.commit()
    db.refresh(db_game)

    # Создаем вопросы
    for question_data in game.questions:
        db_question = models.GameQuestion(
            game_id=db_game.id,
            **question_data.dict()
        )
        db.add(db_question)

    db.commit()
    db.refresh(db_game)
    return db_game

def submit_game_results(db: Session, game_submission: schemas.GameSubmission, user_id: int, game_id: int):
    game = get_game(db, game_id)
    if not game:
        return None

    questions = db.query(models.GameQuestion).filter(models.GameQuestion.game_id == game_id).all()

    correct_answers = 0
    for question in questions:
        user_answer = game_submission.answers.get(str(question.id))
        if user_answer == question.correct_answer:
            correct_answers += 1

    score = (correct_answers / len(questions)) * 100
    points_earned = int((score / 100) * game.points_reward)

    # Сохраняем результат
    db_result = models.GameResult(
        user_id=user_id,
        game_id=game_id,
        score=score,
        total_points=points_earned
    )
    db.add(db_result)
    db.commit()
    db.refresh(db_result)

    return db_result

# Reward CRUD
def get_rewards(db: Session, skip: int = 0, limit: int = 100, available_only: bool = True):
    query = db.query(models.Reward)
    if available_only:
        query = query.filter(models.Reward.is_available == True)
    return query.offset(skip).limit(limit).all()

def create_reward(db: Session, reward: schemas.RewardCreate):
    db_reward = models.Reward(**reward.dict())
    db.add(db_reward)
    db.commit()
    db.refresh(db_reward)
    return db_reward

def claim_reward(db: Session, user_id: int, reward_id: int):
    reward = db.query(models.Reward).filter(models.Reward.id == reward_id).first()
    if not reward or not reward.is_available or reward.stock_quantity <= 0:
        return None

    # Проверяем баллы пользователя
    user_points = get_user_total_points(db, user_id)
    if user_points < reward.points_required:
        return None

    # Создаем заявку на получение награды
    db_claim = models.RewardClaim(
        user_id=user_id,
        reward_id=reward_id
    )

    # Уменьшаем количество наград
    reward.stock_quantity -= 1
    if reward.stock_quantity <= 0:
        reward.is_available = False

    db.add(db_claim)
    db.commit()
    db.refresh(db_claim)
    return db_claim

def get_user_total_points(db: Session, user_id: int):
    result = db.query(func.sum(models.GameResult.total_points)).filter(
        models.GameResult.user_id == user_id
    ).scalar()
    return result or 0