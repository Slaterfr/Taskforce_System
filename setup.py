#!/usr/bin/env python3
"""
Setup script for Taskforce Management System
Run this once to initialize the database and create necessary directories
"""

import os
import sys
from config import Config
from database.models import db

def setup_database():
    """Initialize the database and create all tables"""
    # Derive the sqlite path from the config and ensure the directory/file exist
    db_uri = getattr(Config, 'SQLALCHEMY_DATABASE_URI', '')
    sqlite_path = None
    try:
        from sqlalchemy.engine import make_url
        url = make_url(db_uri)
        sqlite_path = url.database
    except Exception:
        if isinstance(db_uri, str) and db_uri.startswith('sqlite:'):
            sqlite_path = db_uri.split('://', 1)[-1].lstrip('/')

    # Prefer the instance folder: ensure instance/taskforce.db exists
    base_dir = os.path.dirname(os.path.abspath(__file__))
    instance_dir = os.path.join(base_dir, 'instance')
    if not os.path.exists(instance_dir):
        os.makedirs(instance_dir, exist_ok=True)
        print(f"✅ Created directory: {instance_dir}")
    else:
        print(f"✅ Directory already exists: {instance_dir}")

    # Determine the DB file path in instance
    db_file = os.path.join(instance_dir, 'taskforce.db')
    try:
        open(db_file, 'a', encoding='utf-8').close()
        print(f"✅ Ensured sqlite file exists: {db_file}")
    except Exception as e:
        print(f"⚠️ Warning: could not touch sqlite file {db_file}: {e}")
    # Compute sqlite_path for later use
    sqlite_path = db_file

    # Now import and create the Flask app (after filesystem is prepared)
    from app import create_app
    app = create_app()

    # If we computed an absolute db_file above, make SQLAlchemy use it (Windows-friendly)
    # Ensure the Flask app uses the instance DB absolute path
    abs_db_file = db_file
    abs_uri = 'sqlite:///' + abs_db_file.replace('\\', '/')
    app.config['SQLALCHEMY_DATABASE_URI'] = abs_uri
    print(f"[DEBUG] Overriding app.config['SQLALCHEMY_DATABASE_URI'] -> {abs_uri}")
    
    # Create all database tables
    with app.app_context():
        try:
            # Debug: show what SQLAlchemy will try to open
            current_uri = app.config.get('SQLALCHEMY_DATABASE_URI')
            print(f"[DEBUG] app.config['SQLALCHEMY_DATABASE_URI'] = {current_uri}")
            try:
                from sqlalchemy.engine import make_url
                print(f"[DEBUG] parsed database path = {make_url(current_uri).database}")
            except Exception:
                pass
            db.create_all()
            print("✅ Database tables created successfully!")
            
            # Check if we have any members
            from database.models import Member
            member_count = Member.query.count()
            print(f"✅ Current member count: {member_count}")
            
            if member_count == 0:
                print("\n💡 Tip: Run the app with 'flask run' or 'python app.py'")
                print("   Then visit http://localhost:5000 to add your first member!")
                
        except Exception as e:
            print(f"❌ Error creating database via Flask-SQLAlchemy: {e}")
            # Fallback: try to create tables using SQLAlchemy engine directly
            try:
                from sqlalchemy import create_engine
                print(f"[DEBUG] Attempting fallback using SQLAlchemy engine -> {abs_uri}")
                engine = create_engine(app.config.get('SQLALCHEMY_DATABASE_URI'))
                # Use the Flask-SQLAlchemy metadata object
                db.metadata.create_all(engine)
                print("✅ Database tables created successfully via SQLAlchemy engine fallback!")
            except Exception as e2:
                print(f"❌ Fallback also failed: {e2}")
                return False
    
    return True

def create_sample_data():
    """Create some sample data for testing (optional)"""
    from app import create_app
    app = create_app()
    
    with app.app_context():
        from database.models import Member, ActivityLog
        from datetime import datetime
        
        # Check if we already have data
        if Member.query.count() > 0:
            print("📊 Sample data already exists, skipping...")
            return
        
        # Create sample members
        sample_members = [
            Member(
                discord_username="Commander_Alpha",
                roblox_username="AlphaLeader",
                current_rank="Commander"
            ),
            Member(
                discord_username="Crusader_Beta", 
                roblox_username="BetaWarrior",
                current_rank="Crusader"
            ),
            Member(
                discord_username="Aspirant_Gamma",
                roblox_username="GammaNewbie", 
                current_rank="Aspirant"
            )
        ]
        
        for member in sample_members:
            db.session.add(member)
        
        db.session.commit()
        
        # Add some sample activities
        sample_activities = [
            ActivityLog(
                member_id=1,
                activity_type="Training",
                description="Completed advanced leadership training",
                logged_by="System"
            ),
            ActivityLog(
                member_id=2,
                activity_type="Operation", 
                description="Led successful patrol mission",
                logged_by="Commander_Alpha"
            ),
            ActivityLog(
                member_id=3,
                activity_type="Training",
                description="Completed basic training course",
                logged_by="Sergeant_Beta"
            )
        ]
        
        for activity in sample_activities:
            db.session.add(activity)
        
        db.session.commit()
        
        print("✅ Sample data created!")
        print("   - 3 sample members added")
        print("   - 3 sample activities logged")

if __name__ == "__main__":
    print("🚀 Setting up Taskforce Management System...")
    print("=" * 50)
    
    if setup_database():
        print("\n" + "=" * 50)
        print("✅ Setup completed successfully!")
        
        # Ask if user wants sample data
        if len(sys.argv) > 1 and sys.argv[1] == "--sample":
            print("\n📊 Creating sample data...")
            create_sample_data()
        
        print("\n🎯 Next steps:")
        print("1. Run: python app.py")
        print("2. Visit: http://localhost:5000")
        print("3. Start managing your taskforce!")
        
    else:
        print("\n❌ Setup failed. Please check the errors above.")
        sys.exit(1)