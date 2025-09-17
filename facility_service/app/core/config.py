import os
from pydantic_settings import BaseSettings
from dotenv import load_dotenv
import os

# Always load .env from root
BASE_DIR = os.path.dirname(os.path.dirname(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))

class Settings(BaseSettings):
    JWT_SECRET: str = os.getenv("JWT_SECRET")
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 1440  # 24 hours default
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

