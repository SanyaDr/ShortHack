from fastapi import FastAPI, Depends, HTTPException, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
import os
from typing import List
import logging

from app import crud, models, schemas, auth
from app.database import SessionLocal, engine, create_database
from app.auth import get_current_active_user

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="X5Tech Student Platform",
    version="1.0.0",
    description="Платформа для взаимодействия студентов с X5Tech"
)

# Определяем пути
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")

# Монтируем статические файлы
app.mount("/static", StaticFiles(directory=os.path.join(FRONTEND_DIR, "static")), name="static")
#app.mount("/app/static", StaticFiles(directory="app/static"), name="app_static")

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

# Главная страница
@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse("index.html", {"request": request})

# Страница стажировок
@app.get("/internships", response_class=HTMLResponse)
async def read_internships(request: Request, db: Session = Depends(get_db)):
    internships = db.query(models.Internship).filter(models.Internship.is_active == True).all()
    return templates.TemplateResponse("internships.html", {
        "request": request,
        "internships": internships
    })

# Регистрация
@app.get("/register", response_class=HTMLResponse)
async def register_form(request: Request):
    return templates.TemplateResponse("auth/register.html", {"request": request})

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
        # Проверяем длину пароля
        if len(password) > 72:
            return templates.TemplateResponse("auth/register.html", {
                "request": request,
                "error": "Пароль слишком длинный (максимум 72 символа)"
            })

        # Проверяем минимальную длину пароля
        if len(password) < 6:
            return templates.TemplateResponse("auth/register.html", {
                "request": request,
                "error": "Пароль должен содержать минимум 6 символов"
            })

        # Проверяем, существует ли пользователь
        if crud.get_user_by_email(db, email):
            return templates.TemplateResponse("auth/register.html", {
                "request": request,
                "error": "Пользователь с таким email уже существует"
            })

        if crud.get_user_by_phone(db, phone):
            return templates.TemplateResponse("auth/register.html", {
                "request": request,
                "error": "Пользователь с таким номером телефона уже существует"
            })

        # Создаем пользователя
        hashed_password = auth.get_password_hash(password)
        db_user = models.User(
            email=email,
            phone=phone,
            telegram_id=telegram_id,
            full_name=full_name,
            interests=interests,
            study_direction=study_direction,
            hashed_password=hashed_password
        )
        db.add(db_user)
        db.commit()
        db.refresh(db_user)

        return RedirectResponse(url="/login", status_code=303)

    except Exception as e:
        print(f"Ошибка при регистрации: {e}")
        return templates.TemplateResponse("auth/register.html", {
            "request": request,
            "error": f"Произошла ошибка при регистрации: {str(e)}"
        })
# Вход в систему
@app.get("/login", response_class=HTMLResponse)
async def login_form(request: Request):
    return templates.TemplateResponse("auth/login.html", {"request": request})

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
                "error": "Неверный email или пароль"
            })

        access_token = auth.create_access_token(data={"sub": user.email})
        response = RedirectResponse(url="/", status_code=303)
        response.set_cookie(key="access_token", value=f"Bearer {access_token}")
        return response

    except Exception as e:
        print(f"Ошибка при входе: {e}")
        return templates.TemplateResponse("auth/login.html", {
            "request": request,
            "error": "Произошла ошибка при входе в систему"
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
        current_user: models.User = Depends(auth.get_current_active_user),
        db: Session = Depends(get_db)
):
    total_points = crud.get_user_total_points(db, current_user.id)
    user_games = db.query(models.GameResult).filter(
        models.GameResult.user_id == current_user.id
    ).count()

    return templates.TemplateResponse("profile.html", {
        "request": request,
        "user": current_user,
        "total_points": total_points,
        "games_played": user_games
    })

# Таблица лидеров
@app.get("/leaderboard", response_class=HTMLResponse)
async def read_leaderboard(
        request: Request,
        db: Session = Depends(get_db)
):
    leaderboard = crud.get_leaderboard(db)
    return templates.TemplateResponse("leaderboard.html", {
        "request": request,
        "leaderboard": leaderboard
    })

# Награды
@app.get("/rewards", response_class=HTMLResponse)
async def read_rewards(
        request: Request,
        current_user: models.User = Depends(auth.get_current_active_user),
        db: Session = Depends(get_db)
):
    rewards = crud.get_rewards(db, available_only=True)
    user_points = crud.get_user_total_points(db, current_user.id)
    return templates.TemplateResponse("rewards.html", {
        "request": request,
        "rewards": rewards,
        "user_points": user_points
    })

# Игры
@app.get("/games", response_class=HTMLResponse)
async def read_games(
        request: Request,
        current_user: models.User = Depends(auth.get_current_active_user),
        db: Session = Depends(get_db)
):
    games = crud.get_games(db, active_only=True)
    return templates.TemplateResponse("games/list.html", {
        "request": request,
        "games": games
    })

# Конкретная игра
@app.get("/games/{game_id}", response_class=HTMLResponse)
async def play_game(
        request: Request,
        game_id: int,
        current_user: models.User = Depends(auth.get_current_active_user),
        db: Session = Depends(get_db)
):
    game = crud.get_game(db, game_id)
    if not game or not game.is_active:
        raise HTTPException(status_code=404, detail="Игра не найдена")

    # В зависимости от типа игры показываем соответствующий шаблон
    if game.game_type == "truth_or_lie":
        template = "games/truth_or_lie.html"
    elif game.game_type == "mem_vs_situation":
        template = "games/mem_vs_situation.html"
    else:
        template = "games/default.html"

    return templates.TemplateResponse(template, {
        "request": request,
        "game": game
    })

# О компании
@app.get("/about", response_class=HTMLResponse)
async def about_company(request: Request):
    return templates.TemplateResponse("about.html", {"request": request})

# API endpoints для AJAX запросов
@app.get("/api/user/points")
async def get_user_points(
        current_user: models.User = Depends(auth.get_current_active_user),
        db: Session = Depends(get_db)
):
    points = crud.get_user_total_points(db, current_user.id)
    return {"points": points}

@app.post("/api/rewards/{reward_id}/claim")
async def claim_reward(
        reward_id: int,
        current_user: models.User = Depends(auth.get_current_active_user),
        db: Session = Depends(get_db)
):
    claim = crud.claim_reward(db, current_user.id, reward_id)
    if not claim:
        raise HTTPException(status_code=400, detail="Не удалось получить награду")
    return {"message": "Заявка на получение награды отправлена"}

# Админ панель
@app.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(
        request: Request,
        current_user: models.User = Depends(auth.get_current_active_user),
        db: Session = Depends(get_db)
):
    if not current_user.is_admin and not current_user.is_manager:
        raise HTTPException(status_code=403, detail="Доступ запрещен")

    total_users = db.query(models.User).count()
    total_games = db.query(models.Game).count()
    total_rewards = db.query(models.Reward).count()

    return templates.TemplateResponse("admin/dashboard.html", {
        "request": request,
        "total_users": total_users,
        "total_games": total_games,
        "total_rewards": total_rewards
    })

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)