import os
import secrets
from dotenv import load_dotenv

load_dotenv()


class Settings:
    # Security — MUST be set in .env in production
    SECRET_KEY: str = os.environ.get("SECRET_KEY", secrets.token_hex(32))
    STAFF_PASSWORD: str = os.environ.get("STAFF_PASSWORD", "")

    # Database
    DATABASE_URL: str = os.environ.get("DATABASE_URL", "sqlite:///database/taskforce.db")

    # Roblox
    ROBLOX_GROUP_ID: str = os.environ.get("ROBLOX_GROUP_ID", "")
    ROBLOX_COOKIE: str = os.environ.get("ROBLOX_COOKIE", "")
    ROBLOX_SYNC_ENABLED: bool = os.environ.get("ROBLOX_SYNC_ENABLED", "false").lower() == "true"
    ROBLOX_SYNC_INTERVAL: int = int(os.environ.get("ROBLOX_SYNC_INTERVAL", "3600"))
    ROBLOX_BACKGROUND_SYNC_ENABLED: bool = os.environ.get(
        "ROBLOX_BACKGROUND_SYNC_ENABLED",
        os.environ.get("ROBLOX_SYNC_ENABLED", "false"),
    ).lower() == "true"

    # Bot API
    DISCORD_BOT_API_KEY: str = (
        os.environ.get("TF_SYSTEM_API_KEY") or os.environ.get("DISCORD_BOT_API_KEY", "")
    )
    API_RATE_LIMIT: int = int(os.environ.get("API_RATE_LIMIT", "100"))
    API_ENABLE_LOGGING: bool = os.environ.get("API_ENABLE_LOGGING", "true").lower() == "true"

    # Discord Notifications
    DISCORD_NOTIFICATION_WEBHOOK_URL: str = os.environ.get("DISCORD_NOTIFICATION_WEBHOOK_URL", "")


settings = Settings()
