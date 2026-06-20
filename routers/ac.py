from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify, session, send_file
from database.models import db, Member
from database.ac_models import (
    ACPeriod, ActivityEntry, InactivityNotice, ACExemption,
    ACTIVITY_TYPES, get_member_quota, MonthlyActivityEntry,
)
from services import ac_service
from utils.auth import hct_required
from utils.ac_reports import send_discord_webhook
from utils.excel_reports import generate_ac_workbook_bytes, merge_into_uploaded_workbook_bytes
from datetime import datetime, timedelta

ac_bp = Blueprint('ac', __name__)


@ac_bp.route('/')
@hct_required
def ac_dashboard():
    current_period = ac_service.get_active_period()
    if not current_period:
        return render_template('ac/ac_setup.html')

    activity_stats = ac_service.get_activity_stats(current_period)
    member_progress = ac_service.build_member_progress(current_period)

    all_activities = ActivityEntry.query.filter_by(ac_period_id=current_period.id).all()
    title_winners = ac_service.calculate_title_rewards(all_activities, current_period)

    return render_template('ac/ac_dashboard.html',
                         current_period=current_period,
                         member_progress=member_progress,
                         activity_types=ACTIVITY_TYPES,
                         activity_stats=activity_stats,
                         title_winners=title_winners)


@ac_bp.route('/create_period', methods=['GET', 'POST'])
@hct_required
def create_ac_period():
    if request.method == 'POST':
        period_name = request.form.get('period_name', '').strip()
        start_date = datetime.strptime(request.form.get('start_date'), '%Y-%m-%d')
        end_date = datetime.strptime(request.form.get('end_date'), '%Y-%m-%d') if request.form.get('end_date') else (start_date + timedelta(weeks=2) - timedelta(days=1))
        ac_service.create_period(period_name, start_date, end_date)
        flash('AC period created', 'success')
        return redirect(url_for('ac.ac_dashboard'))
    return render_template('ac/create_period.html')


@ac_bp.route('/edit_period', methods=['GET', 'POST'])
@hct_required
def edit_ac_period():
    current_period = ac_service.get_active_period()
    if not current_period:
        flash('No active AC period', 'error')
        return redirect(url_for('ac.ac_dashboard'))
    
    if request.method == 'POST':
        period_name = request.form.get('period_name', '').strip()
        if period_name:
            ac_service.update_period_name(current_period.id, period_name)
            flash('Period name updated', 'success')
            return redirect(url_for('ac.ac_dashboard'))
        else:
            flash('Period name cannot be empty', 'error')
    
    return render_template('ac/edit_period.html', period=current_period)


@ac_bp.route('/finalize_period', methods=['POST'])
@hct_required
def finalize_period():
    """
    Finalize the current AC period:
    1. Capture all member statistics for the period
    2. Mark period as finalized
    3. Redirect to title rewards page
    """
    current_period = ac_service.get_active_period()
    if not current_period:
        flash('No active AC period to finalize', 'error')
        return redirect(url_for('ac.ac_dashboard'))


@ac_bp.route('/clear_all_activities', methods=['POST'])
@hct_required
def clear_all_activities():
    """Clear all activities for all members in the current period (MonthlyActivityEntry preserved)"""
    current_period = ac_service.get_active_period()
    if not current_period:
        flash('No active AC period', 'error')
        return redirect(url_for('ac.ac_dashboard'))
    
    deleted_count = ac_service.clear_all_activities(current_period.id)
    
    flash(f'Cleared {deleted_count} activity entries for all members. Title tracking data preserved.', 'success')
    return redirect(url_for('ac.ac_dashboard'))


@ac_bp.route('/clear_titles', methods=['POST'])
@hct_required
def clear_titles():
    """Clear all title tracking data - manual action to reset title history"""
    current_period = ac_service.get_active_period()
    if not current_period:
        flash('No active AC period', 'error')
        return redirect(url_for('ac.ac_dashboard'))
    
    deleted_count = ac_service.clear_titles(current_period.id)
    
    flash(f'Cleared {deleted_count} title tracking entries. Monthly activity history reset.', 'success')
    return redirect(url_for('ac.ac_dashboard'))


