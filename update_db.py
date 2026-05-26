"""
Database schema update script
Updates the database schema to match the latest SQLAlchemy models.
Works with any database backend configured in DATABASE_URL.
"""
from dotenv import load_dotenv
from app import create_app
from database.models import db
from config import Config

# Load environment variables
load_dotenv()

app = create_app()
with app.app_context():
    db_uri = Config.SQLALCHEMY_DATABASE_URI
    print("🔄 Updating database schema...")
    print(f"   Database URI: {db_uri.split('@')[0] if '@' in db_uri else db_uri[:50]}...")
    
    try:
        db.create_all()
        print("✅ Database schema updated successfully.")
    except Exception as e:
        print(f"❌ Error updating database schema: {e}")
        print(f"   Make sure DATABASE_URL is set correctly in your .env file")

