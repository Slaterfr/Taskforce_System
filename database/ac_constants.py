"""
Activity Check constants and pure helper functions.
No database imports - safe to import anywhere.
"""

# Activity types and their point values
ACTIVITY_TYPES: dict = {
    "Mission": {"points": 0.5, "limited": False, "description": "Posted or led a mission"},
    "Supervision": {"points": 1.0, "limited": False, "description": "Supervised activities or members"},
    "Training": {"points": 1.0, "limited": False, "description": "Hosted training session"},
    "Raid": {"points": 1.5, "limited": False, "description": "Led or participated in raid"},
    "Patrol": {"points": 1.5, "limited": False, "description": "Led patrol activity"},
    "Tryout": {"points": 1.5, "limited": False, "description": "Conducted recruitment tryout"},
    "Tryout Certification": {"points": 1.0, "limited": False, "description": "Certified tryout host (host only)"},
    "Cancelled Training": {"points": 0.5, "limited": True, "description": "Training session that was cancelled (1 per cycle)"},
    "Cancelled Tryout": {"points": 0.5, "limited": True, "description": "Tryout that was cancelled (1 per cycle)"},
    "Tryout Grading": {"points": 0.5, "limited": True, "description": "Graded tryout results (1 per cycle)"},
    "Dueling Supervision/Evaluation": {"points": 0.5, "limited": True, "description": "Supervised or evaluated dueling (1 per cycle)"},
    "Joint Combat Training": {"points": 1.5, "limited": False, "description": "Participated in Joint Combat Training (JCT)"},
}

# Quota requirements by rank
AC_QUOTAS: dict = {
    "Prospect": 1.0,
    "Commander": 2.0,
    "Marshal": 2.0,
    "General": 3.0,
    "Chief General": 3.0,
}


def get_member_quota(rank: str) -> float:
    """Get AC quota for a member's rank."""
    return AC_QUOTAS.get(rank, 0.0)


def get_activity_points(activity_type: str) -> float:
    """Get point value for an activity type."""
    return ACTIVITY_TYPES.get(activity_type, {}).get("points", 0.0)


def is_limited_activity(activity_type: str) -> bool:
    """Check if activity type is limited to 1 per cycle."""
    return ACTIVITY_TYPES.get(activity_type, {}).get("limited", False)
