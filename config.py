import os
import secrets
from dotenv import load_dotenv

load_dotenv()


class Settings:
    # Security - MUST be set in .env in production
    SECRET_KEY: str = os.environ.get("SECRET_KEY", secrets.token_hex(32))
    STAFF_PASSWORD: str = os.environ.get("STAFF_PASSWORD", "")

    # Database
    DATABASE_URL: str = os.environ.get("DATABASE_URL", "sqlite:///database/taskforce.db")

    # Roblox Group & Sync
    ROBLOX_GROUP_ID: str = os.environ.get("ROBLOX_GROUP_ID", "")
    ROBLOX_COOKIE: str = os.environ.get("ROBLOX_COOKIE", "")
    ROBLOX_SYNC_ENABLED: bool = os.environ.get("ROBLOX_SYNC_ENABLED", "false").lower() == "true"
    ROBLOX_SYNC_INTERVAL: int = int(os.environ.get("ROBLOX_SYNC_INTERVAL", "3600"))
    ROBLOX_BACKGROUND_SYNC_ENABLED: bool = os.environ.get(
        "ROBLOX_BACKGROUND_SYNC_ENABLED",
        os.environ.get("ROBLOX_SYNC_ENABLED", "false"),
    ).lower() == "true"

    # Roblox OAuth 2.0
    ROBLOX_CLIENT_ID: str = os.environ.get("ROBLOX_CLIENT_ID", "")
    ROBLOX_CLIENT_SECRET: str = os.environ.get("ROBLOX_CLIENT_SECRET", "")
    ROBLOX_REDIRECT_URI: str = os.environ.get(
        "ROBLOX_REDIRECT_URI", "http://localhost:5000/auth/roblox/callback"
    )

    # JWT Authentication
    JWT_SECRET_KEY: str = os.environ.get("JWT_SECRET_KEY", os.environ.get("SECRET_KEY", secrets.token_hex(32)))
    JWT_ALGORITHM: str = "HS256"
    JWT_USER_TOKEN_EXPIRE_MINUTES: int = int(os.environ.get("JWT_USER_TOKEN_EXPIRE_MINUTES", "10080"))
    JWT_TENANT_TOKEN_EXPIRE_MINUTES: int = int(os.environ.get("JWT_TENANT_TOKEN_EXPIRE_MINUTES", "10080"))

    # Bot API
    DISCORD_BOT_API_KEY: str = (
        os.environ.get("TF_SYSTEM_API_KEY") or os.environ.get("DISCORD_BOT_API_KEY", "")
    )
    API_RATE_LIMIT: int = int(os.environ.get("API_RATE_LIMIT", "100"))
    API_ENABLE_LOGGING: bool = os.environ.get("API_ENABLE_LOGGING", "true").lower() == "true"

    # Discord Notifications
    DISCORD_NOTIFICATION_WEBHOOK_URL: str = os.environ.get("DISCORD_NOTIFICATION_WEBHOOK_URL", "")


settings = Settings()
