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

    # Normalize sqlite path: prefer instance/taskforce.db
    uri = app.config.get('SQLALCHEMY_DATABASE_URI', '') or ''
    base_dir = op.dirname(op.abspath(__file__))
    instance_dir = op.join(base_dir, 'instance')
    os.makedirs(instance_dir, exist_ok=True)

    db_file = None
    if uri.startswith('sqlite:///'):
        # if configured, use it but ensure directory exists
        db_path = uri.replace('sqlite:///', '')
        if not op.isabs(db_path):
            db_path = op.join(app.root_path, db_path)
        db_dir = op.dirname(db_path)
        if db_dir and not op.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)
        db_file = db_path
    else:
        # default to instance/taskforce.db
        db_file = op.join(instance_dir, 'taskforce.db')

    # ensure file exists (touch) and normalize for SQLAlchemy
    try:
        open(db_file, 'a').close()
    except Exception:
        pass
    norm = db_file.replace('\\', '/')
    app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{norm}"

    # Initialize DB
    db.init_app(app)

    # Create tables if missing
    with app.app_context():
        db.create_all()

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

    return app

app = create_app()

# ========== AUTH ROUTES ==========

@app.route('/staff/login', methods=['GET', 'POST'])
def staff_login():
    # Support form POST and JSON POST for API/AJAX callers
    if request.method == 'POST':
        password = ''
        if request.is_json:
            try:
                data = request.get_json(silent=True) or {}
                password = data.get('password', '')
            except Exception:
                password = ''
        else:
            password = request.form.get('password', '')

        if check_password(password):
            session['is_staff'] = True
            session['staff_username'] = 'staff'
            # do not make session permanent — avoid persistent login cookies
            session.permanent = False

            # If AJAX/JSON request, return JSON success
            if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.accept_mimetypes.accept_json:
                next_url = session.pop('next_url', None)

                flash('Staff login successful', 'success')
                next_url = session.pop('next_url', None)
                return redirect(next_url or url_for('dashboard'))

        # Invalid password
        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.accept_mimetypes.accept_json:
            return jsonify({'error': 'authentication_failed'}), 401
        flash('Invalid password', 'error')

    return render_template('staff_login.html')

@app.route('/staff/logout')
def staff_logout():
    session.clear()
    flash('Logged out', 'info')
    return redirect(url_for('public_roster'))

# ========== PUBLIC VIEW ==========

@app.route('/')
def public_roster():
    search = request.args.get('search', '')
    query = Member.query.filter_by(is_active=True)
    if search:
        s = f"%{search}%"
        query = query.filter(
            (Member.discord_username.ilike(s)) |
            (Member.roblox_username.ilike(s)) |
            (Member.current_rank.ilike(s))
        )
    members = query.order_by(Member.current_rank, Member.discord_username).all()
    return render_template('public_roster.html', members=members, search=search)

@app.route('/public/member/<int:member_id>')
def public_member(member_id):
    """Public read-only member view (limited data)"""
    member = Member.query.get_or_404(member_id)
    # limit data for public view: basic profile + recent non-sensitive activities
    recent_activities = ActivityEntry.query.filter_by(member_id=member_id).order_by(ActivityEntry.activity_date.desc()).limit(5).all()
    # do not include internal IA notices or editable controls
    return render_template('public_member.html',
                           member=member,
                           recent_activities=recent_activities)

# ========== STAFF DASHBOARD & MANAGEMENT (protected) ==========

@app.route('/dashboard')
@staff_required
def dashboard():
    member_count = Member.query.filter_by(is_active=True).count()
    recent_activities = ActivityLog.query.order_by(ActivityLog.log_date.desc()).limit(5).all()
    return render_template('dashboard.html',
                           member_count=member_count,
                           recent_activities=recent_activities)

# Members list / CRUD
@app.route('/members')
@staff_required
def members():
    search = request.args.get('search', '')
    query = Member.query.filter_by(is_active=True)
    if search:
        s = f"%{search}%"
        query = query.filter(
            (Member.discord_username.ilike(s)) |
            (Member.roblox_username.ilike(s)) |
            (Member.current_rank.ilike(s))
        )
    members_list = query.order_by(Member.current_rank, Member.discord_username).all()
    return render_template('members.html', members=members_list, search=search)

@app.route('/member/<int:member_id>')
@staff_required
def member_detail(member_id):
    member = Member.query.get_or_404(member_id)
    activities = ActivityLog.query.filter_by(member_id=member_id).order_by(ActivityLog.log_date.desc()).all()
    promotions = PromotionLog.query.filter_by(member_id=member_id).order_by(PromotionLog.promotion_date.desc()).all()
    return render_template('member_detail.html', member=member, activities=activities, promotions=promotions)

