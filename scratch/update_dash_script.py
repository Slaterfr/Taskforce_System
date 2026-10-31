import os

file_path = os.path.join(os.path.dirname(__file__), "..", "services", "member_service.py")
with open(file_path, "r", encoding="utf-8") as f:
    text = f.read()

target = '''def get_dashboard_data():
    """Return dashboard statistics and recent activity logs."""
    member_count = len(db_session().exec(select(Member).filter_by(is_active=True)).all())
    recent_activities = db_session().query(ActivityLog).order_by(ActivityLog.log_date.desc()).limit(5).all()
    return {
        'member_count': member_count,
        'recent_activities': recent_activities
    }'''

replacement = '''def get_dashboard_data(tenant_id=None):
    """Return dashboard statistics and recent activity logs scoped to tenant."""
    t_id = tenant_id or get_tenant_id()
    query = select(Member).where(Member.is_active == True)
    if t_id:
        query = query.where(Member.tenant_id == t_id)
    member_count = len(db_session().exec(query).all())

    act_query = db_session().query(ActivityLog)
    if t_id:
        act_query = act_query.filter(ActivityLog.tenant_id == t_id)
    recent_activities = act_query.order_by(ActivityLog.log_date.desc()).limit(5).all()
    return {
        'member_count': member_count,
        'recent_activities': recent_activities
    }'''

# Normalize line endings for replacement
norm_text = text.replace("\r\n", "\n")
norm_target = target.replace("\r\n", "\n")
norm_replacement = replacement.replace("\r\n", "\n")

if norm_target in norm_text:
    updated = norm_text.replace(norm_target, norm_replacement)
    with open(file_path, "w", encoding="utf-8", newline="") as f:
        f.write(updated.replace("\n", "\r\n"))
    print("SUCCESS")
else:
    print("TARGET NOT FOUND")

