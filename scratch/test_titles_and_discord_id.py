import sys
import os

# Set paths
sys.path.insert(0, r"c:\Users\emend\OneDrive\Documentos\TF_System\Taskforce_System")

from database.engine import engine, get_session
from sqlmodel import Session, select
from database.tenant_models import Group
from database.ac_models import Title, ACPeriod
from services import ac_service
from utils.tenant_context import set_tenant_context, get_tenant_id
from utils.ac_reports import ACReportGenerator

def test_titles_crud_and_calculation():
    print("=== Testing Multitenant Titles CRUD & Calculation ===")
    tenant_id = 2  # Delta Sector
    set_tenant_context(tenant_id=tenant_id, permissions=["manage_ac", "edit_config"], system_role="admin")

    # Pre-cleanup any existing titles for tenant_id
    with Session(engine) as s:
        existing_titles = s.exec(select(Title).where(Title.tenant_id == tenant_id)).all()
        for et in existing_titles:
            s.delete(et)
        s.commit()

    # 1. Create a Title
    res = ac_service.create_title(
        name="Apex Strike Lead",
        activity_required="Raid",
        quantity_required=3,
        description="Awarded to the operative leading the most strikes in Delta Sector",
        period_type="cycle",
        tenant_id=tenant_id
    )
    assert res.get("success") is True, f"Failed to create: {res}"
    title = res["title"]
    print(f"Created title: ID={title.id}, name='{title.name}', tenant_id={title.tenant_id}")
    assert title.id is not None
    assert title.name == "Apex Strike Lead"
    assert title.tenant_id == tenant_id

    # 2. Get all titles for tenant
    titles = ac_service.get_all_titles(tenant_id)
    print(f"Found {len(titles)} titles for tenant {tenant_id}")
    assert any(t.id == title.id for t in titles)

    # 3. Update Title
    res_up = ac_service.update_title(
        title_id=title.id,
        name="Apex Vanguard",
        activity_required="Raid",
        quantity_required=5,
        description="Updated description",
        period_type="cycle",
        is_active=True
    )
    assert res_up.get("success") is True, f"Failed to update: {res_up}"
    updated = res_up["title"]
    assert updated.name == "Apex Vanguard"
    assert updated.quantity_required == 5
    print(f"Updated title: name='{updated.name}', quantity={updated.quantity_required}")

    # 4. Verify in Report Service
    with Session(engine) as session:
        # Check active AC period for tenant 2 or tenant 1
        period = session.exec(select(ACPeriod).where(ACPeriod.tenant_id == tenant_id)).first()
        if not period:
            period = session.exec(select(ACPeriod)).first()
        
        if period:
            report_svc = ACReportGenerator(period, [])
            rewards = report_svc.calculate_title_rewards()
            print(f"Calculated title rewards for period {period.id}: {rewards}")
            assert isinstance(rewards, dict)

    # 5. Delete Title
    del_res = ac_service.delete_title(title.id)
    assert del_res.get("success") is True, f"Failed to delete: {del_res}"
    remaining = ac_service.get_all_titles(tenant_id)
    assert not any(t.id == title.id for t in remaining)
    print("Deleted test title successfully!")


def test_discord_group_id_and_api():
    print("\n=== Testing discord_group_id on Group & API Resolution ===")
    from fastapi.testclient import TestClient
    from app import app
    from config import settings

    test_guild_id = "998877665544332211"

    # Set discord_group_id on Group 2
    with Session(engine) as session:
        grp = session.get(Group, 2)
        if grp:
            grp.discord_group_id = test_guild_id
            session.add(grp)
            session.commit()
            print(f"Set Group 2 (Delta Sector) discord_group_id to: {test_guild_id}")

    client = TestClient(app)
    api_key = getattr(settings, 'DISCORD_BOT_API_KEY', 'default-key')
    headers = {"Authorization": f"Bearer {api_key}"}

    # 1. Test GET /api/v1/groups/by-discord-id/{discord_group_id}
    res = client.get(f"/api/v1/groups/by-discord-id/{test_guild_id}", headers=headers)
    print(f"Lookup by Discord Guild ID status: {res.status_code}")
    assert res.status_code == 200
    data = res.json()
    assert data.get("success") is True
    assert data["group"]["id"] == 2
    assert data["group"]["discord_group_id"] == test_guild_id
    print(f"Group resolved correctly: ID={data['group']['id']}, Name='{data['group']['name']}'")

    # 2. Test API request scoping via X-Discord-Group-ID header
    headers_with_discord = {
        "Authorization": f"Bearer {api_key}",
        "X-Discord-Group-ID": test_guild_id
    }
    res_status = client.get("/api/v1/status", headers=headers_with_discord)
    assert res_status.status_code == 200
    print("Status endpoint successfully resolved with X-Discord-Group-ID header!")

    print("\nAll multitenant titles and discord_group_id tests passed successfully!")

if __name__ == "__main__":
    test_titles_crud_and_calculation()
    test_discord_group_id_and_api()
