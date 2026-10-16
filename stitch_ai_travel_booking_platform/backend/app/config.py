import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")


class Settings:
    database_url = os.getenv("DATABASE_URL", "sqlite:///./travel.db")
    secret_key = os.getenv("SECRET_KEY", "dev-only-insecure-key-change-me-0000")
    access_token_minutes = int(os.getenv("ACCESS_TOKEN_MINUTES", "60"))
    cors_origins = [o for o in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",") if o]
    memory_service_url = os.getenv("MEMORY_SERVICE_URL", "").rstrip("/")
    memory_service_token = os.getenv("MEMORY_SERVICE_TOKEN", "")
    agent_memory_path = os.getenv("AGENT_MEMORY_PATH", str(Path(__file__).resolve().parents[3] / "data" / "voyara_memory"))
    context_tokenizer_path = os.getenv("CONTEXT_TOKENIZER_PATH", "")
    context_tokenizer_id = os.getenv("CONTEXT_TOKENIZER_ID", "")
    context_use_gpu = os.getenv("CONTEXT_USE_GPU", "false").lower() == "true"


settings = Settings()