@app.route('/add_member', methods=['GET', 'POST'])
@staff_required
def add_member():
    if request.method == 'POST':
        discord_username = request.form.get('discord_username', '').strip()
        roblox_username = request.form.get('roblox_username', '').strip() or None
        current_rank = request.form.get('current_rank', 'Aspirant').strip()

        if not discord_username:
            flash('Discord username is required', 'error')
            return redirect(url_for('add_member'))

        existing = Member.query.filter_by(discord_username=discord_username).first()
        if existing:
            flash('Member with this Discord username already exists!', 'error')
            return redirect(url_for('add_member'))

        m = Member(discord_username=discord_username, roblox_username=roblox_username, current_rank=current_rank)
        db.session.add(m)
        db.session.commit()
        
        # Sync to Roblox if enabled and member has Roblox username
        if current_app.config.get('ROBLOX_SYNC_ENABLED') and m.roblox_username:
            result = add_member_to_roblox(m)
            if not result['success']:
                flash(f"Member added, but Roblox sync failed: {result['message']}", 'warning')
        
        flash('Member added', 'success')
        return redirect(url_for('member_detail', member_id=m.id))
    return render_template('add_member.html')

@app.route('/member/<int:member_id>/edit', methods=['GET', 'POST'])
@staff_required
def edit_member(member_id):
    member = Member.query.get_or_404(member_id)
    
    # Get available ranks from RankMapping, or use default list
    rank_mappings = RankMapping.query.filter_by(is_active=True).order_by(RankMapping.system_rank).all()
    if rank_mappings:
        available_ranks = [mapping.system_rank for mapping in rank_mappings]
    else:
        # Fallback to default ranks if no mappings exist
        available_ranks = ['Aspirant', 'Novice', 'Adept', 'Crusader', 'Paladin', 
                          'Exemplar', 'Prospect', 'Commander', 'Marshal', 'General', 'Chief General']
    
    if request.method == 'POST':
        old_rank = member.current_rank
        member.discord_username = request.form.get('discord_username', member.discord_username).strip()
        member.roblox_username = request.form.get('roblox_username', member.roblox_username).strip() or None
        member.current_rank = request.form.get('current_rank', member.current_rank).strip()
        member.last_updated = datetime.utcnow()
        db.session.commit()
        
        # Sync to Roblox if enabled and rank changed
        sync_enabled = current_app.config.get('ROBLOX_SYNC_ENABLED', False)
        rank_changed = old_rank != member.current_rank
        has_roblox_id = bool(member.roblox_id)
        
        current_app.logger.info(f"Edit member: sync_enabled={sync_enabled}, rank_changed={rank_changed}, has_roblox_id={has_roblox_id}")
        
        if sync_enabled and rank_changed and has_roblox_id:
            current_app.logger.info(f"Syncing {member.discord_username} rank change: {old_rank} -> {member.current_rank}")
            result = sync_member_to_roblox(member)
            if not result['success']:
                error_msg = f"Member updated, but Roblox sync failed: {result['message']}"
                current_app.logger.error(error_msg)
                flash(error_msg, 'warning')
            else:
                current_app.logger.info(f"Successfully synced {member.discord_username} to Roblox")
        elif sync_enabled and rank_changed and not has_roblox_id:
            current_app.logger.warning(f"Cannot sync {member.discord_username} - no Roblox ID set")
            flash('Member updated, but cannot sync to Roblox (no Roblox ID)', 'warning')
        elif not sync_enabled:
            current_app.logger.debug(f"Roblox sync is disabled - skipping sync for {member.discord_username}")
        
        flash('Member updated', 'success')
        return redirect(url_for('member_detail', member_id=member.id))
    return render_template('edit_member.html', member=member, available_ranks=available_ranks)

@app.route('/member/<int:member_id>/delete', methods=['POST'])
@staff_required
def delete_member(member_id):
    member = Member.query.get_or_404(member_id)
    
    # Sync removal to Roblox if enabled
    if current_app.config.get('ROBLOX_SYNC_ENABLED') and member.roblox_id:
        result = remove_member_from_roblox(member)
        if not result['success']:
            flash(f"Member removed from system, but Roblox sync failed: {result['message']}", 'warning')
    
    member.is_active = False
    member.last_updated = datetime.utcnow()
    db.session.commit()
    flash('Member removed', 'success')
    return redirect(url_for('members'))

# ========== ACTIVITY CHECK (AC) ROUTES ==========

def _members_with_quota_query():
    """Return members that have a quota (exclude General/Chief General). Case-insensitive."""
    excluded = {'general', 'chief general'}
    # get ranks that have quota > 0
    allowed = [r.lower() for r, q in AC_QUOTAS.items() if q and q > 0 and r.lower() not in excluded]
    return Member.query.filter(
        Member.is_active == True,
        func.lower(Member.current_rank).in_(allowed)
    ).order_by(func.lower(Member.current_rank), Member.discord_username)

