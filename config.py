import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///database/taskforce.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Roblox API settings (for later phases)
    ROBLOX_GROUP_ID = os.environ.get('ROBLOX_GROUP_ID') or ''
    ROBLOX_API_KEY = os.environ.get('ROBLOX_API_KEY') or ''