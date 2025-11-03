import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = 'Cev_Is_Swifts_Fav_Aparently'  # Change this to a secure random key
    STAFF_PASSWORD = 'task2025'  # Change this to a secure password
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///database/taskforce.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Roblox API settings (for later phases)
    ROBLOX_GROUP_ID = os.environ.get('ROBLOX_GROUP_ID') or ''
    ROBLOX_API_KEY = os.environ.get('ROBLOX_API_KEY') or ''
