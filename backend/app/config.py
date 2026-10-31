"""Settings read once from the environment (and a local .env, if present)."""

import os
from pathlib import Path
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()  # nearest .env (backend/)
load_dotenv(Path(__file__).resolve().parents[2] / ".env")  # repo-root .env; never overrides values already set


@dataclass(frozen=True)
class Settings:
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./fraud.db")
    groq_api_key: str | None = os.getenv("GROQ_API_KEY") or None
    cors_origins: list[str] = field(
        default_factory=lambda: [
            o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",") if o.strip()
        ]
    )
    port: int = int(os.getenv("PORT", "8000"))


settings = Settings()
