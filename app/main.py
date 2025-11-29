from fastapi import FastAPI, Depends, HTTPException, Request, Form, Cookie
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlalchemy.orm import Session
import os
from typing import Optional
import logging
from jose import jwt

from app import crud, models, schemas, auth
from app.database import SessionLocal, engine, create_database
from app.auth import get_current_user, get_current_active_user, SECRET_KEY, ALGORITHM

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="X5Tech Student Platform",
    version="1.0.0",
    description="Платформа для взаимодействия студентов с X5Tech"
)

# Определяем правильные пути
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # Папка ShortHack
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")

# Монтируем статические файлы фронтенда
app.mount("/static", StaticFiles(directory=os.path.join(FRONTEND_DIR, "static")), name="static")

# Настраиваем шаблоны
templates = Jinja2Templates(directory=os.path.join(FRONTEND_DIR, "templates"))

@app.on_event("startup")
def startup_event():
    """Создает базу данных при запуске приложения"""
    logger.info("🚀 Запуск X5Tech Student Platform...")
    create_database()
    logger.info("✅ Платформа готова к работе!")

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Dependency для получения пользователя из куки
async def get_current_user_from_cookie(
        access_token: Optional[str] = Cookie(None),
        db: Session = Depends(get_db)
):
    if not access_token:
        return None

    try:
        # Убираем "Bearer " из токена
        token = access_token.replace("Bearer ", "")
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            return None
    except Exception:
        return None

    user = crud.get_user_by_email(db, email=email)
    return user

# Главная страница
@app.get("/", response_class=HTMLResponse)
async def read_root(
        request: Request,
        user: Optional[models.User] = Depends(get_current_user_from_cookie),
        db: Session = Depends(get_db)
):
    user_points = 0
    if user:
        user_points = crud.get_user_total_points(db, user.id)

    return templates.TemplateResponse("index.html", {
        "request": request,
        "user": user,
        "user_points": user_points
    })

# Страница "О компании"
@app.get("/about", response_class=HTMLResponse)
async def about_company(
        request: Request,
        user: Optional[models.User] = Depends(get_current_user_from_cookie),
        db: Session = Depends(get_db)
):
    return templates.TemplateResponse("about.html", {
        "request": request,
        "user": user
    })

# Страница стажировок
@app.get("/internships", response_class=HTMLResponse)
async def read_internships(
        request: Request,
        user: Optional[models.User] = Depends(get_current_user_from_cookie),
        db: Session = Depends(get_db)
):
    return templates.TemplateResponse("internships.html", {
        "request": request,
        "user": user
    })


# Регистрация - GET метод (показывает форму)
@app.get("/register", response_class=HTMLResponse)
async def register_form(
        request: Request,
        user: Optional[models.User] = Depends(get_current_user_from_cookie)
):
    if user:
        return RedirectResponse(url="/", status_code=303)

    return templates.TemplateResponse("auth/register.html", {
        "request": request,
        "user": user
    })

# Регистрация - POST метод (обрабатывает форму)
@app.post("/register")
async def register(
        request: Request,
        email: str = Form(...),
        phone: str = Form(...),
        telegram_id: str = Form(...),
        full_name: str = Form(...),
        password: str = Form(...),
        study_direction: str = Form(None),
        interests: str = Form(None),
        db: Session = Depends(get_db)
):
    try:
        # Проверяем минимальную длину пароля
        if len(password) < 6:
            return templates.TemplateResponse("auth/register.html", {
                "request": request,
                "error": "Пароль должен содержать минимум 6 символов",
                "user": None
            })

        # Проверяем, существует ли пользователь
        if crud.get_user_by_email(db, email):
            return templates.TemplateResponse("auth/register.html", {
                "request": request,
                "error": "Пользователь с таким email уже существует",
                "user": None
            })

        if crud.get_user_by_phone(db, phone):
            return templates.TemplateResponse("auth/register.html", {
                "request": request,
                "error": "Пользователь с таким номером телефона уже существует",
                "user": None
            })

        # Создаем пользователя
        user_data = schemas.UserCreate(
            email=email,
            phone=phone,
            telegram_id=telegram_id,
            full_name=full_name,
            password=password,
            study_direction=study_direction,
            interests=interests
        )

        user = crud.create_user(db=db, user=user_data)

        return RedirectResponse(url="/login", status_code=303)

    except Exception as e:
        print(f"Ошибка при регистрации: {e}")
        return templates.TemplateResponse("auth/register.html", {
            "request": request,
            "error": f"Произошла ошибка при регистрации: {str(e)}",
            "user": None
        })

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

# Вход в систему
@app.get("/login", response_class=HTMLResponse)
async def login_form(
        request: Request,
        user: Optional[models.User] = Depends(get_current_user_from_cookie)
):
    if user:
        return RedirectResponse(url="/", status_code=303)

    return templates.TemplateResponse("auth/login.html", {
        "request": request,
        "user": user
    })

@app.post("/login")
async def login(
        request: Request,
        email: str = Form(...),
        password: str = Form(...),
        db: Session = Depends(get_db)
):
    try:
        user = auth.authenticate_user(db, email, password)
        if not user:
            return templates.TemplateResponse("auth/login.html", {
                "request": request,
                "error": "Неверный email или пароль",
                "user": None
            })

        access_token = auth.create_access_token(data={"sub": user.email})
        response = RedirectResponse(url="/", status_code=303)
        response.set_cookie(
            key="access_token",
            value=f"Bearer {access_token}",
            httponly=True,
            max_age=1800  # 30 минут
        )
        return response

    except Exception as e:
        print(f"Ошибка при входе: {e}")
        return templates.TemplateResponse("auth/login.html", {
            "request": request,
            "error": "Произошла ошибка при входе в систему",
            "user": None
        })

