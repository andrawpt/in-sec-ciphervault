import base64
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env", override=False)


def _key(name: str) -> bytes:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is not set. Run first: python -m scripts.init_env")
    key = base64.b64decode(value)
    if len(key) != 32:
        raise RuntimeError(f"{name} must be 32 bytes (base64).")
    return key


def _path(name: str, default: str) -> Path:
    p = Path(os.getenv(name, default))
    return p if p.is_absolute() else BASE_DIR / p


@dataclass(frozen=True)
class Settings:
    master_key: bytes
    integrity_key: bytes
    blind_index_key: bytes
    jwt_secret: str
    jwt_exp_minutes: int
    db_path: Path
    storage_dir: Path
    max_upload_mb: int
    cors_origins: list[str]


@lru_cache
def get_settings() -> Settings:
    jwt_secret = os.getenv("JWT_SECRET", "").strip()
    if len(jwt_secret) < 32:
        raise RuntimeError("JWT_SECRET is not set. Run first: python -m scripts.init_env")
    return Settings(
        master_key=_key("MASTER_KEY"),
        integrity_key=_key("INTEGRITY_KEY"),
        blind_index_key=_key("BLIND_INDEX_KEY"),
        jwt_secret=jwt_secret,
        jwt_exp_minutes=int(os.getenv("JWT_EXP_MINUTES", "120")),
        db_path=_path("DB_PATH", "data/lapor.db"),
        storage_dir=_path("STORAGE_DIR", "storage"),
        max_upload_mb=int(os.getenv("MAX_UPLOAD_MB", "200")),
        cors_origins=[o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",") if o.strip()],
    )
