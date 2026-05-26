#!/usr/bin/env python3
"""
Setup script for Taskforce Management System
Run this once to initialize the database and create necessary tables.
Uses DATABASE_URL from .env for database connection (supports any SQLAlchemy-supported database).
"""
import os
import sys
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

from config import Config

def setup_database():
    """Initialize the database and create all tables using SQLAlchemy models"""
    db_uri = Config.SQLALCHEMY_DATABASE_URI
    print(f"📦 Connecting to database...")
    print(f"   Database URI: {db_uri.split('@')[0] if '@' in db_uri else db_uri[:50]}...")

    # Import app and models after environment is loaded
    from app import create_app
    from database.models import db

    app = create_app()

    # Create all tables based on SQLAlchemy models
    with app.app_context():
        try:
            db.create_all()
            print("✅ Database tables created successfully!")
            
            # Sanity check - verify at least one table exists
            try:
                from database.models import Member
                member_count = Member.query.count()
                print(f"✅ Member table initialized ({member_count} records)")
            except Exception as e:
                print(f"⚠️  Could not query Member table (this is OK if it's the first run): {e}")
        except Exception as e:
            print(f"❌ Error creating database tables: {e}")
            print(f"   Make sure DATABASE_URL is set correctly in your .env file")
            return False

    return True

def create_sample_data():
    """Optional: create sample data for testing"""
    from app import create_app
    app = create_app()
    with app.app_context():
        from database.models import db, Member
        from datetime import datetime
        
        if Member.query.count() > 0:
            print("ℹ️  Sample data already exists, skipping creation.")
            return
        
        sample_members = [
            Member(
                discord_username="Commander_Alpha", 
                roblox_username="AlphaLeader", 
                current_rank="Commander"
            ),
            Member(
                discord_username="Marshall_Beta", 
                roblox_username="BetaMarshall", 
                current_rank="Marshall"
            ),
            Member(
                discord_username="Aspirant_Gamma", 
                roblox_username="GammaNewbie", 
                current_rank="Aspirant"
            ),
        ]
        
        for member in sample_members:
            db.session.add(member)
        
        db.session.commit()
        print(f"✅ Created {len(sample_members)} sample members")

if __name__ == "__main__":
    print("🚀 Setting up Taskforce Management System...")
    print(f"   Database Backend: {Config.SQLALCHEMY_DATABASE_URI.split('+')[0] if '+' in Config.SQLALCHEMY_DATABASE_URI else 'sqlite'}")
    
    ok = setup_database()
    if not ok:
        print("❌ Setup failed")
        sys.exit(1)
    
    if len(sys.argv) > 1 and sys.argv[1] == "--sample":
        create_sample_data()
    
    print("✅ Setup completed successfully!")
