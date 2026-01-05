import os
from pydantic_settings import BaseSettings
from dotenv import load_dotenv
import os

# Always load .env from root
BASE_DIR = os.path.dirname(os.path.dirname(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))


class Settings(BaseSettings):
    GOOGLE_CLIENT_ID: str = os.getenv("GOOGLE_CLIENT_ID")
    GOOGLE_USERINFO_URL: str = os.getenv("GOOGLE_USERINFO_URL")

    JWT_SECRET: str = os.getenv("JWT_SECRET")
    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM")
    JWT_EXPIRE_MINUTES: int = os.getenv(
        "JWT_EXPIRE_MINUTES")  # 24 hours default
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = os.getenv(
        "JWT_REFRESH_TOKEN_EXPIRE_DAYS")  # 7 Days default

    # Twilio
    TWILIO_ACCOUNT_SID: str | None = os.getenv("TWILIO_ACCOUNT_SID")
    TWILIO_AUTH_TOKEN: str | None = os.getenv("TWILIO_AUTH_TOKEN")
    TWILIO_VERIFY_SID: str | None = os.getenv("TWILIO_VERIFY_SID")
    UPLOAD_DIR: str | None = os.getenv("PROFILE_PIC_PATH")

    DB_USER: str = os.getenv("DB_USER")
    DB_PASS: str = os.getenv("DB_PASS")
    DB_HOST: str = os.getenv("DB_HOST")
    DB_PORT: str = os.getenv("DB_PORT")
    AUTH_DB_NAME: str = os.getenv("AUTH_DB_NAME")
    FACILITY_DB_NAME: str = os.getenv("FACILITY_DB_NAME")
    # Add HRMS database configuration
    HRMS_DB_NAME: str = os.getenv("HRMS_DB_NAME")


    # Email Configuration FOR TICKETS CHANGES 
    SMTP_HOST: str | None = os.getenv("SMTP_HOST")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", 587))
    SMTP_USERNAME: str | None = os.getenv("SMTP_USERNAME")
    SMTP_PASSWORD: str | None = os.getenv("SMTP_PASSWORD")
    SMTP_USE_SSL: bool = os.getenv("SMTP_USE_SSL", "False").lower() == "true"
    EMAIL_SENDER: str = os.getenv("EMAIL_SENDER", "noreply@sales-arm.com")

    class Config:
        env_file = ".env"   # 👈 important
        env_file_encoding = "utf-8"
        extra = "ignore"   # 👈 important


settings = Settings()

AUTH_DATABASE_URL = (
    f"postgresql+psycopg2://{settings.DB_USER}:{settings.DB_PASS}@{settings.DB_HOST}:{settings.DB_PORT}/{settings.AUTH_DB_NAME}?sslmode=require"
)

FACILITY_DATABASE_URL = (
    f"postgresql+psycopg2://{settings.DB_USER}:{settings.DB_PASS}@{settings.DB_HOST}:{settings.DB_PORT}/{settings.FACILITY_DB_NAME}?sslmode=require"
)

# Create HRMS database URL
HRMS_DATABASE_URL = (
    f"postgresql+psycopg2://{settings.DB_USER}:{settings.DB_PASS}@{settings.DB_HOST}:{settings.DB_PORT}/{settings.HRMS_DB_NAME}?sslmode=require"
)