# replace the member_progress building loop in /ac route with this aggregated version
@app.route('/ac')
@staff_required
def ac_dashboard():
    current_period = ACPeriod.query.filter_by(is_active=True).first()
    if not current_period:
        return render_template('ac/ac_setup.html')

    # Get overall activity stats
    activity_stats = db.session.query(
        ActivityEntry.activity_type,
        db.func.count(ActivityEntry.id).label('count'),
        db.func.sum(ActivityEntry.points).label('total_points')
    ).filter_by(
        ac_period_id=current_period.id
    ).group_by(ActivityEntry.activity_type).all()

    # Convert to dict for template
    activity_stats = {
        type_: {
            'count': count,
            'total_points': float(total_points or 0)
        }
        for type_, count, total_points in activity_stats
    }

    member_progress = []
    for m in _members_with_quota_query().all():
        quota = get_member_quota(m.current_rank) or 0
        if not quota:
            continue

        # Get member's activity summary
        member_activities = db.session.query(
            ActivityEntry.activity_type,
            db.func.count(ActivityEntry.id),
            db.func.sum(ActivityEntry.points)
        ).filter_by(
            member_id=m.id,
            ac_period_id=current_period.id
        ).group_by(ActivityEntry.activity_type).all()

        activity_summary = {
            type_: {'count': count, 'points': float(points or 0)}
            for type_, count, points in member_activities
        }

        total_points = sum(stat['points'] for stat in activity_summary.values())
        
        ia_notice = InactivityNotice.query.filter_by(
            member_id=m.id,
            ac_period_id=current_period.id
        ).first()

        exemption = ACExemption.query.filter_by(
            member_id=m.id,
            ac_period_id=current_period.id
        ).first()

        # Determine status and percentage
        if exemption:
            status = 'Exempt'
            pct = 100.0  # Show as 100% for exempt members
        elif ia_notice:
            status = 'Protected (IA)'
            pct = 100.0  # Show as 100% for IA members
        elif total_points >= quota:
            status = 'Passed'
            pct = min(100.0, (total_points / quota) * 100.0) if quota > 0 else 0.0
        else:
            status = 'In Progress'
            pct = min(100.0, (total_points / quota) * 100.0) if quota > 0 else 0.0

        progress = {
            'member': m,
            'quota': quota,
            'points': total_points,
            'percentage': pct,
            'status': status,
            'is_protected': bool(ia_notice),
            'is_exempt': bool(exemption),
            'activity_summary': activity_summary
        }
        member_progress.append(progress)

    # Sort: Exempt first, then IA protected, then by percentage
    member_progress.sort(key=lambda x: (100 if x['is_exempt'] else (99 if x['is_protected'] else x['percentage'])))

    # Calculate title rewards for quick display
    all_activities = ActivityEntry.query.filter_by(ac_period_id=current_period.id).all()
    title_winners = calculate_title_rewards(all_activities, current_period)
    
    return render_template('ac/ac_dashboard.html',
                         current_period=current_period,
                         member_progress=member_progress,
                         activity_types=ACTIVITY_TYPES,
                         activity_stats=activity_stats,
                         title_winners=title_winners)

@app.route('/ac/create_period', methods=['GET', 'POST'])
@staff_required
def create_ac_period():
    if request.method == 'POST':
        period_name = request.form.get('period_name', '').strip()
        start_date = datetime.strptime(request.form.get('start_date'), '%Y-%m-%d')
        end_date = datetime.strptime(request.form.get('end_date'), '%Y-%m-%d') if request.form.get('end_date') else (start_date + timedelta(weeks=2) - timedelta(days=1))
        # deactivate current
        ACPeriod.query.filter_by(is_active=True).update({'is_active': False})
        newp = ACPeriod(period_name=period_name, start_date=start_date, end_date=end_date, is_active=True)
        db.session.add(newp)
        db.session.commit()
        flash('AC period created', 'success')
        return redirect(url_for('ac_dashboard'))
    return render_template('ac/create_period.html')

@app.route('/ac/edit_period', methods=['GET', 'POST'])
@staff_required
def edit_ac_period():
    current_period = ACPeriod.query.filter_by(is_active=True).first()
    if not current_period:
        flash('No active AC period', 'error')
        return redirect(url_for('ac_dashboard'))
    
    if request.method == 'POST':
        period_name = request.form.get('period_name', '').strip()
        if period_name:
            current_period.period_name = period_name
            db.session.commit()
            flash('Period name updated', 'success')
            return redirect(url_for('ac_dashboard'))
        else:
            flash('Period name cannot be empty', 'error')
    
    return render_template('ac/edit_period.html', period=current_period)

@app.route('/ac/clear_all_activities', methods=['POST'])
@staff_required
def clear_all_activities():
    """Clear all activities for all members in the current period"""
    current_period = ACPeriod.query.filter_by(is_active=True).first()
    if not current_period:
        flash('No active AC period', 'error')
        return redirect(url_for('ac_dashboard'))
    
    # Delete all activity entries for the current period
    deleted_count = ActivityEntry.query.filter_by(ac_period_id=current_period.id).delete()
    db.session.commit()
    
    flash(f'Cleared {deleted_count} activity entries for all members', 'success')
    return redirect(url_for('ac_dashboard'))