# Выход из системы
@app.get("/logout")
async def logout():
    response = RedirectResponse(url="/", status_code=303)
    response.delete_cookie(key="access_token")
    return response

# Профиль пользователя
@app.get("/profile", response_class=HTMLResponse)
async def read_profile(
        request: Request,
        user: Optional[models.User] = Depends(get_current_user_from_cookie),
        db: Session = Depends(get_db)
):
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    # Получаем полную статистику пользователя
    user_stats = crud.get_user_stats(db, user.id)

    # Получаем ранг пользователя
    leaderboard = crud.get_leaderboard(db, limit=1000)
    user_rank = None
    for entry in leaderboard:
        if entry['user_id'] == user.id:
            user_rank = entry['rank']
            break

    return templates.TemplateResponse("profile.html", {
        "request": request,
        "user": user,
        "total_points": user_stats['total_points'],
        "games_played": user_stats['games_played'],
        "average_score": user_stats['average_score'],
        "user_rank": user_rank
    })

# Таблица лидеров
@app.get("/leaderboard", response_class=HTMLResponse)
async def read_leaderboard(
        request: Request,
        user: Optional[models.User] = Depends(get_current_user_from_cookie),
        db: Session = Depends(get_db)
):
    leaderboard = crud.get_leaderboard(db, limit=25)

    # Вычисляем статистику для отображения
    total_users = db.query(models.User).count()
    total_games_played = db.query(models.GameResult).count()
    total_points = db.query(func.sum(models.GameResult.total_points)).scalar() or 0

    # Средний балл на пользователя
    avg_points_per_user = total_points / total_users if total_users > 0 else 0

    # Максимальное количество баллов для прогресс-бара
    max_points = max([player['total_points'] for player in leaderboard]) if leaderboard else 0

    user_stats = {}
    if user:
        user_stats = crud.get_user_stats(db, user.id)

        # Получаем ранг пользователя
        full_leaderboard = crud.get_leaderboard(db, limit=1000)
        user_rank = None
        for entry in full_leaderboard:
            if entry['user_id'] == user.id:
                user_rank = entry['rank']
                break
    else:
        user_rank = None
        user_stats = {'total_points': 0, 'games_played': 0}

    return templates.TemplateResponse("leaderboard.html", {
        "request": request,
        "user": user,
        "leaderboard": leaderboard,
        "user_rank": user_rank,
        "user_points": user_stats.get('total_points', 0),
        "user_games_played": user_stats.get('games_played', 0),
        "total_users": total_users,
        "total_games_played": total_games_played,
        "total_points": total_points,
        "avg_points_per_user": avg_points_per_user,
        "max_points": max_points
    })
# Награды
@app.get("/rewards", response_class=HTMLResponse)
async def read_rewards(
        request: Request,
        user: Optional[models.User] = Depends(get_current_user_from_cookie),
        db: Session = Depends(get_db)
):
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    rewards = crud.get_rewards(db, available_only=True)
    user_points = crud.get_user_total_points(db, user.id)
    return templates.TemplateResponse("rewards.html", {
        "request": request,
        "user": user,
        "rewards": rewards,
        "user_points": user_points
    })

# Игры
@app.get("/games", response_class=HTMLResponse)
async def read_games(
        request: Request,
        user: Optional[models.User] = Depends(get_current_user_from_cookie),
        db: Session = Depends(get_db)
):
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    games = crud.get_games(db, active_only=True)
    return templates.TemplateResponse("games.html", {
        "request": request,
        "user": user,
        "games": games
    })

# Health check
@app.get("/health")
async def health_check():
    return {"status": "healthy", "message": "X5Tech Platform is running"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

    from fastapi import Cookie
import json
@app.post("/api/game/complete")
async def complete_game(
        request: Request,
        game_type: str = Form(...),
        score: int = Form(...),
        total_points: int = Form(...),
        access_token: Optional[str] = Cookie(None),
        db: Session = Depends(get_db)
):
    """Endpoint для завершения игры и начисления баллов"""
    if not access_token:
        return {"success": False, "error": "Not authenticated"}

    try:
        # Получаем пользователя из токена
        token = access_token.replace("Bearer ", "")
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("sub")

        user = crud.get_user_by_email(db, email)
        if not user:
            return {"success": False, "error": "User not found"}

        # Начисляем баллы и увеличиваем счетчик игр
        updated_user = crud.update_user_points_and_games(db, user.id, total_points)

        # Получаем обновленную статистику
        user_stats = crud.get_user_stats(db, user.id)

        # Логируем результат игры
        print(f"User {user.email} completed {game_type} with score {score}, earned {total_points} points. Total games: {updated_user.games_played_count}")

        return {
            "success": True,
            "new_points": updated_user.points_count,
            "points_earned": total_points,
            "games_played": updated_user.games_played_count,
            "average_score": user_stats['average_score']
        }

    except Exception as e:
        print(f"Error completing game: {e}")
        return {"success": False, "error": str(e)}