from flask import Flask, render_template, request, flash, redirect, url_for, jsonify
from config import Config
from database.models import db, Member, ActivityLog, PromotionLog
from database.ac_models import ACPeriod, ActivityEntry, InactivityNotice, ACTIVITY_TYPES, AC_QUOTAS, get_member_quota, get_activity_points, is_limited_activity
import os
from datetime import datetime, timedelta
from types import SimpleNamespace
from sqlalchemy import func

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    
    # If using a sqlite file URI, ensure the directory exists and make the path absolute
    uri = app.config.get('SQLALCHEMY_DATABASE_URI', '') or ''
    if uri.startswith('sqlite:///'):
        # strip prefix
        db_path = uri.replace('sqlite:///', '')
        # make absolute relative to app root if not already absolute
        if not os.path.isabs(db_path):
            db_path = os.path.join(app.root_path, db_path)
        db_dir = os.path.dirname(db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)
        # ensure file exists (touch)
        try:
            open(db_path, 'a').close()
        except Exception:
            pass
        # normalize to forward slashes for SQLAlchemy on Windows
        norm_path = db_path.replace('\\', '/')
        app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{norm_path}'
    
    # Initialize database
    db.init_app(app)
    
    # Create tables inside app context
    with app.app_context():
        db.create_all()
    
    return app

app = create_app()

@app.route('/')
def home():
    member_count = Member.query.filter_by(is_active=True).count()
    recent_activities = ActivityLog.query.order_by(ActivityLog.log_date.desc()).limit(5).all()
    return render_template('dashboard.html', member_count=member_count, recent_activities=recent_activities)

@app.route('/members')
def members():
    search = request.args.get('search', '')
    if search:
        members = Member.query.filter(
            (Member.discord_username.contains(search)) |
            (Member.roblox_username.contains(search)) |
            (Member.current_rank.contains(search))
        ).filter_by(is_active=True).all()
    else:
        members = Member.query.filter_by(is_active=True).all()
    
    return render_template('members.html', members=members, search=search)

@app.route('/member/<int:member_id>')
def member_detail(member_id):
    member = Member.query.get_or_404(member_id)
    activities = ActivityLog.query.filter_by(member_id=member_id).order_by(ActivityLog.log_date.desc()).all()
    promotions = PromotionLog.query.filter_by(member_id=member_id).order_by(PromotionLog.promotion_date.desc()).all()
    return render_template('member_detail.html', member=member, activities=activities, promotions=promotions)

@app.route('/add_member', methods=['GET', 'POST'])
def add_member():
    if request.method == 'POST':
        discord_username = request.form.get('discord_username')
        roblox_username = request.form.get('roblox_username')
        current_rank = request.form.get('current_rank', 'Recruit')
        
        # Check if member already exists
        existing = Member.query.filter_by(discord_username=discord_username).first()
        if existing:
            flash('Member with this Discord username already exists!', 'error')
            return redirect(url_for('add_member'))
        
        # Create new member
        member = Member(
            discord_username=discord_username,
            roblox_username=roblox_username or None,
            current_rank=current_rank
        )
        
        db.session.add(member)
        db.session.commit()
        
        flash(f'Member {discord_username} added successfully!', 'success')
        return redirect(url_for('member_detail', member_id=member.id))
    
    return render_template('add_member.html')

@app.route('/log_activity', methods=['GET', 'POST'])
def log_activity():
    if request.method == 'POST':
        member_id = request.form.get('member_id')
        activity_type = request.form.get('activity_type')
        description = request.form.get('description')
        logged_by = request.form.get('logged_by')
        
        activity = ActivityLog(
            member_id=member_id,
            activity_type=activity_type,
            description=description,
            logged_by=logged_by
        )
        
        db.session.add(activity)
        db.session.commit()
        
        flash('Activity logged successfully!', 'success')
        return redirect(url_for('member_detail', member_id=member_id))
    
    members = Member.query.filter_by(is_active=True).order_by(Member.discord_username).all()
    return render_template('log_activity.html', members=members)

