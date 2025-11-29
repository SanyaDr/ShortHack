import uvicorn
from app.database import create_database

if __name__ == "__main__":
    # Создаем базу данных при запуске
    print("🔄 Инициализация базы данных...")
    create_database()

    # Запускаем сервер
    print("🚀 Запуск сервера X5Tech Platform...")
    print("📊 Документация API: http://localhost:8000/docs")
    print("🌐 Веб-интерфейс: http://localhost:8000")

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )