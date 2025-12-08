from flask import Blueprint, render_template, request
from database.models import Member
from database.ac_models import ActivityEntry

public_bp = Blueprint('public', __name__)


@public_bp.route('/')
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


@public_bp.route('/public/member/<int:member_id>')
def public_member(member_id):
    """Public read-only member view (limited data)"""
    member = Member.query.get_or_404(member_id)
    # limit data for public view: basic profile + recent non-sensitive activities
    recent_activities = ActivityEntry.query.filter_by(member_id=member_id).order_by(ActivityEntry.activity_date.desc()).limit(5).all()
    # do not include internal IA notices or editable controls
    return render_template('public_member.html',
                           member=member,
                           recent_activities=recent_activities)
