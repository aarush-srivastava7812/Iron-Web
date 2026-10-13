import os


class Settings:
    database_url = os.getenv("DATABASE_URL", "sqlite:///./travel.db")
    secret_key = os.getenv("SECRET_KEY", "dev-only-insecure-key-change-me-0000")
    access_token_minutes = int(os.getenv("ACCESS_TOKEN_MINUTES", "60"))
    cors_origins = [o for o in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",") if o]


settings = Settings()
