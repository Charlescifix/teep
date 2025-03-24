# app/config.py
import os
from dotenv import load_dotenv

load_dotenv()  # Loads .env into environment variables

class Settings:
    DATABASE_URL = os.getenv("DATABASE_URL")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    # Add other constants if needed

settings = Settings()
