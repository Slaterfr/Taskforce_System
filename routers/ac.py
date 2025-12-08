from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify, session, current_app, send_file
from database.models import db, Member
from database.ac_models import (
    ACPeriod, ActivityEntry, InactivityNotice, ACExemption,
    ACTIVITY_TYPES, AC_QUOTAS, get_member_quota, get_activity_points, is_limited_activity
)
from utils.auth import staff_required
from utils.ac_reports import send_discord_webhook
from utils.excel_reports import generate_ac_workbook_bytes, merge_into_uploaded_workbook_bytes
from sqlalchemy import func
from datetime import datetime, timedelta

ac_bp = Blueprint('ac', __name__)


def _members_with_quota_query():
    """Return members that have a quota (exclude General/Chief General). Case-insensitive."""
    excluded = {'general', 'chief general'}
    # get ranks that have quota > 0
    allowed = [r.lower() for r, q in AC_QUOTAS.items() if q and q > 0 and r.lower() not in excluded]
    return Member.query.filter(
        Member.is_active == True,
        func.lower(Member.current_rank).in_(allowed)
    ).order_by(func.lower(Member.current_rank), Member.discord_username)


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


# Replace the member_progress building loop in /ac route with this aggregated version
@ac_bp.route('/')
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


@ac_bp.route('/create_period', methods=['GET', 'POST'])
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
        return redirect(url_for('ac.ac_dashboard'))
    return render_template('ac/create_period.html')


@ac_bp.route('/edit_period', methods=['GET', 'POST'])
@staff_required
def edit_ac_period():
    current_period = ACPeriod.query.filter_by(is_active=True).first()
    if not current_period:
        flash('No active AC period', 'error')
        return redirect(url_for('ac.ac_dashboard'))
    
    if request.method == 'POST':
        period_name = request.form.get('period_name', '').strip()
        if period_name:
            current_period.period_name = period_name
            db.session.commit()
            flash('Period name updated', 'success')
            return redirect(url_for('ac.ac_dashboard'))
        else:
            flash('Period name cannot be empty', 'error')
    
    return render_template('ac/edit_period.html', period=current_period)


@ac_bp.route('/clear_all_activities', methods=['POST'])
@staff_required
def clear_all_activities():
    """Clear all activities for all members in the current period"""
    current_period = ACPeriod.query.filter_by(is_active=True).first()
    if not current_period:
        flash('No active AC period', 'error')
        return redirect(url_for('ac.ac_dashboard'))
    
    # Delete all activity entries for the current period
    deleted_count = ActivityEntry.query.filter_by(ac_period_id=current_period.id).delete()
    db.session.commit()
    
    flash(f'Cleared {deleted_count} activity entries for all members', 'success')
    return redirect(url_for('ac.ac_dashboard'))


@ac_bp.route('/title_rewards')
@staff_required
def title_rewards():
    """Display title rewards for the current AC period"""
    current_period = ACPeriod.query.filter_by(is_active=True).first()
    if not current_period:
        flash('No active AC period', 'error')
        return redirect(url_for('ac.ac_dashboard'))
    
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


@ac_bp.route('/send_title_webhook', methods=['POST'])
@staff_required
def send_title_webhook():
    """Send title rewards message to Discord webhook"""
    webhook_url = request.form.get('webhook_url', '').strip()
    message = request.form.get('message', '').strip()
    
    if not webhook_url or not message:
        flash('Webhook URL and message are required', 'error')
        return redirect(url_for('ac.title_rewards'))
    
    current_period = ACPeriod.query.filter_by(is_active=True).first()
    period_name = current_period.period_name if current_period else 'Current Period'
    
    success = send_discord_webhook(webhook_url, message, f"Title Rewards - {period_name}")
    
    if success:
        flash('Title rewards sent to Discord successfully!', 'success')
    else:
        flash('Failed to send to Discord. Please check your webhook URL.', 'error')
    
    return redirect(url_for('ac.title_rewards'))


@ac_bp.route('/log_activity', methods=['GET', 'POST'])
@staff_required
def log_ac_activity():
    current_period = ACPeriod.query.filter_by(is_active=True).first()
    if not current_period:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': 'no_active_period'}), 400
        flash('No active AC period. Please create one first.', 'error')
        return redirect(url_for('ac.ac_dashboard'))

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
                return redirect(url_for('ac.log_ac_activity'))

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
        return redirect(url_for('ac.ac_dashboard'))

    # GET: render form/page
    members_with_quota = _members_with_quota_query().all()
    return render_template('ac/log_activity.html',
                           members=members_with_quota,
                           activity_types=ACTIVITY_TYPES,
                           current_period=current_period)


@ac_bp.route('/quick_log', methods=['GET'])
@staff_required
def quick_log():
    current_period = ACPeriod.query.filter_by(is_active=True).first()
    if not current_period:
        flash('No active AC period. Please create one first.', 'error')
        return redirect(url_for('ac.ac_dashboard'))

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


@ac_bp.route('/quick_log_activity', methods=['POST'])
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


@ac_bp.route('/quick_log_ia', methods=['POST'])
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


@ac_bp.route('/quick_log_exempt', methods=['POST'])
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
@ac_bp.route('/export_excel', methods=['GET', 'POST'])
@staff_required
def export_ac_excel():
    period_id = request.args.get('period_id', None, type=int)
    if request.method == 'POST' and 'workbook' in request.files:
        uploaded = request.files['workbook']
        if uploaded.filename == '':
            flash('No workbook uploaded', 'error')
            return redirect(url_for('ac.ac_dashboard'))
        merged_io, filename = merge_into_uploaded_workbook_bytes(uploaded.stream, period_id=period_id)
        return send_file(merged_io, as_attachment=True, download_name=filename, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    out_io, filename = generate_ac_workbook_bytes(period_id=period_id)
    return send_file(out_io, as_attachment=True, download_name=filename, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')


# Replace ac_member_detail route with aggregation + detailed list (keeps delete buttons for staff)
@ac_bp.route('/member/<int:member_id>')
@staff_required
def ac_member_detail(member_id):
    member = Member.query.get_or_404(member_id)
    current_period = ACPeriod.query.filter_by(is_active=True).first()
    if not current_period:
        flash('No active AC period.', 'error')
        return redirect(url_for('ac.ac_dashboard'))

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


# Ensure delete/clear endpoints exist (idempotent if already present)
@ac_bp.route('/activity/<int:activity_id>/delete', methods=['POST'])
@staff_required
def delete_ac_activity(activity_id):
    ae = ActivityEntry.query.get_or_404(activity_id)
    member_id = ae.member_id
    db.session.delete(ae)
    db.session.commit()
    flash('Activity entry deleted.', 'success')
    return redirect(url_for('ac.ac_member_detail', member_id=member_id))


@ac_bp.route('/member/<int:member_id>/clear_activities', methods=['POST'])
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
    return redirect(url_for('ac.ac_member_detail', member_id=member_id))
