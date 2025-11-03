#!/usr/bin/env python3
"""
Setup script for Taskforce Management System
Run this once to initialize the database and create necessary directories
"""
import os
import sys

from config import Config

def setup_database():
    """Initialize the database and create all tables"""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    instance_dir = os.path.join(base_dir, 'instance')
    os.makedirs(instance_dir, exist_ok=True)
    print(f"✅ Instance directory ready: {instance_dir}")

    db_file = os.path.join(instance_dir, 'taskforce.db')
    db_uri = f"sqlite:///{db_file.replace('\\', '/')}"

    # Import app after setting up folders to avoid DB-open on import problems
    from app import create_app
    from database.models import db

    app = create_app()
    # override configured DB URI with instance path for setup
    app.config['SQLALCHEMY_DATABASE_URI'] = db_uri

    # Create DB tables
    with app.app_context():
        try:
            db.create_all()
            print("✅ Database tables created successfully!")
            # quick sanity check
            try:
                from database.models import Member
                print(f"✅ Member table rows: {Member.query.count()}")
            except Exception:
                pass
        except Exception as e:
            print(f"❌ Error creating database tables: {e}")
            return False

    return True

def create_sample_data():
    """Optional: create sample data"""
    from app import create_app
    app = create_app()
    with app.app_context():
        from database.models import db, Member, ActivityLog
        from datetime import datetime
        if Member.query.count() > 0:
            print("Sample data exists, skipping.")
            return
        sample_members = [
            Member(discord_username="Commander_Alpha", roblox_username="AlphaLeader", current_rank="Commander"),
            Member(discord_username="Marshall_Beta", roblox_username="BetaMarshall", current_rank="Marshall"),
            Member(discord_username="Aspirant_Gamma", roblox_username="GammaNewbie", current_rank="Aspirant"),
        ]
        for m in sample_members:
            db.session.add(m)
        db.session.commit()
        print("✅ Sample members created")

if __name__ == "__main__":
    print("🚀 Setting up Taskforce Management System...")
    ok = setup_database()
    if not ok:
        print("Setup failed")
        sys.exit(1)
    if len(sys.argv) > 1 and sys.argv[1] == "--sample":
        create_sample_data()
    print("✅ Setup finished")