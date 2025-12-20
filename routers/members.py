from flask import Blueprint, render_template, request, flash, redirect, url_for, session, current_app
from database.models import db, Member, ActivityLog, PromotionLog, RankMapping
from utils.auth import staff_required
from utils.roblox_sync import sync_member_to_roblox, add_member_to_roblox, remove_member_from_roblox
from datetime import datetime

members_bp = Blueprint('members', __name__)


@members_bp.route('/dashboard')
@staff_required
def dashboard():
    member_count = Member.query.filter_by(is_active=True).count()
    recent_activities = ActivityLog.query.order_by(ActivityLog.log_date.desc()).limit(5).all()
    return render_template('dashboard.html',
                           member_count=member_count,
                           recent_activities=recent_activities)


# Members list / CRUD
@members_bp.route('/members')
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


@members_bp.route('/member/<int:member_id>')
@staff_required
def member_detail(member_id):
    member = Member.query.get_or_404(member_id)
    activities = ActivityLog.query.filter_by(member_id=member_id).order_by(ActivityLog.log_date.desc()).all()
    promotions = PromotionLog.query.filter_by(member_id=member_id).order_by(PromotionLog.promotion_date.desc()).all()
    return render_template('member_detail.html', member=member, activities=activities, promotions=promotions)


@members_bp.route('/add_member', methods=['GET', 'POST'])
@staff_required
def add_member():
    if request.method == 'POST':
        discord_username = request.form.get('discord_username', '').strip()
        roblox_username = request.form.get('roblox_username', '').strip() or None
        current_rank = request.form.get('current_rank', 'Aspirant').strip()

        if not discord_username:
            flash('Discord username is required', 'error')
            return redirect(url_for('members.add_member'))

        existing = Member.query.filter_by(discord_username=discord_username).first()
        if existing:
            flash('Member with this Discord username already exists!', 'error')
            return redirect(url_for('members.add_member'))

        m = Member(discord_username=discord_username, roblox_username=roblox_username, current_rank=current_rank)
        db.session.add(m)
        db.session.commit()
        
        # Sync to Roblox if enabled and member has Roblox username
        if current_app.config.get('ROBLOX_SYNC_ENABLED') and m.roblox_username:
            result = add_member_to_roblox(m)
            if not result['success']:
                flash(f"Member added, but Roblox sync failed: {result['message']}", 'warning')
        
        flash('Member added', 'success')
        return redirect(url_for('members.member_detail', member_id=m.id))
    return render_template('add_member.html')


@members_bp.route('/member/<int:member_id>/edit', methods=['GET', 'POST'])
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
        return redirect(url_for('members.member_detail', member_id=member.id))
    return render_template('edit_member.html', member=member, available_ranks=available_ranks)


@members_bp.route('/member/<int:member_id>/delete', methods=['POST'])
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
    return redirect(url_for('members.members'))


@members_bp.route('/promote_member', methods=['GET', 'POST'])
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
            return redirect(url_for('members.promote_member'))

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
        return redirect(url_for('members.member_detail', member_id=member.id))

    # GET: show form
    members_list = Member.query.filter_by(is_active=True).order_by(Member.discord_username).all()
    return render_template('promote_member.html', members=members_list, available_ranks=available_ranks)

@members_bp.route('/stats')
@staff_required
def stats():
    """Member Statistics Dashboard"""
    from utils.stats_logger import get_stats_history
    import json
    
    # Get last 30 days of history
    data = get_stats_history(days=30)
    
    # Calculate some quick summary stats
    total_members = data['totals'][-1] if data['totals'] else 0
    
    # Find rank with most members
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

