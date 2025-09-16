import os
from pydantic_settings import BaseSettings
from dotenv import load_dotenv
import os

# Always load .env from root
BASE_DIR = os.path.dirname(os.path.dirname(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))

class Settings(BaseSettings):
    GOOGLE_CLIENT_ID: str = os.getenv("GOOGLE_CLIENT_ID")

    JWT_SECRET: str = os.getenv("JWT_SECRET")
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 1440  # 24 hours default

    # Twilio
    TWILIO_ACCOUNT_SID: str | None = os.getenv("TWILIO_ACCOUNT_SID")
    TWILIO_AUTH_TOKEN: str | None = os.getenv("TWILIO_AUTH_TOKEN")
    TWILIO_VERIFY_SID: str | None = os.getenv("TWILIO_VERIFY_SID")
    UPLOAD_DIR : str | None = os.getenv("PROFILE_PIC_PATH")
    
    DB_USER: str= os.getenv("DB_USER")
    DB_PASS: str= os.getenv("DB_PASS")
    DB_HOST: str= os.getenv("DB_HOST")
    DB_PORT: str= os.getenv("DB_PORT")
    DB_NAME: str= os.getenv("DB_NAME")
    
    class Config:
        env_file = ".env"   # 👈 important
        env_file_encoding = "utf-8"
        extra = "ignore"   # 👈 important

settings = Settings()

SQLALCHEMY_DATABASE_URL = (
    f"postgresql://{settings.DB_USER}:{settings.DB_PASS}@{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}"
)