@app.route('/promote_member', methods=['GET', 'POST'])
def promote_member():
    if request.method == 'POST':
        member_id = request.form.get('member_id')
        new_rank = request.form.get('new_rank')
        reason = request.form.get('reason')
        promoted_by = request.form.get('promoted_by')
        
        member = Member.query.get(member_id)
        old_rank = member.current_rank
        
        # Log the promotion
        promotion = PromotionLog(
            member_id=member_id,
            from_rank=old_rank,
            to_rank=new_rank,
            reason=reason,
            promoted_by=promoted_by
        )
        
        # Update member rank
        member.current_rank = new_rank
        member.last_updated = datetime.utcnow()
        
        db.session.add(promotion)
        db.session.commit()
        
        flash(f'{member.discord_username} promoted from {old_rank} to {new_rank}!', 'success')
        return redirect(url_for('member_detail', member_id=member_id))
    
    members = Member.query.filter_by(is_active=True).order_by(Member.discord_username).all()
    return render_template('promote_member.html', members=members)

# API Endpoints (for future bot integration)
@app.route('/api/members', methods=['GET'])
def api_members():
    members = Member.query.filter_by(is_active=True).all()
    return jsonify([member.to_dict() for member in members])

@app.route('/api/member/<int:member_id>', methods=['GET'])
def api_member(member_id):
    member = Member.query.get_or_404(member_id)
    return jsonify(member.to_dict())

# ========== ACTIVITY CHECK (AC) ROUTES ==========

def get_allowed_ac_ranks():
    """Return list of allowed ranks (lowercased) for AC (exclude ranks with no quota)."""
    excluded = {'General', 'Chief General'}
    allowed = [r for r in AC_QUOTAS.keys() if r not in excluded and AC_QUOTAS.get(r, 0) > 0]
    return [r.lower() for r in allowed]
@app.route('/ac')
@app.route('/ac')
def ac_dashboard():
    """Main AC dashboard showing current period and overall stats"""
    current_period = ACPeriod.query.filter_by(is_active=True).first()
    
    if not current_period:
        return render_template('ac/ac_setup.html')
    
    # Use helper to get allowed ranks and match case-insensitively
    allowed_lower = get_allowed_ac_ranks()
    ac_members = Member.query.filter(
        Member.is_active == True,
        func.lower(Member.current_rank).in_(allowed_lower)
    ).all()
    
    # Calculate progress for each member
    member_progress = []
    for member in ac_members:
        quota = get_member_quota(member.current_rank)
        if quota == 0:
            continue
            
        # Get total points for this period
        total_points = db.session.query(db.func.sum(ActivityEntry.points)).filter_by(
            member_id=member.id,
            ac_period_id=current_period.id
        ).scalar() or 0.0
        
        # Check for protective IA
        ia_notice = InactivityNotice.query.filter_by(
            member_id=member.id,
            ac_period_id=current_period.id,
            protects_ac=True
        ).first()
        
        progress = {
            'member': member,
            'quota': quota,
            'points': total_points,
            'percentage': min(100, (total_points / quota) * 100) if quota > 0 else 0,
            'status': 'Protected (IA)' if ia_notice else ('Passed' if total_points >= quota else 'In Progress'),
            'is_protected': bool(ia_notice),
            'recent_activities': ActivityEntry.query.filter_by(
                member_id=member.id, 
                ac_period_id=current_period.id
            ).order_by(ActivityEntry.activity_date.desc()).limit(3).all()
        }
        member_progress.append(progress)
    
    # Sort by progress percentage (lowest first - those who need help)
    member_progress.sort(key=lambda x: x['percentage'] if not x['is_protected'] else 100)
    
    return render_template('ac/ac_dashboard.html', 
                         current_period=current_period, 
                         member_progress=member_progress,
                         activity_types=ACTIVITY_TYPES)

