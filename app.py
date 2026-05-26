from flask import (
    Flask, render_template, request, flash, redirect, url_for, jsonify,
    send_file, session, current_app, Response, make_response
)
from config import Config
from database.models import db, Member, ActivityLog, PromotionLog, RankMapping
from database.ac_models import (
    ACPeriod,
    ActivityEntry,
    InactivityNotice,
    ACExemption,
    ACTIVITY_TYPES,
    AC_QUOTAS,
    get_member_quota,
    get_activity_points,
    is_limited_activity,
)
from utils.ac_reports import ACReportGenerator, send_discord_webhook
from utils.excel_reports import generate_ac_workbook_bytes, merge_into_uploaded_workbook_bytes
from utils.auth import staff_required, is_staff, check_password
from utils.roblox_sync import sync_member_to_roblox, add_member_to_roblox, remove_member_from_roblox, sync_from_roblox
from sqlalchemy import func
from datetime import datetime, timedelta
import os
import os.path as op
import secrets
from io import BytesIO

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Ensure SECRET_KEY
    if not app.config.get('SECRET_KEY'):
        app.config['SECRET_KEY'] = secrets.token_hex(32)

    # Session hardening (adjust as needed)
    app.config.update(
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE='Lax',
        PERMANENT_SESSION_LIFETIME=timedelta(hours=12)
    )

    # Initialize DB with configured database URI (supports any SQLAlchemy backend)
    db.init_app(app)

    # Log database backend info
    db_uri = app.config.get('SQLALCHEMY_DATABASE_URI', '')
    db_type = db_uri.split('://')[0] if '://' in db_uri else 'unknown'
    print(f"\n{'='*60}")
    print(f"📊 Database Configuration")
    print(f"   Backend: {db_type.upper()}")
    print(f"{'='*60}")

    # Set up background sync task if enabled
    sync_enabled = app.config.get('ROBLOX_SYNC_ENABLED', False)
    print(f"\n{'='*60}")
    print(f"🔍 Roblox Sync Status: {'✅ ENABLED' if sync_enabled else '❌ DISABLED'}")
    print(f"{'='*60}")
    
    # Set up background sync task if enabled (and specifically configured for background execution)
    sync_enabled = app.config.get('ROBLOX_SYNC_ENABLED', False)
    background_sync = app.config.get('ROBLOX_BACKGROUND_SYNC_ENABLED', False)
    if sync_enabled and background_sync:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.interval import IntervalTrigger
        
        scheduler = BackgroundScheduler()
        sync_interval = app.config.get('ROBLOX_SYNC_INTERVAL', 3600)  # Default 1 hour
        group_id = app.config.get('ROBLOX_GROUP_ID', 'Not set')
        has_cookie = bool(app.config.get('ROBLOX_COOKIE'))
        
        print(f"📊 Configuration:")
        print(f"   - Group ID: {group_id}")
        print(f"   - Cookie set: {'✅ Yes' if has_cookie else '❌ No'}")
        print(f"   - Sync interval: {sync_interval}s ({sync_interval // 60} minutes)")
        print()
        
        def sync_job():
            with app.app_context():
                try:
                    print(f"\n{'='*60}")
                    print(f"🔄 [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Starting automatic Roblox sync...")
                    print(f"{'='*60}")
                    app.logger.info("🔄 Starting automatic Roblox sync...")
                    
                    result = sync_from_roblox()
                    
                    if result.get('success'):
                        stats = result.get('stats', {})
                        message = (
                            f"✅ Roblox sync completed: {stats.get('added', 0)} added, "
                            f"{stats.get('updated', 0)} updated, {stats.get('rank_changes', 0)} rank changes"
                        )
                        print(message)
                        app.logger.info(message)
                    else:
                        error_msg = f"⚠️ Roblox sync failed: {result.get('message', 'Unknown error')}"
                        print(error_msg)
                        app.logger.warning(error_msg)
                except Exception as e:
                    error_msg = f"❌ Background Roblox sync error: {e}"
                    print(error_msg)
                    app.logger.error(error_msg, exc_info=True)
        
        # Add recurring sync job (every hour)
        scheduler.add_job(
            func=sync_job,
            trigger=IntervalTrigger(seconds=sync_interval),
            id='roblox_sync_job',
            name='Roblox Group Sync',
            replace_existing=True
        )
        
        scheduler.start()
        startup_msg = f"✅ Roblox sync scheduler started - will sync every {sync_interval}s ({sync_interval // 60} minutes)"
        print(startup_msg)
        app.logger.info(startup_msg)
        
        # Run initial sync after a short delay to let app fully start
        initial_run_time = datetime.now() + timedelta(seconds=5)
        scheduler.add_job(
            func=sync_job,
            trigger='date',
            run_date=initial_run_time,
            id='roblox_sync_initial',
            name='Initial Roblox Sync',
            replace_existing=True
        )
        initial_msg = "🔄 Initial sync scheduled (will run in 5 seconds)"
        print(initial_msg)
        app.logger.info(initial_msg)
        
        # --- Add Member Stats Job (Daily) ---
        from utils.stats_logger import capture_member_stats
        
        def stats_job():
            with app.app_context():
                print(f"\n📊 [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Capturing member statistics...")
                capture_member_stats()
        
        scheduler.add_job(
            func=stats_job,
            trigger='cron',
            hour=0,  # Run at midnight
            minute=0,
            id='member_stats_job',
            name='Daily Member Stats',
            replace_existing=True
        )
        print("📈 Daily member stats job scheduled for midnight")
        # ------------------------------------
        
        print(f"{'='*60}\n")
    elif sync_enabled and not background_sync:
        print("⚠️  Roblox Sync is ENABLED but Background Scheduler is DISABLED")
        print("   To enable background sync, set ROBLOX_BACKGROUND_SYNC_ENABLED=true in your .env file")
        print(f"{'='*60}\n")
    else:
        print("⚠️  Auto-sync is DISABLED")
        print("   To enable, set ROBLOX_SYNC_ENABLED=true in your .env file")
        print(f"{'='*60}\n")

    # inject helpful template globals
    @app.context_processor
    def inject_globals():
        return dict(is_staff=is_staff())
    
    # Register Discord Bot API
    from api.discord_bot_api import api_bp
    app.register_blueprint(api_bp, url_prefix='/api/v1')
    
    # Register Mission Tracking API
    from routers.missions import missions_bp
    app.register_blueprint(missions_bp, url_prefix='/api/v1/missions')

    return app


