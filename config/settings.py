from pathlib import Path

class Settings:
    BASE_DIR: Path = Path(__file__).resolve().parent.parent

    SECRET_KEY: str = "8f2d7b9b0d6d43f7a6c928c2f8897a62e1b4f90cfe742c7a9fa3c78a196a2c31"

    DATABASE_URL: str = f"sqlite+aiosqlite:///{BASE_DIR}/cinemacon.sqlite3"

    MEDIA_DIR: Path = BASE_DIR / "media" / "uploads"
    MEDIA_DIR.mkdir(parents=True, exist_ok=True)

    PASSWORD_HASH_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    

settings = Settings()