@ac_bp.route('/title_rewards')
@hct_required
def title_rewards():
    """Display title rewards for the current AC period"""
    current_period = ac_service.get_active_period()
    if not current_period:
        flash('No active AC period', 'error')
        return redirect(url_for('ac.ac_dashboard'))
    
    # Get all activities for the current period
    all_activities = ac_service.get_period_activities(current_period.id)
    
    # Calculate title rewards (includes Executor title with mission stats)
    titles = ac_service.calculate_title_rewards(all_activities, current_period)
    
    # Generate Discord message
    discord_message = ac_service.generate_title_discord_message(titles, current_period)
    
    return render_template('ac/title_rewards.html',
                         current_period=current_period,
                         titles=titles,
                         discord_message=discord_message)


@ac_bp.route('/send_title_webhook', methods=['POST'])
@hct_required
def send_title_webhook():
    """Send title rewards message to Discord webhook"""
    webhook_url = request.form.get('webhook_url', '').strip()
    message = request.form.get('message', '').strip()
    
    if not webhook_url or not message:
        flash('Webhook URL and message are required', 'error')
        return redirect(url_for('ac.title_rewards'))
    
    current_period = ac_service.get_active_period()
    period_name = current_period.period_name if current_period else 'Current Period'
    
    success = send_discord_webhook(webhook_url, message, f"Title Rewards - {period_name}")
    
    if success:
        flash('Title rewards sent to Discord successfully!', 'success')
    else:
        flash('Failed to send to Discord. Please check your webhook URL.', 'error')
    
    return redirect(url_for('ac.title_rewards'))


@ac_bp.route('/log_activity', methods=['GET', 'POST'])
@hct_required
def log_ac_activity():
    current_period = ac_service.get_active_period()
    if not current_period:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': 'no_active_period'}), 400
        flash('No active AC period. Please create one first.', 'error')
        return redirect(url_for('ac.ac_dashboard'))

    if request.method == 'POST':
        data = request.get_json(silent=True) or request.form
        activity_date = datetime.strptime(data.get('activity_date'), '%Y-%m-%d')

        result = ac_service.log_activity(
            data.get('member_id'),
            data.get('activity_type'),
            activity_date=activity_date,
            description=data.get('description'),
            logged_by=data.get('logged_by') or 'HC Team',
            quantity=data.get('quantity', 1),
            period=current_period,
            validate_activity_type=False,
        )

        if not result['success']:
            if result.get('error') == 'limited_activity_exists':
                flash('Limited activity already logged for this period', 'error')
            return redirect(url_for('ac.log_ac_activity'))

        quantity = result['count']
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json:
            return jsonify({
                'success': True,
                'activity_ids': result['activity_ids'],
                'count': quantity,
            }), 200

        activity_type = data.get('activity_type')
        flash(
            f'Successfully logged {quantity} {activity_type} activit{"ies" if quantity > 1 else "y"}',
            'success',
        )
        return redirect(url_for('ac.ac_dashboard'))

    members_with_quota = ac_service.get_members_with_quota()
    return render_template('ac/log_activity.html',
                           members=members_with_quota,
                           activity_types=ACTIVITY_TYPES,
                           current_period=current_period)


@ac_bp.route('/quick_log', methods=['GET'])
@hct_required
def quick_log():
    current_period = ac_service.get_active_period()
    if not current_period:
        flash('No active AC period. Please create one first.', 'error')
        return redirect(url_for('ac.ac_dashboard'))

    log_data = ac_service.get_quick_log_data(current_period.id)

    return render_template('ac/ac_quick_log.html',
                         members=log_data['members'],
                         activity_types=ACTIVITY_TYPES,
                         current_period=current_period,
                         today=datetime.utcnow().strftime('%Y-%m-%d'),
                         member_activities=log_data['member_activities'],
                         member_activity_counts=log_data['member_activity_counts'],
                         member_ia_status=log_data['member_ia_status'],
                         member_exempt_status=log_data['member_exempt_status'])


