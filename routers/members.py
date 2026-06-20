from flask import Blueprint, render_template, request, flash, redirect, url_for, session, current_app
from services import member_service
from utils.auth import staff_required

members_bp = Blueprint('members', __name__)


@members_bp.route('/dashboard')
@staff_required
def dashboard():
    dashboard_data = member_service.get_dashboard_data()
    return render_template('dashboard.html',
                           member_count=dashboard_data['member_count'],
                           recent_activities=dashboard_data['recent_activities'])


@members_bp.route('/members')
@staff_required
def members():
    search = request.args.get('search', '')
    members_list = member_service.search_members(search)
    return render_template('members.html', members=members_list, search=search)


@members_bp.route('/member/<int:member_id>')
@staff_required
def member_detail(member_id):
    detail = member_service.get_member_profile_details(member_id)
    if not detail:
        from flask import abort
        abort(404)
    return render_template('member_detail.html',
                           member=detail['member'],
                           activities=detail['activities'],
                           promotions=detail['promotions'])


@members_bp.route('/add_member', methods=['GET', 'POST'])
@staff_required
def add_member():
    if request.method == 'POST':
        result = member_service.create_member(
            request.form.get('discord_username', ''),
            roblox_username=request.form.get('roblox_username'),
            current_rank=request.form.get('current_rank', 'Aspirant'),
        )

        if not result['success']:
            if result.get('error') == 'member_exists':
                flash('Member with this Discord username already exists!', 'error')
            else:
                flash(result.get('message', 'Failed to add member'), 'error')
            return redirect(url_for('members.add_member'))

        member = result['member']
        roblox_sync = result.get('roblox_sync', {})
        if not roblox_sync.get('success') and member.roblox_username:
            flash(f"Member added, but Roblox sync failed: {roblox_sync.get('message')}", 'warning')

        flash('Member added', 'success')
        return redirect(url_for('members.member_detail', member_id=member.id))

    return render_template('add_member.html')


@members_bp.route('/member/<int:member_id>/edit', methods=['GET', 'POST'])
@staff_required
def edit_member(member_id):
    member = member_service.get_member(member_id, active_only=False)
    if not member:
        from flask import abort
        abort(404)
    available_ranks = member_service.get_available_ranks()

    if request.method == 'POST':
        result = member_service.update_member_profile(
            member_id,
            discord_username=request.form.get('discord_username', member.discord_username),
            roblox_username=request.form.get('roblox_username', member.roblox_username),
            current_rank=request.form.get('current_rank', member.current_rank),
        )

        if not result['success']:
            flash(result.get('message', 'Failed to update member'), 'error')
            return redirect(url_for('members.edit_member', member_id=member_id))

        roblox_sync = result.get('roblox_sync', {})
        if result.get('rank_changed') and not roblox_sync.get('success'):
            if roblox_sync.get('message') == 'Cannot sync to Roblox (no Roblox ID)':
                flash('Member updated, but cannot sync to Roblox (no Roblox ID)', 'warning')
            elif current_app.config.get('ROBLOX_SYNC_ENABLED'):
                flash(f"Member updated, but Roblox sync failed: {roblox_sync.get('message')}", 'warning')

        flash('Member updated', 'success')
        return redirect(url_for('members.member_detail', member_id=member_id))

    return render_template('edit_member.html', member=member, available_ranks=available_ranks)


@members_bp.route('/member/<int:member_id>/delete', methods=['POST'])
@staff_required
def delete_member(member_id):
    result = member_service.deactivate_member(member_id)
    if not result['success']:
        flash(result.get('message', 'Member not found'), 'error')
        return redirect(url_for('members.members'))

    roblox_sync = result.get('roblox_sync', {})
    if not roblox_sync.get('success') and current_app.config.get('ROBLOX_SYNC_ENABLED'):
        flash(f"Member removed from system, but Roblox sync failed: {roblox_sync.get('message')}", 'warning')

    flash('Member removed', 'success')
    return redirect(url_for('members.members'))


@members_bp.route('/promote_member', methods=['GET', 'POST'])
@staff_required
def promote_member():
    """Promote a member and record a PromotionLog"""
    available_ranks = member_service.get_available_ranks()

    if request.method == 'POST':
        member_id = request.form.get('member_id', type=int)
        new_rank = request.form.get('new_rank', '').strip()
        reason = request.form.get('reason', '').strip()
        promoted_by = request.form.get('promoted_by', '').strip() or session.get('staff_username', 'Staff')

        result = member_service.promote_member(
            member_id,
            new_rank,
            reason=reason,
            promoted_by=promoted_by,
        )

        if not result['success']:
            flash(result.get('message', 'Promotion failed'), 'error')
            return redirect(url_for('members.promote_member'))

        member = result['member']
        roblox_sync = result.get('roblox_sync', {})
        if not result.get('unchanged') and not roblox_sync.get('success'):
            if roblox_sync.get('message') == 'Cannot sync to Roblox (no Roblox ID)':
                flash('Promotion saved, but cannot sync to Roblox (no Roblox ID)', 'warning')
            elif current_app.config.get('ROBLOX_SYNC_ENABLED'):
                flash(f"Promotion saved, but Roblox sync failed: {roblox_sync.get('message')}", 'warning')

        flash(
            f'{member.discord_username} promoted from {result["old_rank"]} to {result["new_rank"]}',
            'success',
        )
        return redirect(url_for('members.member_detail', member_id=member.id))

    members_list = member_service.get_all_active_members()
    return render_template('promote_member.html', members=members_list, available_ranks=available_ranks)


@members_bp.route('/stats')
@staff_required
def stats():
    """Member Statistics Dashboard"""
    from utils.stats_logger import get_stats_history
    import json

    data = get_stats_history(days=30)
    total_members = data['totals'][-1] if data['totals'] else 0

    latest_ranks = data['latest_ranks']
    most_populated_rank = "N/A"
    max_count = 0
    if latest_ranks:
        most_populated_rank = max(latest_ranks, key=latest_ranks.get)
        max_count = latest_ranks[most_populated_rank]

    return render_template('stats.html',
                          dates=json.dumps(data['dates']),
                          totals=json.dumps(data['totals']),
                          rank_labels=json.dumps(list(latest_ranks.keys())),
                          rank_values=json.dumps(list(latest_ranks.values())),
                          total_members=total_members,
                          most_populated_rank=most_populated_rank,
                          most_populated_count=max_count)