@app.route('/ac/title_rewards')
@staff_required
def title_rewards():
    """Display title rewards for the current AC period"""
    current_period = ACPeriod.query.filter_by(is_active=True).first()
    if not current_period:
        flash('No active AC period', 'error')
        return redirect(url_for('ac_dashboard'))
    
    # Get all activities for the current period
    all_activities = ActivityEntry.query.filter_by(ac_period_id=current_period.id).all()
    
    # Calculate title rewards
    titles = calculate_title_rewards(all_activities, current_period)
    
    # Generate Discord message
    discord_message = generate_title_discord_message(titles, current_period)
    
    return render_template('ac/title_rewards.html',
                         current_period=current_period,
                         titles=titles,
                         discord_message=discord_message)

@app.route('/ac/send_title_webhook', methods=['POST'])
@staff_required
def send_title_webhook():
    """Send title rewards message to Discord webhook"""
    webhook_url = request.form.get('webhook_url', '').strip()
    message = request.form.get('message', '').strip()
    
    if not webhook_url or not message:
        flash('Webhook URL and message are required', 'error')
        return redirect(url_for('title_rewards'))
    
    current_period = ACPeriod.query.filter_by(is_active=True).first()
    period_name = current_period.period_name if current_period else 'Current Period'
    
    success = send_discord_webhook(webhook_url, message, f"Title Rewards - {period_name}")
    
    if success:
        flash('Title rewards sent to Discord successfully!', 'success')
    else:
        flash('Failed to send to Discord. Please check your webhook URL.', 'error')
    
    return redirect(url_for('title_rewards'))

def calculate_title_rewards(all_activities, period):
    """
    Calculate title reward winners based on activity counts for the current period.
    Returns dict of title winners.
    """
    # Count activities by type for each member
    member_stats = {}
    
    for activity in all_activities:
        member_id = activity.member_id
        member = activity.member
        activity_type = activity.activity_type
        
        if member_id not in member_stats:
            member_stats[member_id] = {
                'name': member.discord_username,
                'events': 0,  # Training + Raid + Patrol for HWTM
                'missions': 0,
                'raids': 0,
                'patrols': 0,
                'tryouts': 0
            }
        
        # Track specific activity types
        if activity_type == 'Raid':
            member_stats[member_id]['raids'] += 1
            member_stats[member_id]['events'] += 1  # Events = Training + Raid + Patrol
        elif activity_type == 'Patrol':
            member_stats[member_id]['patrols'] += 1
            member_stats[member_id]['events'] += 1  # Events = Training + Raid + Patrol
        elif activity_type == 'Training':
            member_stats[member_id]['events'] += 1  # Events = Training + Raid + Patrol
        elif activity_type == 'Mission':
            member_stats[member_id]['missions'] += 1
        elif activity_type == 'Tryout':
            member_stats[member_id]['tryouts'] += 1
    
    # Calculate winners - always show all titles, even if no one meets minimum
    titles = {}
    
    # Host with the Most (most events = Training + Raid + Patrol, min 5)
    if member_stats:
        event_leaders = [(mid, stats['events'], stats['name']) 
                        for mid, stats in member_stats.items() 
                        if stats['events'] > 0]
        if event_leaders:
            winner = max(event_leaders, key=lambda x: x[1])
            meets_minimum = winner[1] >= 5
            titles['Host with the Most'] = {
                'winner': winner[2] if meets_minimum else f"{winner[2]} (Not Qualified)",
                'count': winner[1],
                'requirement': '5+ events hosted (Training + Raid + Patrol)',
                'qualified': meets_minimum
            }
        else:
            titles['Host with the Most'] = {
                'winner': 'No participants',
                'count': 0,
                'requirement': '5+ events hosted (Training + Raid + Patrol)',
                'qualified': False
            }
    
    # Taskmaster (most missions, min 5)
    if member_stats:
        mission_leaders = [(mid, stats['missions'], stats['name']) 
                          for mid, stats in member_stats.items() 
                          if stats['missions'] > 0]
        if mission_leaders:
            winner = max(mission_leaders, key=lambda x: x[1])
            meets_minimum = winner[1] >= 5
            titles['Taskmaster'] = {
                'winner': winner[2] if meets_minimum else f"{winner[2]} (Not Qualified)",
                'count': winner[1],
                'requirement': '5+ missions posted',
                'qualified': meets_minimum
            }
        else:
            titles['Taskmaster'] = {
                'winner': 'No participants',
                'count': 0,
                'requirement': '5+ missions posted',
                'qualified': False
            }
    
    # Legionnaire (most raids, min 5)
    if member_stats:
        raid_leaders = [(mid, stats['raids'], stats['name']) 
                       for mid, stats in member_stats.items() 
                       if stats['raids'] > 0]
        if raid_leaders:
            winner = max(raid_leaders, key=lambda x: x[1])
            meets_minimum = winner[1] >= 5
            titles['Legionnaire'] = {
                'winner': winner[2] if meets_minimum else f"{winner[2]} (Not Qualified)",
                'count': winner[1],
                'requirement': '5+ raids hosted',
                'qualified': meets_minimum
            }
        else:
            titles['Legionnaire'] = {
                'winner': 'No participants',
                'count': 0,
                'requirement': '5+ raids hosted',
                'qualified': False
            }
    
    # Scout (most tryouts, min 5)
    if member_stats:
        tryout_leaders = [(mid, stats['tryouts'], stats['name']) 
                         for mid, stats in member_stats.items() 
                         if stats['tryouts'] > 0]
        if tryout_leaders:
            winner = max(tryout_leaders, key=lambda x: x[1])
            meets_minimum = winner[1] >= 5
            titles['Scout'] = {
                'winner': winner[2] if meets_minimum else f"{winner[2]} (Not Qualified)",
                'count': winner[1],
                'requirement': '5+ tryouts hosted',
                'qualified': meets_minimum
            }
        else:
            titles['Scout'] = {
                'winner': 'No participants',
                'count': 0,
                'requirement': '5+ tryouts hosted',
                'qualified': False
            }
    
    return titles

