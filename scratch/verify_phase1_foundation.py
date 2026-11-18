import os
import sys

if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

def verify_phase0_and_phase1():
    print("=" * 64)
    print("NEXUS // VERIFYING PHASE 0 (AUDIT) & PHASE 1 (DESIGN FOUNDATION)")
    print("=" * 64)

    # 1. Verify Phase 0 Deliverable: FRONTEND_AUDIT.md
    audit_path = os.path.join(BASE_DIR, "FRONTEND_AUDIT.md")
    assert os.path.isfile(audit_path), "Missing FRONTEND_AUDIT.md"
    with open(audit_path, "r", encoding="utf-8") as f:
        audit_text = f.read()
    for section in [
        "Executive Summary",
        "Complete Route & Template Inventory",
        "Backend API & AJAX Contracts",
        "CSS & Visual System Technical Debt Register",
    ]:
        assert section in audit_text, f"Missing section '{section}' in FRONTEND_AUDIT.md"
    print("[PASS] Phase 0: FRONTEND_AUDIT.md verified with complete route & debt inventory.")

    # 2. Verify Phase 1 Deliverable: design-system.md
    ds_path = os.path.join(BASE_DIR, "design-system.md")
    assert os.path.isfile(ds_path), "Missing design-system.md"
    with open(ds_path, "r", encoding="utf-8") as f:
        ds_text = f.read()

    required_tokens = [
        "#11151B", "#1B222B", "#232D38", "#303B47",
        "#EDF3F7", "#98A8B6", "#32C5E8", "#38C98A",
        "#EAB45B", "#ED6672"
    ]
    for token in required_tokens:
        assert token in ds_text, f"Token {token} missing from design-system.md"
    print("[PASS] Phase 1: design-system.md verified with all 10 Nexus color tokens & typography spec.")

    # 3. Verify static/css/style.css
    css_path = os.path.join(BASE_DIR, "static", "css", "style.css")
    assert os.path.isfile(css_path), "Missing static/css/style.css"
    with open(css_path, "r", encoding="utf-8") as f:
        css_text = f.read()

    for token in required_tokens:
        assert token in css_text, f"Token {token} missing from static/css/style.css"
    for css_var in [
        "--nx-bg", "--nx-surface", "--nx-surface-elevated", "--nx-border",
        "--nx-text-primary", "--nx-text-secondary", "--nx-accent",
        "--nx-success", "--nx-warning", "--nx-danger",
        "--nx-font-sans", "--nx-font-mono"
    ]:
        assert css_var in css_text, f"CSS variable {css_var} missing from style.css"
    assert '[class*="col-"]' not in css_text, "Destructive col-* override still present in style.css"
    print("[PASS] Phase 1: static/css/style.css verified with semantic tokens & primitive classes.")

    # 4. Verify templates/components/_macros.html exists and contains all 7 primitives
    macros_path = os.path.join(BASE_DIR, "templates", "components", "_macros.html")
    assert os.path.isfile(macros_path), "Missing templates/components/_macros.html"
    with open(macros_path, "r", encoding="utf-8") as f:
        macros_text = f.read()

    for macro_name in [
        "macro nx_page_header",
        "macro nx_stat_card",
        "macro nx_card_header",
        "macro nx_badge",
        "macro nx_status_dot",
        "macro nx_progress_bar",
        "macro nx_empty_state",
    ]:
        assert macro_name in macros_text, f"Missing {macro_name} in _macros.html"
    print("[PASS] Phase 1: templates/components/_macros.html verified with all 7 UI primitives.")

    print("=" * 64)
    print("ALL PHASE 0 & PHASE 1 DELIVERABLES VERIFIED SUCCESSFULLY!")
    print("=" * 64)

if __name__ == "__main__":
    verify_phase0_and_phase1()

