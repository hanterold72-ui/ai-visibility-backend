from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    APP_NAME: str = "AI-Visibility Platform"
    ENVIRONMENT: str = "production"
    FRONTEND_URL: str = "http://localhost:3000"
    SERVICE_API_KEY: str = "change-me"
    JWT_SECRET: str = "change-me-32-chars-minimum"
    AUTO_CREATE_TABLES: bool = True
    DATABASE_URL: str = ""
    REDIS_URL: str = "redis://localhost:6379/0"
    PERPLEXITY_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    GOOGLE_GEMINI_API_KEY: str = ""
    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    STRIPE_PRICE_STARTER: str = ""
    STRIPE_PRICE_PRO: str = ""
    STRIPE_PRICE_AGENCY: str = ""
    YOOKASSA_SHOP_ID: str = ""
    YOOKASSA_SECRET_KEY: str = ""

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()
