from pathlib import Path
from typing import List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = (BACKEND_DIR / "nova_license.db").as_posix()
DEFAULT_KEY_PATH = (BACKEND_DIR / "keys" / "nova-key-2026-01_private.pem").as_posix()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(
            str(BACKEND_DIR / ".env"),
            str(BACKEND_DIR.parent / ".env"),
            ".env",
        ),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    NOVA_APP_NAME: str = "NOVA License Management"
    NOVA_DATABASE_URL: str = f"sqlite:///{DEFAULT_DB_PATH}"

    # JWT Settings
    NOVA_JWT_SECRET_KEY: str = "dev-only-jwt-secret-key-replace-in-production-env-32bytes"
    NOVA_JWT_ALGORITHM: str = "HS256"
    NOVA_ACCESS_TOKEN_EXPIRE_MINUTES: int = 480

    # Signing Key Settings
    NOVA_ACTIVE_KEY_ID: Optional[str] = None
    NOVA_SIGNING_PRIVATE_KEY_PATH: Optional[str] = None
    NOVA_SIGNING_PRIVATE_KEY_PEM: Optional[str] = None
    NOVA_SIGNING_KEY_PASSPHRASE: Optional[str] = None

    # CORS
    NOVA_CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000"

    @property
    def cors_origins_list(self) -> List[str]:
        return [o.strip() for o in self.NOVA_CORS_ORIGINS.split(",") if o.strip()]

    @property
    def resolved_private_key_path(self) -> Optional[Path]:
        if not self.NOVA_SIGNING_PRIVATE_KEY_PATH or not self.NOVA_SIGNING_PRIVATE_KEY_PATH.strip():
            return None
        p = Path(self.NOVA_SIGNING_PRIVATE_KEY_PATH.strip())
        if not p.is_absolute():
            candidate = BACKEND_DIR / p
            if candidate.exists():
                return candidate
        return p


settings = Settings()