@ac_bp.route('/quick_log_activity', methods=['POST'])
@hct_required
def quick_log_activity():
    """
    Accept JSON {member_id, activity_type, activity_date, logged_by, quantity}
    Returns JSON {success, message, points, count} or error.
    """
    data = request.get_json(force=True, silent=True) or {}
    member_id = data.get('member_id')
    activity_type = data.get('activity_type')
    if not member_id or not activity_type:
        return jsonify({'success': False, 'message': 'member_id and activity_type required'}), 400

    activity_date = None
    if data.get('activity_date'):
        try:
            activity_date = datetime.strptime(data.get('activity_date'), '%Y-%m-%d')
        except Exception:
            activity_date = datetime.utcnow()

    result = ac_service.log_activity(
        member_id,
        activity_type,
        activity_date=activity_date,
        description=data.get('description'),
        logged_by=data.get('logged_by', 'HC Team'),
        quantity=data.get('quantity', 1),
        mark_limited=True,
        validate_activity_type=False,
    )

    if not result['success']:
        message = result.get('message', 'Failed to log activity')
        if result.get('error') == 'no_active_period':
            return jsonify({'success': False, 'message': 'No active AC period'}), 400
        return jsonify({'success': False, 'message': message}), 400

    return jsonify({
        'success': True,
        'points': result['points'],
        'count': result['count'],
        'activity_ids': result['activity_ids'],
    })


@ac_bp.route('/quick_log_ia', methods=['POST'])
@hct_required
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

    result = ac_service.toggle_ia_status(
        member_id,
        reason=data.get('reason', 'Quick log IA'),
        approved_by=data.get('approved_by', session.get('staff_username', 'HC Team')),
    )

    if not result['success']:
        return jsonify({'success': False, 'message': result.get('message')}), 400

    return jsonify({
        'success': True,
        'is_ia': result['is_ia'],
        'message': result['message'],
    })


@ac_bp.route('/quick_log_exempt', methods=['POST'])
@hct_required
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

    result = ac_service.toggle_exempt_status(
        member_id,
        reason=data.get('reason', 'Quick log exemption'),
        approved_by=data.get('approved_by', session.get('staff_username', 'HC Team')),
    )

    if not result['success']:
        return jsonify({'success': False, 'message': result.get('message')}), 400

    return jsonify({
        'success': True,
        'is_exempt': result['is_exempt'],
        'message': result['message'],
    })


# Export AC to Excel (GET: new workbook; POST: merge uploaded workbook)
@ac_bp.route('/export_excel', methods=['GET', 'POST'])
@hct_required
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
@hct_required
def ac_member_detail(member_id):
    current_period = ac_service.get_active_period()
    if not current_period:
        flash('No active AC period.', 'error')
        return redirect(url_for('ac.ac_dashboard'))

    detail = ac_service.get_member_ac_detail(member_id, current_period.id)
    if not detail:
        from flask import abort
        abort(404)

    return render_template(
        'ac/member_detail.html',
        member=detail['member'],
        current_period=current_period,
        activities=detail['activities'],  # full list for detailed view
        aggregated_activities=detail['aggregated_activities'],  # summaries for compact view
        quota=detail['quota'],
        total_points=detail['total_points']
    )


# Ensure delete/clear endpoints exist (idempotent if already present)
@ac_bp.route('/activity/<int:activity_id>/delete', methods=['POST'])
@hct_required
def delete_ac_activity(activity_id):
    try:
        # Use service deletion
        result = ac_service.delete_activity_entry(activity_id)
        if not result['success']:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False, 'message': result.get('message')}), 404
            flash(result.get('message'), 'error')
            return redirect(url_for('ac.quick_log'))
        
        # Return JSON for AJAX requests, else redirect
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': True, 'message': 'Activity deleted'}), 200
        
        flash('Activity entry deleted.', 'success')
        member_id = result['member'].id if result.get('member') else None
        if member_id:
            return redirect(url_for('ac.ac_member_detail', member_id=member_id))
        return redirect(url_for('ac.ac_dashboard'))
    except Exception as e:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': str(e)}), 500
        flash(f'Error deleting activity: {e}', 'error')
        return redirect(url_for('ac.quick_log'))


@ac_bp.route('/member/<int:member_id>/clear_activities', methods=['POST'])
@hct_required
def clear_member_activities(member_id):
    period_id = request.form.get('period_id', type=int)
    if not period_id:
        active = ac_service.get_active_period()
        period_id = active.id if active else None

    deleted_count = ac_service.clear_member_activities(member_id, period_id)
    flash(f'Deleted {deleted_count} activity entries for member.', 'success')
    return redirect(url_for('ac.ac_member_detail', member_id=member_id))
