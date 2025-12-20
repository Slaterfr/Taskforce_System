from datetime import datetime, timedelta
from database.models import db, Member, MemberStats
from flask import current_app

def capture_member_stats():
    """
    Captures a snapshot of current member counts and rank distribution.
    Saves to the MemberStats table.
    """
    try:
        # Get all active members
        members = Member.query.filter_by(is_active=True).all()
        total_members = len(members)
        
        # Calculate rank distribution
        rank_counts = {}
        for member in members:
            rank = member.current_rank
            rank_counts[rank] = rank_counts.get(rank, 0) + 1
            
        # Create snapshot
        stats = MemberStats(
            timestamp=datetime.utcnow(),
            total_members=total_members,
            rank_counts=rank_counts
        )
        
        db.session.add(stats)
        db.session.commit()
        
        current_app.logger.info(f"✅ Captured member stats: {total_members} members")
        return True
        
    except Exception as e:
        current_app.logger.error(f"❌ Error capturing member stats: {e}")
        db.session.rollback()
        return False

def get_stats_history(days=30):
    """
    Retrieves stats history for the last N days.
    Returns formatted data for charts.
    """
    try:
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        # Get stats ordered by date
        history = MemberStats.query.filter(
            MemberStats.timestamp >= cutoff_date
        ).order_by(MemberStats.timestamp.asc()).all()
        
        # Format data for Chart.js
        dates = [entry.timestamp.strftime('%Y-%m-%d') for entry in history]
        totals = [entry.total_members for entry in history]
        
        # Get latest rank distribution
        latest_ranks = history[-1].rank_counts if history else {}
        
        return {
            'dates': dates,
            'totals': totals,
            'latest_ranks': latest_ranks
        }
    except Exception as e:
        current_app.logger.error(f"❌ Error retrieving stats history: {e}")
        return {
            'dates': [],
            'totals': [],
            'latest_ranks': {}
        }