@app.route('/ac/log_activity', methods=['GET', 'POST'])
def log_ac_activity():
    """Log an activity for AC tracking"""
    current_period = ACPeriod.query.filter_by(is_active=True).first()
    if not current_period:
        flash('No active AC period. Please create one first.', 'error')
        return redirect(url_for('ac_dashboard'))
    
    if request.method == 'POST':
        member_id = request.form.get('member_id')
        activity_type = request.form.get('activity_type')
        description = request.form.get('description')
        activity_date = datetime.strptime(request.form.get('activity_date'), '%Y-%m-%d')
        logged_by = request.form.get('logged_by')
        
        member = Member.query.get(member_id)
        points = get_activity_points(activity_type)
        
        # Check if this is a limited activity and member already has one
        if is_limited_activity(activity_type):
            existing = ActivityEntry.query.filter_by(
                member_id=member_id,
                ac_period_id=current_period.id,
                activity_type=activity_type
            ).first()
            
            if existing:
                flash(f'{activity_type} can only be logged once per AC period. {member.discord_username} already has one.', 'error')
                return redirect(url_for('log_ac_activity'))
        
        # Create activity entry
        activity_entry = ActivityEntry(
            member_id=member_id,
            ac_period_id=current_period.id,
            activity_type=activity_type,
            points=points,
            description=description,
            activity_date=activity_date,
            logged_by=logged_by,
            is_limited_activity=is_limited_activity(activity_type)
        )
        
        db.session.add(activity_entry)
        db.session.commit()
        
        flash(f'Logged {activity_type} ({points} points) for {member.discord_username}', 'success')
        return redirect(url_for('ac_dashboard'))
    
    # Get members eligible for AC
    ac_members = Member.query.filter(
        Member.is_active == True,
        Member.current_rank.in_(['Prospect', 'Commander', 'Marshall', 'General', 'Chief General'])
    ).order_by(Member.discord_username).all()
    
    return render_template('ac/log_activity.html', 
                         members=ac_members, 
                         activity_types=ACTIVITY_TYPES,
                         current_period=current_period)

@app.route('/ac/create_period', methods=['GET', 'POST'])
def create_ac_period():
    """Create a new AC period"""
    if request.method == 'POST':
        period_name = request.form.get('period_name')
        start_date = datetime.strptime(request.form.get('start_date'), '%Y-%m-%d')
        
        # Calculate end date (2 weeks from start)
        end_date = start_date + timedelta(weeks=2) - timedelta(days=1)  # End of day on last day
        
        # Deactivate any existing active periods
        ACPeriod.query.filter_by(is_active=True).update({'is_active': False})
        
        # Create new period
        new_period = ACPeriod(
            period_name=period_name,
            start_date=start_date,
            end_date=end_date,
            is_active=True
        )
        
        db.session.add(new_period)
        db.session.commit()
        
        flash(f'Created new AC period: {period_name}', 'success')
        return redirect(url_for('ac_dashboard'))
    
    return render_template('ac/create_period.html')

@app.route('/ac/quick_log', methods=['GET'])
def ac_quick_log():
    """Quick AC logging UI (rapid-fire buttons)"""
    current_period = ACPeriod.query.filter_by(is_active=True).first()
    if not current_period:
        flash('No active AC period.', 'error')
        return redirect(url_for('ac_dashboard'))

    # Build allowed ranks from AC_QUOTAS but exclude ranks that have no quota
    excluded_ranks = {'General', 'Chief General'}
    allowed_ranks = [r for r in AC_QUOTAS.keys() if r not in excluded_ranks]

    # Query active members who have a quota (include Marshalls, etc.)
    members = Member.query.filter(
        Member.is_active == True,
        Member.current_rank.in_(allowed_ranks)
    ).order_by(Member.current_rank.desc(), Member.discord_username).all()

    # Build activity_types object the template expects (details.points, details.limited)
    activity_types = {}
    for atype in ACTIVITY_TYPES:
        activity_types[atype] = SimpleNamespace(
            points=get_activity_points(atype),
            limited=bool(is_limited_activity(atype))
        )

    today = datetime.utcnow().date().isoformat()

    return render_template(
        'ac/ac_quick_log.html',
        current_period=current_period,
        members=members,
        activity_types=activity_types,
        today=today
    )

@app.route('/ac/quick_log_activity', methods=['POST'])
def quick_log_activity():
    """AJAX endpoint for rapid fire logging"""
    from flask import jsonify
    
    data = request.get_json()
    current_period = ACPeriod.query.filter_by(is_active=True).first()
    
    if not current_period:
        return jsonify({'success': False, 'message': 'No active AC period'})
    
    member_id = data.get('member_id')
    activity_type = data.get('activity_type')
    activity_date = datetime.strptime(data.get('activity_date'), '%Y-%m-%d')
    logged_by = data.get('logged_by', 'HC Team')
    
    points = get_activity_points(activity_type)
    
    # Check for limited activities
    if is_limited_activity(activity_type):
        existing = ActivityEntry.query.filter_by(
            member_id=member_id,
            ac_period_id=current_period.id,
            activity_type=activity_type
        ).first()
        
        if existing:
            return jsonify({
                'success': False, 
                'message': f'{activity_type} can only be logged once per AC period'
            })
    
    # Create activity entry
    activity_entry = ActivityEntry(
        member_id=member_id,
        ac_period_id=current_period.id,
        activity_type=activity_type,
        points=points,
        activity_date=activity_date,
        logged_by=logged_by,
        is_limited_activity=is_limited_activity(activity_type)
    )
    
    db.session.add(activity_entry)
    db.session.commit()
    
    return jsonify({'success': True, 'points': points})

