from io import BytesIO
from typing import List
from datetime import datetime
from openpyxl import Workbook, load_workbook
from openpyxl.utils import get_column_letter
from database.models import Member
from database.ac_models import ACPeriod, ActivityEntry, InactivityNotice, get_member_quota

def _gather_ac_rows(period: ACPeriod) -> List[List]:
    """Return list of rows (including header) for the AC period"""
    header = [
        "Rank",
        "Discord Username",
        "Roblox Username",
        "Quota",
        "Points",
        "Percentage",
        "Status",
        "Protected (IA)",
        "Recent Activities"
    ]
    rows = [header]

    if not period:
        return rows

    # Query members with quota
    members = Member.query.filter(Member.is_active == True).order_by(Member.current_rank, Member.discord_username).all()
    for m in members:
        quota = get_member_quota(m.current_rank) or 0
        if quota == 0:
            # skip ranks with no quota
            continue

        total_points = (
            ActivityEntry.query.with_entities(
                ActivityEntry.points
            )
            .filter(ActivityEntry.member_id == m.id, ActivityEntry.ac_period_id == period.id)
            .all()
        )
        total_points = sum(p[0] for p in total_points) if total_points else 0.0

        ia = InactivityNotice.query.filter_by(member_id=m.id, ac_period_id=period.id, protects_ac=True).first()
        recent_acts = ActivityEntry.query.filter_by(member_id=m.id, ac_period_id=period.id).order_by(ActivityEntry.activity_date.desc()).limit(5).all()
        recent_str = "; ".join(f"{a.activity_date.strftime('%Y-%m-%d')}:{a.activity_type}({a.points})" for a in recent_acts)

        pct = round(min(100.0, (total_points / quota) * 100.0), 2) if quota else 0.0
        status = "Protected (IA)" if ia else ("Passed" if total_points >= quota else "In Progress")

        rows.append([
            m.current_rank,
            m.discord_username,
            m.roblox_username or "",
            quota,
            total_points,
            pct,
            status,
            "Yes" if ia else "No",
            recent_str
        ])

    return rows

def _write_rows_to_sheet(wb: Workbook, sheet_name: str, rows: List[List]):
    # create safe unique sheet name
    name = sheet_name[:31]  # Excel limit
    if name in wb.sheetnames:
        # append a suffix
        idx = 1
        base = name
        while f"{base}_{idx}" in wb.sheetnames:
            idx += 1
        name = f"{base}_{idx}"

    ws = wb.create_sheet(title=name)
    for r_idx, row in enumerate(rows, start=1):
        for c_idx, value in enumerate(row, start=1):
            ws.cell(row=r_idx, column=c_idx, value=value)

    # Auto-adjust column widths a bit
    for i, _ in enumerate(rows[0], start=1):
        col = get_column_letter(i)
        max_len = max(
            (len(str(cell)) if cell is not None else 0)
            for cell in (r[i-1] for r in rows)
        )
        ws.column_dimensions[col].width = min(max(10, max_len + 2), 60)

def generate_ac_workbook_bytes(period_id: int = None) -> (BytesIO, str):
    """
    Build a new workbook for given AC period_id (or active if None).
    Returns (BytesIO, filename).
    """
    if period_id:
        period = ACPeriod.query.get(period_id)
    else:
        period = ACPeriod.query.filter_by(is_active=True).first()

    period_name = period.period_name if period else f"AC_{datetime.utcnow().strftime('%Y%m%d')}"
    rows = _gather_ac_rows(period)

    wb = Workbook()
    # remove default sheet
    default = wb.active
    wb.remove(default)
    _write_rows_to_sheet(wb, f"AC_{period_name}", rows)

    out = BytesIO()
    wb.save(out)
    out.seek(0)
    filename = f"AC_{period_name}.xlsx"
    return out, filename

def merge_into_uploaded_workbook_bytes(uploaded_file_stream, period_id: int = None) -> (BytesIO, str):
    """
    Load uploaded workbook (file-like), append a sheet with the AC data, and return bytes.
    """
    # load existing
    uploaded_file_stream.seek(0)
    try:
        wb = load_workbook(uploaded_file_stream)
    except Exception:
        # if load fails, create new workbook
        wb = Workbook()
        wb.remove(wb.active)

    if period_id:
        period = ACPeriod.query.get(period_id)
    else:
        period = ACPeriod.query.filter_by(is_active=True).first()

    period_name = period.period_name if period else f"AC_{datetime.utcnow().strftime('%Y%m%d')}"
    rows = _gather_ac_rows(period)
    _write_rows_to_sheet(wb, f"AC_{period_name}", rows)

    out = BytesIO()
    wb.save(out)
    out.seek(0)
    filename = f"merged_AC_{period_name}.xlsx"
    return out, filename