app = create_app()

# ========== REGISTER BLUEPRINTS ==========
# Import and register all routers

from routers.auth import auth_bp
from routers.public import public_bp
from routers.members import members_bp
from routers.ac import ac_bp
from routers.sync import sync_bp
from routers.missions import missions_bp

# Register blueprints
app.register_blueprint(auth_bp)
app.register_blueprint(public_bp)
app.register_blueprint(members_bp)
app.register_blueprint(ac_bp, url_prefix='/ac')
app.register_blueprint(sync_bp)

# Backwards-compatible alias: some templates expect endpoint name 'log_activity'
# This maps the old endpoint to the new blueprint endpoint
try:
    from routers.ac import log_ac_activity
    app.add_url_rule('/ac/log_activity', endpoint='log_activity', view_func=log_ac_activity, methods=['GET', 'POST'])
except Exception:
    # If app not ready or rule exists, ignore
    pass


if __name__ == '__main__':
    # use 0.0.0.0 if you want external access
    app.run(debug=True)


# Global exception handler to log unexpected errors (helps debugging production 500s)
@app.errorhandler(Exception)
def handle_exception(e):
    import traceback
    tb = traceback.format_exc()
    try:
        app.logger.error('Unhandled exception:\n%s', tb)
        with open('app_errors.log', 'a', encoding='utf-8') as fh:
            fh.write(tb + '\n' + ('-'*80) + '\n')
    except Exception:
        pass
    # Always log and return a 500 page; the interactive debugger is still available when running locally
    return render_template('500.html'), 500