@app.route('/ac/batch_log', methods=['POST'])
def batch_log_activities():
    """Batch log multiple activities at once"""
    current_period = ACPeriod.query.filter_by(is_active=True).first()
    
    if not current_period:
        flash('No active AC period', 'error')
        return redirect(url_for('ac_dashboard'))
    
    batch_text = request.form.get('batch_input', '')
    batch_date = datetime.strptime(request.form.get('batch_date'), '%Y-%m-%d')
    logged_by = request.form.get('batch_logged_by')
    
    # Parse the batch text
    lines = [line.strip() for line in batch_text.split('\n') if line.strip()]
    
    keywords_map = {
        'training': 'Training', 'hosted': 'Training', 'host': 'Training',
        'raid': 'Raid', 'raided': 'Raid',
        'patrol': 'Patrol',
        'mission': 'Mission', 'posted': 'Mission',
        'tryout': 'Tryout', 'recruitment': 'Tryout',
        'supervision': 'Supervision', 'supervised': 'Supervision',
        'evaluation': 'Evaluation', 'eval': 'Evaluation'
    }
    
    success_count = 0
    error_count = 0
    
    for line in lines:
        lower_line = line.lower()
        
        # Extract username (first word)
        username = line.split()[0] if line.split() else ''
        
        # Find activity type
        activity_type = None
        for keyword, act_type in keywords_map.items():
            if keyword in lower_line:
                activity_type = act_type
                break
        
        if not activity_type or not username:
            error_count += 1
            continue
        
        # Find member
        member = Member.query.filter(
            Member.discord_username.ilike(f'%{username}%'),
            Member.is_active == True
        ).first()
        
        if not member:
            error_count += 1
            continue
        
        # Check if limited activity already exists
        points = get_activity_points(activity_type)
        if is_limited_activity(activity_type):
            existing = ActivityEntry.query.filter_by(
                member_id=member.id,
                ac_period_id=current_period.id,
                activity_type=activity_type
            ).first()
            
            if existing:
                error_count += 1
                continue
        
        # Create activity
        activity_entry = ActivityEntry(
            member_id=member.id,
            ac_period_id=current_period.id,
            activity_type=activity_type,
            points=points,
            activity_date=batch_date,
            logged_by=logged_by,
            is_limited_activity=is_limited_activity(activity_type)
        )
        
        db.session.add(activity_entry)
        success_count += 1
    
    db.session.commit()
    
    flash(f'Batch logged {success_count} activities! ({error_count} skipped)', 'success')
    return redirect(url_for('ac_dashboard'))

# Detailed AC view for a specific member
@app.route('/ac/member/<int:member_id>')
def ac_member_detail(member_id):
    member = Member.query.get_or_404(member_id)
    current_period = ACPeriod.query.filter_by(is_active=True).first()
    
    if not current_period:
        flash('No active AC period.', 'error')
        return redirect(url_for('ac_dashboard'))
    
    # Get all activities for this member in current period
    activities = ActivityEntry.query.filter_by(
        member_id=member_id,
        ac_period_id=current_period.id
    ).order_by(ActivityEntry.activity_date.desc()).all()
    
    # Get IA notices
    ia_notices = InactivityNotice.query.filter_by(
        member_id=member_id,
        ac_period_id=current_period.id
    ).all()
    
    # Calculate stats
    quota = get_member_quota(member.current_rank)
    total_points = sum(activity.points for activity in activities)
    
    return render_template('ac/member_detail.html',
                         member=member,
                         current_period=current_period,
                         activities=activities,
                         ia_notices=ia_notices,
                         quota=quota,
                         total_points=total_points)

if __name__ == '__main__':
    app.run(debug=True)