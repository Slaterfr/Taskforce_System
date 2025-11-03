from flask import (
    Flask, render_template, request, flash, redirect, url_for, jsonify,
    send_file, session, current_app, Response, make_response
)
from config import Config
from database.models import db, Member, ActivityLog, PromotionLog
from database.ac_models import (
    ACPeriod,
    ActivityEntry,
    InactivityNotice,
    ACTIVITY_TYPES,
    AC_QUOTAS,
    get_member_quota,
    get_activity_points,
    is_limited_activity,
)
from utils.ac_reports import ACReportGenerator, send_discord_webhook
from utils.excel_reports import generate_ac_workbook_bytes, merge_into_uploaded_workbook_bytes
from utils.auth import staff_required, is_staff, check_password
from sqlalchemy import func
from datetime import datetime, timedelta
import os
import os.path as op
import secrets
from io import BytesIO
from collections import defaultdict

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
                return jsonify({'success': True, 'next': next_url or url_for('dashboard')}), 200

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
        flash('Member added', 'success')
        return redirect(url_for('member_detail', member_id=m.id))
    return render_template('add_member.html')

@app.route('/member/<int:member_id>/edit', methods=['GET', 'POST'])
@staff_required
def edit_member(member_id):
    member = Member.query.get_or_404(member_id)
    if request.method == 'POST':
        member.discord_username = request.form.get('discord_username', member.discord_username).strip()
        member.roblox_username = request.form.get('roblox_username', member.roblox_username).strip() or None
        member.current_rank = request.form.get('current_rank', member.current_rank).strip()
        member.last_updated = datetime.utcnow()
        db.session.commit()
        flash('Member updated', 'success')
        return redirect(url_for('member_detail', member_id=member.id))
    return render_template('edit_member.html', member=member)

@app.route('/member/<int:member_id>/delete', methods=['POST'])
@staff_required
def delete_member(member_id):
    member = Member.query.get_or_404(member_id)
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
        pct = min(100.0, (total_points / quota) * 100.0) if quota > 0 else 0.0

        ia_notice = InactivityNotice.query.filter_by(
            member_id=m.id,
            ac_period_id=current_period.id,
            protects_ac=True
        ).first()

        progress = {
            'member': m,
            'quota': quota,
            'points': total_points,
            'percentage': pct,
            'status': 'Protected (IA)' if ia_notice else ('Passed' if total_points >= quota else 'In Progress'),
            'is_protected': bool(ia_notice),
            'activity_summary': activity_summary
        }
        member_progress.append(progress)

    member_progress.sort(key=lambda x: (100 if x['is_protected'] else x['percentage']))

    return render_template('ac/ac_dashboard.html',
                         current_period=current_period,
                         member_progress=member_progress,
                         activity_types=ACTIVITY_TYPES,
                         activity_stats=activity_stats)

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

    return render_template('ac/ac_quick_log.html',
                         members=members_with_quota,
                         activity_types=ACTIVITY_TYPES,
                         current_period=current_period,
                         today=datetime.utcnow().strftime('%Y-%m-%d'),
                         member_activities=member_activities,
                         member_activity_counts=member_activity_counts)

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

        flash(f'{member.discord_username} promoted from {old_rank} to {new_rank}', 'success')
        return redirect(url_for('member_detail', member_id=member.id))

    # GET: show form
    members_list = Member.query.filter_by(is_active=True).order_by(Member.discord_username).all()
    return render_template('promote_member.html', members=members_list)

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