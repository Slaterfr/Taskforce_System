import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = 'Cev_Is_Swifts_Fav_Aparently'  # Change this to a secure random key
    STAFF_PASSWORD = 'task2025'  # Change this to a secure password
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///database/taskforce.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Roblox API settings
    ROBLOX_GROUP_ID = os.environ.get('ROBLOX_GROUP_ID') or ''
    ROBLOX_COOKIE = os.environ.get('ROBLOX_COOKIE') or ''  # .ROBLOSECURITY cookie for write operations
    ROBLOX_SYNC_ENABLED = os.environ.get('ROBLOX_SYNC_ENABLED', 'false').lower() == 'true'
    ROBLOX_SYNC_INTERVAL = int(os.environ.get('ROBLOX_SYNC_INTERVAL', '3600'))  # Default 1 hour (3600 seconds)
    ROBLOX_BACKGROUND_SYNC_ENABLED = os.environ.get('ROBLOX_BACKGROUND_SYNC_ENABLED', str(ROBLOX_SYNC_ENABLED)).lower() == 'true'
