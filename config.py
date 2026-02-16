import os
from dotenv import load_dotenv

load_dotenv()  # Загружает переменные из .env файла

BOT_TOKEN = os.getenv('BOT_TOKEN')        # Берет токен из переменных окружения
BOT_USERNAME = os.getenv('BOT_USERNAME')  # Берет username бота из переменных окружения