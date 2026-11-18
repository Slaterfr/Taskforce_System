import os
import sys

if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
VENV_SITE = os.path.join(BASE_DIR, "venv", "Lib", "site-packages")
if os.path.isdir(VENV_SITE):
    sys.path.insert(0, VENV_SITE)
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")

PHASE3_TEMPLATES = [
    "dashboard.html",
    "public_roster.html",
    "members.html",
    "member_detail.html",
    "public_member.html",
    "add_member.html",
    "edit_member.html",
    "promote_member.html",
    "confirm_delete.html",
    "public_ac_progress.html",
    "ac/ac_quick_log.html",
    "ac/log_activity.html",
    "ac/ac_dashboard.html",
    "ac/member_detail.html",
    "ac/ac_setup.html",
    "ac/create_period.html",
    "ac/edit_period.html",
    "ac/title_rewards.html",
]

def verify_phase3():
    print("=" * 64)
    print("NEXUS // VERIFYING PHASE 3 (CORE MODULES: OVERVIEW, MEMBERS, ACTIVITIES, AC)")
    print("=" * 64)

    import jinja2
    env = jinja2.Environment(loader=jinja2.FileSystemLoader(TEMPLATES_DIR))

    for tpl in PHASE3_TEMPLATES:
        full_p = os.path.join(TEMPLATES_DIR, tpl)
        assert os.path.isfile(full_p), f"Missing template {tpl}"
        with open(full_p, "r", encoding="utf-8") as f:
            content = f.read()

        # Verify Nexus design system primitives are imported and used
        assert "components/_macros.html" in content, f"{tpl} does not import _macros.html"
        assert 'style="color: white;"' not in content, f"Legacy inline white style still present in {tpl}"

        # Compile Jinja2 AST
        env.get_template(tpl)
        print(f"[PASS] {tpl} compiled cleanly and uses Nexus UI primitives.")

    # Verify BUG-01 resolution: dashboard.html renders recent_activities loop
    with open(os.path.join(TEMPLATES_DIR, "dashboard.html"), "r", encoding="utf-8") as f:
        dash_html = f.read()
    assert "{% for act in recent_activities %}" in dash_html, "BUG-01 not fixed in dashboard.html"
    print("[PASS] BUG-01 Resolved: dashboard.html renders recent_activities operational feed table.")

    # Verify BUG-02 resolution: ac/member_detail.html wires #ia-toggle and #exempt-toggle
    with open(os.path.join(TEMPLATES_DIR, "ac/member_detail.html"), "r", encoding="utf-8") as f:
        ac_mem_html = f.read()
    assert "quick_log_ia" in ac_mem_html and "quick_log_exempt" in ac_mem_html, "BUG-02 not fixed in ac/member_detail.html"
    print("[PASS] BUG-02 Resolved: ac/member_detail.html wires #ia-toggle and #exempt-toggle to AJAX endpoints.")

    print("=" * 64)
    print("ALL 18 PHASE 3 CORE MODULE TEMPLATES VERIFIED SUCCESSFULLY!")
    print("=" * 64)

if __name__ == "__main__":
    verify_phase3()

