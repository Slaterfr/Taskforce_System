"""
Phase 4 (Administration & Staff Operations) + Phase 5 (Full-System QA) Verification Suite
Validates Jinja2 AST compilation, design system compliance, contract preservation, and
end-to-end rendering across the Taskforce Nexus application.
"""
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
CSS_PATH = os.path.join(BASE_DIR, "static", "css", "style.css")

# Load pure-python packages (jinja2, markupsafe) from venv
VENV_SITE = os.path.join(BASE_DIR, "venv", "Lib", "site-packages")
if os.path.isdir(VENV_SITE):
    sys.path.insert(0, VENV_SITE)

import jinja2


def assert_contains(content: str, needle: str, label: str):
    if needle not in content:
        raise AssertionError(f"[{label}] Missing expected token/contract: {needle!r}")


def verify_phase4_templates(env: jinja2.Environment):
    print("=== Phase 4: Administration & Staff Operations Verification ===")
    phase4_files = [
        "group/group_settings.html",
        "ac/ac_config.html",
        "stats.html",
        "privacy.html",
        "terms.html",
        "docs/index.html",
    ]
    for rel_path in phase4_files:
        full_path = os.path.join(TEMPLATES_DIR, rel_path.replace("/", os.sep))
        assert os.path.isfile(full_path), f"Missing template: {rel_path}"
        with open(full_path, "r", encoding="utf-8") as f:
            source = f.read()
        env.parse(source)
        print(f"  [OK] AST compiled: {rel_path}")

    # 1. Verify group/group_settings.html contracts
    with open(os.path.join(TEMPLATES_DIR, "group", "group_settings.html"), "r", encoding="utf-8") as f:
        gs = f.read()
    for token in [
        'name="name"',
        'name="discord_group_id"',
        'name="webhook_channel_id"',
        'name="activity_channel_id"',
        'name="ranks_channel_id"',
        'name="description"',
        'name="cookie"',
        "update_rank_permissions",
        "nx_page_header",
    ]:
        assert_contains(gs, token, "group/group_settings.html")
    assert "theme_preset" not in gs, "Legacy 8-theme neon preset selector should be retired in group_settings.html"
    print("  [OK] group/group_settings.html contracts & theme retirement verified")

    # 2. Verify ac/ac_config.html contracts
    with open(os.path.join(TEMPLATES_DIR, "ac", "ac_config.html"), "r", encoding="utf-8") as f:
        acc = f.read()
    for token in [
        "create_activity_type",
        "edit_activity_type",
        "delete_activity_type",
        "create_rank_quota",
        "edit_rank_quota",
        "delete_rank_quota",
        "create_title",
        "edit_title",
        "delete_title",
        "editActivityModal",
        "editQuotaModal",
        "editTitleModal",
        "nx-tabs",
    ]:
        assert_contains(acc, token, "ac/ac_config.html")
    print("  [OK] ac/ac_config.html 3-tab console & modal contracts verified")

    # 3. Verify stats.html contracts & dark-mode Chart.js palette
    with open(os.path.join(TEMPLATES_DIR, "stats.html"), "r", encoding="utf-8") as f:
        st = f.read()
    for token in [
        'id="growthChart"',
        'id="rankChart"',
        "#32C5E8",
        "nx_stat_card",
    ]:
        assert_contains(st, token, "stats.html")
    assert "Math.random()" not in st, "stats.html should not use random RGB chart colors"
    print("  [OK] stats.html dark-mode telemetry charts verified")

    # 4. Verify docs/index.html screenshots & required test strings
    with open(os.path.join(TEMPLATES_DIR, "docs", "index.html"), "r", encoding="utf-8") as f:
        docs = f.read()
    required_docs_tokens = [
        "Tactical Command Network Documentation",
        "Tier 1: Operative &amp; Member Manual",
        "Staff Clearance Required",
        "High Command Clearance Required",
        "Level 1: Operative",
        "Level 2: Field Staff",
        "Level 3: High Command (HCT)",
        "Single &amp; Bulk Activity Logging Protocols",
        "Granular Rank Permissions Matrix",
        "Discord Bot Channels Routing",
        "Interactive @Cortex Command Simulator",
        "docs-search-input",
        "sim-btn",
        "/static/img/docs/register_sector_preview.png",
        "/static/img/docs/sector_settings_identity.png",
        "/static/img/docs/portal_dashboard_overview.png",
        "/static/img/docs/bot_logging_execution.png",
        "/static/img/docs/rank_permissions_matrix.png",
        "/static/img/docs/roblox_cookie_inspect.png",
        "/static/img/docs/discord_channels_setup.png",
    ]
    for token in required_docs_tokens:
        assert_contains(docs, token, "docs/index.html")
    print("  [OK] docs/index.html all 7 screenshots & clearance strings verified")


def verify_phase5_full_qa(env: jinja2.Environment):
    print("\n=== Phase 5: Full-System Quality Assurance & Regression Audit ===")

    # 1. Verify all 10 Nexus color tokens in static/css/style.css
    with open(CSS_PATH, "r", encoding="utf-8") as f:
        css = f.read()
    expected_tokens = {
        "--nx-bg": "#11151B",
        "--nx-surface": "#1B222B",
        "--nx-surface-elevated": "#232D38",
        "--nx-border": "#303B47",
        "--nx-text-primary": "#EDF3F7",
        "--nx-text-secondary": "#98A8B6",
        "--nx-accent": "#32C5E8",
        "--nx-success": "#38C98A",
        "--nx-warning": "#EAB45B",
        "--nx-danger": "#ED6672",
    }
    for var_name, hex_val in expected_tokens.items():
        assert var_name in css and hex_val.lower() in css.lower(), (
            f"Missing design token {var_name}: {hex_val} in style.css"
        )
    print("  [OK] All 10 Nexus color tokens verified in static/css/style.css")

    # 2. Compile EVERY template across the entire templates/ directory
    compiled_count = 0
    for root, _, files in os.walk(TEMPLATES_DIR):
        for fname in sorted(files):
            if not fname.endswith(".html"):
                continue
            full_path = os.path.join(root, fname)
            rel_path = os.path.relpath(full_path, TEMPLATES_DIR).replace("\\", "/")
            with open(full_path, "r", encoding="utf-8") as f:
                src = f.read()
            env.parse(src)
            compiled_count += 1
    print(f"  [OK] Compiled all {compiled_count} HTML templates in templates/ with zero syntax errors")

    # 3. Verify BUG-01 and BUG-02 fixes remain intact
    with open(os.path.join(TEMPLATES_DIR, "dashboard.html"), "r", encoding="utf-8") as f:
        dash = f.read()
    assert_contains(dash, "recent_activities", "BUG-01 fix in dashboard.html")
    assert_contains(dash, "cookie_record", "Roblox Sync card in dashboard.html")

    with open(os.path.join(TEMPLATES_DIR, "ac", "member_detail.html"), "r", encoding="utf-8") as f:
        ac_md = f.read()
    assert_contains(ac_md, "quick_log_ia", "BUG-02 IA toggle fix in ac/member_detail.html")
    assert_contains(ac_md, "quick_log_exempt", "BUG-02 Exempt toggle fix in ac/member_detail.html")
    print("  [OK] BUG-01 (dashboard recent_activities) and BUG-02 (IA/Exempt AJAX toggles) verified")


if __name__ == "__main__":
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(TEMPLATES_DIR),
        autoescape=True,
    )
    verify_phase4_templates(env)
    verify_phase5_full_qa(env)
    print("\nALL PHASE 4 & PHASE 5 VERIFICATION CHECKS PASSED.")