def generate_title_discord_message(titles, period):
    """Generate Discord message for title winners (only qualified)"""
    qualified_titles = {k: v for k, v in titles.items() if v.get('qualified', False)}
    
    if not qualified_titles:
        return "No title winners this cycle (minimum requirements not met)."
    
    message = f"🏆 **Title Rewards - {period.period_name}** 🏆\n\n"
    
    for title, info in qualified_titles.items():
        message += f"**@{title}**\n"
        message += f"👑 Winner: **{info['winner']}**\n"
        message += f"📊 Achievement: {info['count']} ({info['requirement']})\n\n"
    
    return message

@app.route('/ac/log_activity', methods=['GET', 'POST'])
@staff_required
def log_ac_activity():
    current_period = ACPeriod.query.filter_by(is_active=True).first()
    if not current_period:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': 'no_active_period'}), 400
        flash('No active AC period. Please create one first.', 'error')
        return redirect(url_for('ac_dashboard'))

    if request.method == 'POST':
        data = request.get_json(silent=True) or request.form
        member_id = data.get('member_id')
        activity_type = data.get('activity_type')
        description = data.get('description')
        activity_date = datetime.strptime(data.get('activity_date'), '%Y-%m-%d')
        logged_by = data.get('logged_by') or 'HC Team'
        points = get_activity_points(activity_type)

        if is_limited_activity(activity_type):
            existing = ActivityEntry.query.filter_by(
                member_id=member_id,
                ac_period_id=current_period.id,
                activity_type=activity_type
            ).first()
            if existing:
                flash('Limited activity already logged for this period', 'error')
                return redirect(url_for('log_ac_activity'))

        ae = ActivityEntry(
            member_id=member_id,
            ac_period_id=current_period.id,
            activity_type=activity_type,
            points=points,
            description=description,
            activity_date=activity_date,
            logged_by=logged_by
        )
        db.session.add(ae)
        db.session.commit()

        # If AJAX, return JSON success (avoid redirect)
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json:
            return jsonify({'success': True, 'activity_id': ae.id}), 200

        flash('Activity logged successfully', 'success')
        return redirect(url_for('ac_dashboard'))

    # GET: render form/page
    members_with_quota = _members_with_quota_query().all()
    return render_template('ac/log_activity.html',
                           members=members_with_quota,
                           activity_types=ACTIVITY_TYPES,
                           current_period=current_period)

# Backwards-compatible alias: some templates expect endpoint name 'log_activity'
try:
    app.add_url_rule('/ac/log_activity', endpoint='log_activity', view_func=log_ac_activity, methods=['GET', 'POST'])
except Exception:
    # If app not ready or rule exists, ignore
    pass

@app.route('/ac/quick_log', methods=['GET'])
@staff_required
def quick_log():
    current_period = ACPeriod.query.filter_by(is_active=True).first()
    if not current_period:
        flash('No active AC period. Please create one first.', 'error')
        return redirect(url_for('ac_dashboard'))

    members_with_quota = _members_with_quota_query().all()
    
    # Get activities and counts per member
    member_activities = {}
    member_activity_counts = {}
    member_ia_status = {}
    member_exempt_status = {}
    
    for member in members_with_quota:
        # Get recent activities for display
        recent = ActivityEntry.query.filter_by(
            member_id=member.id,
            ac_period_id=current_period.id
        ).order_by(ActivityEntry.activity_date.desc()).limit(3).all()
        member_activities[member.id] = recent
        
        # Get activity counts per type for this member
        counts = db.session.query(
            ActivityEntry.activity_type,
            db.func.count(ActivityEntry.id)
        ).filter_by(
            member_id=member.id,
            ac_period_id=current_period.id
        ).group_by(ActivityEntry.activity_type).all()
        
        member_activity_counts[member.id] = dict(counts)
        
        # Check IA status
        ia_notice = InactivityNotice.query.filter_by(
            member_id=member.id,
            ac_period_id=current_period.id
        ).first()
        member_ia_status[member.id] = bool(ia_notice)
        
        # Check exempt status
        exemption = ACExemption.query.filter_by(
            member_id=member.id,
            ac_period_id=current_period.id
        ).first()
        member_exempt_status[member.id] = bool(exemption)

    return render_template('ac/ac_quick_log.html',
                         members=members_with_quota,
                         activity_types=ACTIVITY_TYPES,
                         current_period=current_period,
                         today=datetime.utcnow().strftime('%Y-%m-%d'),
                         member_activities=member_activities,
                         member_activity_counts=member_activity_counts,
                         member_ia_status=member_ia_status,
                         member_exempt_status=member_exempt_status)

