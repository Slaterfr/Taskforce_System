from sqlmodel import create_engine, Session, SQLModel
from sqlalchemy.orm import scoped_session, sessionmaker, with_loader_criteria
from sqlalchemy import event
from config import settings
from utils.tenant_context import get_tenant_id

# Tenant-scoped models that require automated isolation
from database.models import (
    Member, ActivityLog, PromotionLog, RankMapping, MemberStats,
    Mission, MissionCompletion, MonthlyStat
)
from database.ac_models import (
    ACPeriod, ActivityEntry, MonthlyActivityEntry,
    InactivityNotice, ACExemption, PeriodStatistics,
    ActivityType, RankQuota, Title
)

from database.permission_models import (
    RankPermission
)

TENANT_SCOPED_MODELS = [
    Member, ActivityLog, PromotionLog, RankMapping, MemberStats,
    Mission, MissionCompletion, MonthlyStat,
    ACPeriod, ActivityEntry, MonthlyActivityEntry,
    InactivityNotice, ACExemption, PeriodStatistics,
    ActivityType, RankQuota, Title,
    RankPermission
]




engine = create_engine(
    settings.DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {},
)

db_session = scoped_session(sessionmaker(autocommit=False, autoflush=False, bind=engine, class_=Session))

@event.listens_for(Session, "do_orm_execute")
def _apply_tenant_isolation_filters(execute_state):
    """
    Automatically injects WHERE tenant_id = :current_tenant_id into ORM select queries.
    Can be bypassed if execute_state execution_options has skip_tenant_filter=True.
    """
    if execute_state.is_select and not execute_state.execution_options.get("skip_tenant_filter", False):
        tenant_id = get_tenant_id()
        if tenant_id is not None:
            execute_state.statement = execute_state.statement.options(
                *[
                    with_loader_criteria(
                        model,
                        lambda cls: cls.tenant_id == tenant_id,
                        include_aliases=True
                    )
                    for model in TENANT_SCOPED_MODELS
                ]
            )

@event.listens_for(Session, "before_flush")
def _auto_set_tenant_id(session, flush_context, instances):
    """
    Automatically populates tenant_id on newly created instances if not explicitly set.
    """
    tenant_id = get_tenant_id()
    if tenant_id is not None:
        for obj in session.new:
            if hasattr(obj, "tenant_id"):
                curr = getattr(obj, "tenant_id", None)
                if curr is None or (curr == 1 and tenant_id != 1):
                    setattr(obj, "tenant_id", tenant_id)

def get_session():
    """FastAPI dependency that yields a database session."""
    with Session(engine) as session:
        yield session

def create_db():
    SQLModel.metadata.create_all(engine)

