from flask import Blueprint, render_template, request
from database.ac_models import ACTIVITY_TYPES
from services import ac_service, member_service

public_bp = Blueprint('public', __name__)


@public_bp.route('/')
def public_roster():
    search = request.args.get('search', '')
    members = member_service.search_members(search)
    return render_template('public_roster.html', members=members, search=search)


@public_bp.route('/public/member/<int:member_id>')
def public_member(member_id):
    """Public read-only member view (limited data)"""
    data = member_service.get_public_member_data(member_id)
    if not data:
        from flask import abort
        abort(404)
    return render_template('public_member.html',
                           member=data['member'],
                           recent_activities=data['recent_activities'])


@public_bp.route('/ac_progress')
def public_ac_progress():
    current_period = ac_service.get_active_period()
    if not current_period:
        return render_template('public_ac_progress.html',
                             current_period=None,
                             member_progress=[],
                             activity_types=ACTIVITY_TYPES)

    member_progress = ac_service.build_member_progress(current_period)

    return render_template('public_ac_progress.html',
                         current_period=current_period,
                         member_progress=member_progress,
                         activity_types=ACTIVITY_TYPES)