@app.route('/ac/quick_log_activity', methods=['POST'])
@staff_required
def quick_log_activity():
    """
    Accept JSON {member_id, activity_type, activity_date, logged_by}
    Returns JSON {success, message, points} or error.
    """
    data = request.get_json(force=True, silent=True) or {}
    member_id = data.get('member_id')
    activity_type = data.get('activity_type')
    if not member_id or not activity_type:
        return jsonify({'success': False, 'message': 'member_id and activity_type required'}), 400

    current_period = ACPeriod.query.filter_by(is_active=True).first()
    if not current_period:
        return jsonify({'success': False, 'message': 'No active AC period'}), 400

    # parse date
    activity_date = None
    if data.get('activity_date'):
        try:
            activity_date = datetime.strptime(data.get('activity_date'), '%Y-%m-%d')
        except Exception:
            activity_date = datetime.utcnow()

    logged_by = data.get('logged_by', 'HC Team')
    points = get_activity_points(activity_type)

    # enforce limited-activity rule
    if is_limited_activity(activity_type):
        existing = ActivityEntry.query.filter_by(member_id=member_id, ac_period_id=current_period.id, activity_type=activity_type).first()
        if existing:
            return jsonify({'success': False, 'message': 'Limited activity already logged for this period'}), 400

    ae = ActivityEntry(
        member_id=member_id,
        ac_period_id=current_period.id,
        activity_type=activity_type,
        points=points,
        description=data.get('description'),
        activity_date=activity_date or datetime.utcnow(),
        logged_by=logged_by,
        is_limited_activity=is_limited_activity(activity_type)
    )
    db.session.add(ae)
    db.session.commit()
    return jsonify({'success': True, 'points': points})

@app.route('/ac/quick_log_ia', methods=['POST'])
@staff_required
def quick_log_ia():
    """
    Toggle IA status for a member in the current period.
    Accept JSON {member_id, reason, approved_by}
    Returns JSON {success, message, is_ia}
    """
    data = request.get_json(force=True, silent=True) or {}
    member_id = data.get('member_id')
    if not member_id:
        return jsonify({'success': False, 'message': 'member_id required'}), 400

    current_period = ACPeriod.query.filter_by(is_active=True).first()
    if not current_period:
        return jsonify({'success': False, 'message': 'No active AC period'}), 400

    # Check if IA already exists
    ia_notice = InactivityNotice.query.filter_by(
        member_id=member_id,
        ac_period_id=current_period.id
    ).first()

    if ia_notice:
        # Remove IA
        db.session.delete(ia_notice)
        db.session.commit()
        return jsonify({'success': True, 'is_ia': False, 'message': 'IA removed'})
    else:
        # Create IA - use period dates as default
        reason = data.get('reason', 'Quick log IA')
        approved_by = data.get('approved_by', session.get('staff_username', 'HC Team'))
        
        ia_notice = InactivityNotice(
            member_id=member_id,
            ac_period_id=current_period.id,
            start_date=current_period.start_date,
            end_date=current_period.end_date,
            reason=reason,
            approved_by=approved_by,
            protects_ac=True
        )
        db.session.add(ia_notice)
        db.session.commit()
        return jsonify({'success': True, 'is_ia': True, 'message': 'IA set'})

@app.route('/ac/quick_log_exempt', methods=['POST'])
@staff_required
def quick_log_exempt():
    """
    Toggle Exempt status for a member in the current period.
    Accept JSON {member_id, reason, approved_by}
    Returns JSON {success, message, is_exempt}
    """
    data = request.get_json(force=True, silent=True) or {}
    member_id = data.get('member_id')
    if not member_id:
        return jsonify({'success': False, 'message': 'member_id required'}), 400

    current_period = ACPeriod.query.filter_by(is_active=True).first()
    if not current_period:
        return jsonify({'success': False, 'message': 'No active AC period'}), 400

    # Check if exemption already exists
    exemption = ACExemption.query.filter_by(
        member_id=member_id,
        ac_period_id=current_period.id
    ).first()

    if exemption:
        # Remove exemption
        db.session.delete(exemption)
        db.session.commit()
        return jsonify({'success': True, 'is_exempt': False, 'message': 'Exemption removed'})
    else:
        # Create exemption
        reason = data.get('reason', 'Quick log exemption')
        approved_by = data.get('approved_by', session.get('staff_username', 'HC Team'))
        
        exemption = ACExemption(
            member_id=member_id,
            ac_period_id=current_period.id,
            reason=reason,
            approved_by=approved_by
        )
        db.session.add(exemption)
        db.session.commit()
        return jsonify({'success': True, 'is_exempt': True, 'message': 'Exemption set'})

