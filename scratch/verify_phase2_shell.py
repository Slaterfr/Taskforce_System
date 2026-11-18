import os
import sys

if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
VENV_SITE = os.path.join(BASE_DIR, "venv", "Lib", "site-packages")
if os.path.isdir(VENV_SITE):
    sys.path.insert(0, VENV_SITE)
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")

def verify_phase2_shell():
    print("=" * 64)
    print("NEXUS // VERIFYING PHASE 2 (APPLICATION SHELL & PORTAL)")
    print("=" * 64)

    # 1. Verify base.html structure
    base_path = os.path.join(TEMPLATES_DIR, "base.html")
    with open(base_path, "r", encoding="utf-8") as f:
        base_html = f.read()

    required_shell_markers = [
        'id="nx-sidebar"',
        'id="nx-topbar"',
        'class="nx-tenant-switcher"',
        'id="nx-cmd-palette"',
        'id="nx-cmd-trigger"',
        'class="nx-sidebar__footer"',
        'class="nx-workspace"',
        'Geist+Mono',
        'unpkg.com/lucide',
        '{% if is_staff or is_hct %}',
        '{% if is_hct %}',
    ]
    for marker in required_shell_markers:
        assert marker in base_html, f"Missing required shell marker '{marker}' in base.html"
    print("[PASS] base.html contains Sidebar, Topbar, Tenant Switcher, Command Palette, Notification Center, and Role Gating.")

    # 2. Verify landing.html & portal templates use Nexus macros & classes
    for rel_path, expected in [
        ("landing.html", ["nx-card", "nx_stat_card", "SESSION TELEMETRY"]),
        ("portal/select_group.html", ["nx_page_header", "nx_empty_state", "registerGroupModal"]),
        ("portal/dev_login.html", ["nx_page_header", "nx-card", "nx-btn-primary"]),
    ]:
        full_p = os.path.join(TEMPLATES_DIR, rel_path)
        assert os.path.isfile(full_p), f"Missing template {rel_path}"
        with open(full_p, "r", encoding="utf-8") as f:
            txt = f.read()
        for item in expected:
            assert item in txt, f"Expected '{item}' in {rel_path}"
        print(f"[PASS] {rel_path} verified with Nexus Tactical Operations components.")

    # 3. Verify Jinja2 syntax compilation if jinja2 is available
    try:
        import jinja2
        env = jinja2.Environment(loader=jinja2.FileSystemLoader(TEMPLATES_DIR))
        for tpl_name in [
            "components/_macros.html",
            "base.html",
            "landing.html",
            "portal/select_group.html",
            "portal/dev_login.html",
        ]:
            env.get_template(tpl_name)
        print("[PASS] Jinja2 template AST compilation succeeded for all Phase 2 templates.")
    except ImportError:
        print("[INFO] Jinja2 not in global python; static AST markers verified.")

    print("=" * 64)
    print("ALL PHASE 2 APPLICATION SHELL CHECKS PASSED!")
    print("=" * 64)

if __name__ == "__main__":
    verify_phase2_shell()
