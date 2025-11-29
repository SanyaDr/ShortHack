from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os

# SQLite база данных
SQLALCHEMY_DATABASE_URL = "sqlite:///./app.db"

# Создаем движок SQLAlchemy
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False}
)

# Создаем фабрику сессий
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Базовый класс для моделей
Base = declarative_base()

def create_database():
    """Создает базу данных и все таблицы, если они не существуют"""
    try:
        # Проверяем существование файла базы данных
        db_file = "./app.db"
        db_exists = os.path.exists(db_file)

        # Создаем все таблицы
        Base.metadata.create_all(bind=engine)

        if not db_exists:
            print("✅ База данных создана успешно!")
        else:
            print("✅ База данных подключена!")

    except Exception as e:
        print(f"❌ Ошибка при создании базы данных: {e}")
        raise

# Зависимость для получения сессии базы данных
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()