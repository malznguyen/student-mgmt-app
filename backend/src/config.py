from dataclasses import dataclass
from pathlib import Path
import os

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


@dataclass
class Settings:
    """Application configuration loaded from environment variables."""

    mongodb_uri: str = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
    mongodb_db_name: str = os.getenv("MONGODB_DB_NAME", "university")


settings = Settings()
