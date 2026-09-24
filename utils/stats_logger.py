from database.engine import db_session
from sqlmodel import select
from datetime import datetime, timedelta
from database.models import Member, MemberStats
from config import settings
import logging

logger = logging.getLogger(__name__)

from utils.tenant_context import set_tenant_context, get_tenant_id

def capture_member_stats(tenant_id: Optional[int] = None):
    """
    Captures a snapshot of current member counts and rank distribution for a tenant.
    Saves to the MemberStats table.
    """
    effective_tenant_id = tenant_id or get_tenant_id() or 1
    set_tenant_context(effective_tenant_id)
    try:
        # Get all active members for this tenant
        members = db_session().exec(
            select(Member).where(Member.tenant_id == effective_tenant_id, Member.is_active == True)
        ).all()
        total_members = len(members)

        # Calculate rank distribution
        rank_counts = {}
        for member in members:
            rank = member.current_rank
            rank_counts[rank] = rank_counts.get(rank, 0) + 1

        # Create snapshot
        stats = MemberStats(
            tenant_id=effective_tenant_id,
            timestamp=datetime.utcnow(),
            total_members=total_members,
            rank_counts=rank_counts
        )

        db_session().add(stats)
        db_session().commit()

        logger.info(f"✅ [Tenant {effective_tenant_id}] Captured member stats: {total_members} members")
        return True

        
    except Exception as e:
        logger.error(f"❌ Error capturing member stats: {e}")
        db_session().rollback()
        return False

def get_stats_history(days=30):
    """
    Retrieves stats history for the last N days.
    Returns formatted data for charts.
    """
    try:
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        # Get stats ordered by date
        history = db_session().query(MemberStats).filter(
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
        logger.error(f"❌ Error retrieving stats history: {e}")
        return {
            'dates': [],
            'totals': [],
            'latest_ranks': {}
        }
