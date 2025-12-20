from app import create_app
from database.models import db

app = create_app()
with app.app_context():
    print("🔄 Updating database schema...")
    db.create_all()
    print("✅ Database schema updated.")