# Export AC to Excel (GET: new workbook; POST: merge uploaded workbook)
@app.route('/ac/export_excel', methods=['GET', 'POST'])
@staff_required
def export_ac_excel():
    period_id = request.args.get('period_id', None, type=int)
    if request.method == 'POST' and 'workbook' in request.files:
        uploaded = request.files['workbook']
        if uploaded.filename == '':
            flash('No workbook uploaded', 'error')
            return redirect(url_for('ac_dashboard'))
        merged_io, filename = merge_into_uploaded_workbook_bytes(uploaded.stream, period_id=period_id)
        return send_file(merged_io, as_attachment=True, download_name=filename, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    out_io, filename = generate_ac_workbook_bytes(period_id=period_id)
    return send_file(out_io, as_attachment=True, download_name=filename, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

# replace ac_member_detail route with aggregation + detailed list (keeps delete buttons for staff)
@app.route('/ac/member/<int:member_id>')
@staff_required
def ac_member_detail(member_id):
    member = Member.query.get_or_404(member_id)
    current_period = ACPeriod.query.filter_by(is_active=True).first()
    if not current_period:
        flash('No active AC period.', 'error')
        return redirect(url_for('ac_dashboard'))

    # all activities for the member in current period
    activities = ActivityEntry.query.filter_by(member_id=member_id, ac_period_id=current_period.id).order_by(ActivityEntry.activity_date.desc()).all()

    # aggregated summaries by (activity_type, points)
    agg = {}
    for a in activities:
        key = (a.activity_type, a.points)
        if key not in agg:
            agg[key] = {'count': 0, 'last_date': a.activity_date}
        agg[key]['count'] += 1
        if a.activity_date and a.activity_date > agg[key]['last_date']:
            agg[key]['last_date'] = a.activity_date

    aggregated_activities = sorted(
        (
            {'activity_type': k[0], 'points': k[1], 'count': v['count'], 'activity_date': v['last_date']}
            for k, v in agg.items()
        ),
        key=lambda x: x['activity_date'] or datetime.min,
        reverse=True
    )

    quota = get_member_quota(member.current_rank)
    total_points = sum(a.points for a in activities)

    return render_template(
        'ac/member_detail.html',
        member=member,
        current_period=current_period,
        activities=activities,  # full list for detailed view
        aggregated_activities=aggregated_activities,  # summaries for compact view
        quota=quota,
        total_points=total_points
    )

@app.route('/promote_member', methods=['GET', 'POST'])
@staff_required
def promote_member():
    """Promote a member and record a PromotionLog"""
    # Get available ranks from RankMapping, or use default list
    rank_mappings = RankMapping.query.filter_by(is_active=True).order_by(RankMapping.system_rank).all()
    if rank_mappings:
        available_ranks = [mapping.system_rank for mapping in rank_mappings]
    else:
        # Fallback to default ranks if no mappings exist
        available_ranks = ['Aspirant', 'Novice', 'Adept', 'Crusader', 'Paladin', 
                          'Exemplar', 'Prospect', 'Commander', 'Marshal', 'General', 'Chief General']
    
    if request.method == 'POST':
        member_id = request.form.get('member_id', type=int)
        new_rank = request.form.get('new_rank', '').strip()
        reason = request.form.get('reason', '').strip()
        promoted_by = request.form.get('promoted_by', '').strip() or session.get('staff_username', 'Staff')

        member = Member.query.get(member_id)
        if not member:
            flash('Member not found', 'error')
            return redirect(url_for('promote_member'))

        old_rank = member.current_rank
        member.current_rank = new_rank
        member.last_updated = datetime.utcnow()

        # create promotion log (ensure PromotionLog model accepts these fields)
        promotion = PromotionLog(
            member_id=member.id,
            from_rank=old_rank,
            to_rank=new_rank,
            reason=reason,
            promoted_by=promoted_by,
            promotion_date=datetime.utcnow()
        )
        db.session.add(promotion)
        db.session.commit()

        # Sync to Roblox if enabled
        sync_enabled = current_app.config.get('ROBLOX_SYNC_ENABLED', False)
        has_roblox_id = bool(member.roblox_id)
        
        current_app.logger.info(f"Promote member: sync_enabled={sync_enabled}, has_roblox_id={has_roblox_id}, rank: {old_rank} -> {new_rank}")
        
        if sync_enabled and has_roblox_id:
            current_app.logger.info(f"Syncing {member.discord_username} promotion: {old_rank} -> {new_rank}")
            result = sync_member_to_roblox(member)
            if not result['success']:
                error_msg = f"Promotion saved, but Roblox sync failed: {result['message']}"
                current_app.logger.error(error_msg)
                flash(error_msg, 'warning')
            else:
                current_app.logger.info(f"Successfully synced {member.discord_username} promotion to Roblox")
        elif sync_enabled and not has_roblox_id:
            current_app.logger.warning(f"Cannot sync {member.discord_username} - no Roblox ID set")
            flash('Promotion saved, but cannot sync to Roblox (no Roblox ID)', 'warning')
        elif not sync_enabled:
            current_app.logger.debug(f"Roblox sync is disabled - skipping sync for {member.discord_username}")

        flash(f'{member.discord_username} promoted from {old_rank} to {new_rank}', 'success')
        return redirect(url_for('member_detail', member_id=member.id))

    # GET: show form
    members_list = Member.query.filter_by(is_active=True).order_by(Member.discord_username).all()
    return render_template('promote_member.html', members=members_list, available_ranks=available_ranks)

# ensure delete/clear endpoints exist (idempotent if already present)
@app.route('/ac/activity/<int:activity_id>/delete', methods=['POST'])
@staff_required
def delete_ac_activity(activity_id):
    ae = ActivityEntry.query.get_or_404(activity_id)
    member_id = ae.member_id
    db.session.delete(ae)
    db.session.commit()
    flash('Activity entry deleted.', 'success')
    return redirect(url_for('ac_member_detail', member_id=member_id))

@app.route('/ac/member/<int:member_id>/clear_activities', methods=['POST'])
@staff_required
def clear_member_activities(member_id):
    period_id = request.form.get('period_id', type=int)
    if not period_id:
        active = ACPeriod.query.filter_by(is_active=True).first()
        period_id = active.id if active else None

    query = ActivityEntry.query.filter_by(member_id=member_id)
    if period_id:
        query = query.filter_by(ac_period_id=period_id)

    deleted_count = query.delete(synchronize_session=False)
    db.session.commit()
    flash(f'Deleted {deleted_count} activity entries for member.', 'success')
    return redirect(url_for('ac_member_detail', member_id=member_id))

# ========== ROBLOX SYNC ROUTES ==========

@app.route('/roblox/rank_mappings', methods=['GET', 'POST'])
@staff_required
def manage_rank_mappings():
    """Manage rank mappings between system ranks and Roblox role IDs"""
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'add':
            system_rank = request.form.get('system_rank', '').strip()
            roblox_role_id = request.form.get('roblox_role_id', type=int)
            roblox_role_name = request.form.get('roblox_role_name', '').strip() or None
            
            if not system_rank or not roblox_role_id:
                flash('System rank and Roblox role ID are required', 'error')
                return redirect(url_for('manage_rank_mappings'))
            
            # Check if mapping already exists
            existing = RankMapping.query.filter_by(system_rank=system_rank).first()
            if existing:
                existing.roblox_role_id = roblox_role_id
                existing.roblox_role_name = roblox_role_name
                existing.is_active = True
                existing.last_updated = datetime.utcnow()
                flash(f'Updated mapping for {system_rank}', 'success')
            else:
                mapping = RankMapping(
                    system_rank=system_rank,
                    roblox_role_id=roblox_role_id,
                    roblox_role_name=roblox_role_name
                )
                db.session.add(mapping)
                flash(f'Added mapping for {system_rank}', 'success')
            
            db.session.commit()
        
        elif action == 'delete':
            mapping_id = request.form.get('mapping_id', type=int)
            if mapping_id:
                mapping = RankMapping.query.get(mapping_id)
                if mapping:
                    db.session.delete(mapping)
                    db.session.commit()
                    flash('Mapping deleted', 'success')
        
        elif action == 'toggle':
            mapping_id = request.form.get('mapping_id', type=int)
            if mapping_id:
                mapping = RankMapping.query.get(mapping_id)
                if mapping:
                    mapping.is_active = not mapping.is_active
                    mapping.last_updated = datetime.utcnow()
                    db.session.commit()
                    flash('Mapping updated', 'success')
        
        return redirect(url_for('manage_rank_mappings'))
    
    # GET: show all mappings
    mappings = RankMapping.query.order_by(RankMapping.system_rank).all()
    
    # Get available roles from Roblox if configured
    roblox_roles = []
    if current_app.config.get('ROBLOX_GROUP_ID'):
        try:
            from utils.roblox_sync import get_roblox_api
            roblox_api = get_roblox_api()
            if roblox_api:
                roblox_roles = roblox_api.get_group_roles()
        except Exception as e:
            current_app.logger.error(f"Error fetching Roblox roles: {e}")
    
    # Pass config values to template
    config_info = {
        'ROBLOX_SYNC_ENABLED': current_app.config.get('ROBLOX_SYNC_ENABLED', False),
        'ROBLOX_SYNC_INTERVAL': current_app.config.get('ROBLOX_SYNC_INTERVAL', 600),
        'ROBLOX_GROUP_ID': current_app.config.get('ROBLOX_GROUP_ID', '')
    }
    
    return render_template('roblox/rank_mappings.html', mappings=mappings, roblox_roles=roblox_roles, config=config_info)

@app.route('/roblox/sync_now', methods=['POST'])
@staff_required
def sync_now():
    """Manually trigger a sync from Roblox"""
    try:
        result = sync_from_roblox()
        if result['success']:
            flash(result['message'], 'success')
        else:
            flash(f"Sync failed: {result['message']}", 'error')
    except Exception as e:
        flash(f"Sync error: {str(e)}", 'error')
    
    return redirect(request.referrer or url_for('dashboard'))

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