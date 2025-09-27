from flask import Flask, render_template, request, flash, redirect, url_for, jsonify
from config import Config
from database.models import db, Member, ActivityLog, PromotionLog
import os
from datetime import datetime

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    
    # Create database directory if it doesn't exist
    # Safely derive the sqlite file path and ensure its directory exists.
    db_uri = app.config.get('SQLALCHEMY_DATABASE_URI', '')
    try:
        # Use SQLAlchemy URL parsing to reliably extract the database path
        from sqlalchemy.engine import make_url
        url = make_url(db_uri)
        sqlite_path = url.database  # None for in-memory, path string otherwise
    except Exception:
        # Fallback: crude parsing
        sqlite_path = None
        if db_uri.startswith('sqlite:'):
            sqlite_path = db_uri.split('://', 1)[-1].lstrip('/')

    if sqlite_path:
        # If path is relative, make it relative to the application root for predictability
        if not os.path.isabs(sqlite_path):
            db_file = os.path.abspath(os.path.join(app.root_path, sqlite_path))
        else:
            db_file = os.path.abspath(sqlite_path)

        db_dir = os.path.dirname(db_file)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)
        # Debug: print resolved paths so we can see what sqlite is trying to open
        print(f"[DEBUG] SQLALCHEMY_DATABASE_URI={db_uri}")
        print(f"[DEBUG] Resolved sqlite file path: {db_file}")
        # Ensure the sqlite file exists (touch) so sqlite can open it
        try:
            if not os.path.exists(db_file):
                open(db_file, 'a', encoding='utf-8').close()
        except Exception as e:
            print(f"[DEBUG] Failed to touch sqlite file: {e}")
        # Ensure SQLAlchemy uses the absolute file path (convert backslashes to forward slashes)
        abs_uri = 'sqlite:///' + db_file.replace('\\', '/')
        app.config['SQLALCHEMY_DATABASE_URI'] = abs_uri
        print(f"[DEBUG] Overriding SQLALCHEMY_DATABASE_URI -> {abs_uri}")

    # Initialize database (after ensuring config points to the absolute sqlite path)
    db.init_app(app)
    
    # Create tables
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
        current_rank = request.form.get('current_rank', 'Aspirant')

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


@app.route('/member/<int:member_id>/edit', methods=['GET', 'POST'])
def edit_member(member_id):
    member = Member.query.get_or_404(member_id)
    if request.method == 'POST':
        discord_username = request.form.get('discord_username')
        roblox_username = request.form.get('roblox_username')
        current_rank = request.form.get('current_rank')

        # Ensure discord username uniqueness
        existing = Member.query.filter(Member.discord_username == discord_username, Member.id != member.id).first()
        if existing:
            flash('Another member with this Discord username already exists!', 'error')
            return redirect(url_for('edit_member', member_id=member.id))

        member.discord_username = discord_username
        member.roblox_username = roblox_username or None
        member.current_rank = current_rank
        member.last_updated = datetime.utcnow()

        db.session.commit()

        flash('Member updated successfully!', 'success')
        return redirect(url_for('member_detail', member_id=member.id))

    return render_template('edit_member.html', member=member)


@app.route('/member/<int:member_id>/delete', methods=['GET', 'POST'])
def delete_member(member_id):
    member = Member.query.get_or_404(member_id)
    if request.method == 'POST':
        # Soft-delete: mark inactive
        member.is_active = False
        member.last_updated = datetime.utcnow()
        db.session.commit()
        flash(f'Member {member.discord_username} has been removed.', 'success')
        return redirect(url_for('members'))

    return render_template('confirm_delete.html', member=member)

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

if __name__ == '__main__':
    app.run(debug=True)