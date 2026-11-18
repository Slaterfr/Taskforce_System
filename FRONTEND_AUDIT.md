# NEXUS — Phase 0: Comprehensive Frontend Architecture & Technical Debt Audit

**Version:** 1.0  
**Project:** Taskforce Nexus (`Taskforce_System`)  
**Audit Status:** Complete (Phase 0 Baseline)  
**Target Design Direction:** Tactical Operations (`#11151B` / `#1B222B` / `#232D38` / `#303B47` / `#32C5E8`)

---

## 1. Executive Summary

Taskforce Nexus is a multi-tenant operational command and personnel management platform for Roblox groups with real-time Discord bot integration (`@Cortex`). While its backend architecture (FastAPI, SQLModel, Dual-JWT Roblox OAuth2, row-level tenant isolation, and live Roblox/Discord API synchronization) is production-capable, the **frontend layer exhibits three distinct generations of inconsistent UI development**:

1. **Generation 1 (Legacy Raw HTML / Unstyled Prototypes):** 11 templates (`member_detail.html`, `add_member.html`, `edit_member.html`, `promote_member.html`, `ac/ac_quick_log.html`, `ac/log_activity.html`, `ac/member_detail.html`, `ac/ac_setup.html`, `ac/create_period.html`, `ac/edit_period.html`, `stats.html`) render raw unstyled HTML tags (`<h3 style="color: white;">`, unstyled `<ul>` lists, or white Bootstrap 4 cards) directly onto a dark background.
2. **Generation 2 (Neon Purple Glassmorphism):** Core tables and dashboards (`dashboard.html`, `members.html`, `public_roster.html`, `public_ac_progress.html`, `ac/ac_dashboard.html`) rely on `static/css/style.css` with heavy purple gradients (`#7e22ce` → `#a855f7`), `backdrop-filter: blur(20px)`, `16px` card radii, and aggressive `!important` overrides.
3. **Generation 3 (Monolithic Inline-Styled Views):** Newer multi-tenant pages (`group/group_settings.html`, `ac/ac_config.html`, `docs/index.html`, `landing.html`) embed hundreds of inline `style="background: rgba(15, 23, 42, 0.75) !important; ..."` attributes directly inside Jinja2 markup, bypassing shared CSS classes.

---

## 2. Frontend Stack & Rendering Pipeline

| Layer | Technology / File | Role & Behavior |
|---|---|---|
| **Web Framework** | FastAPI (`app.py`) | Serves HTML routes, REST API endpoints (`/api/v1/*`), and static assets (`/static`). |
| **Templating Engine** | Jinja2 (`utils/templates.py`) | Server-Side Rendered (SSR) HTML templates in `Taskforce_System/templates/`. |
| **Global Context Injector** | `custom_TemplateResponse` ([`utils/templates.py`](file:///c:/Users/emend/OneDrive/Documentos/TF_System/Taskforce_System/utils/templates.py)) | Automatically injects `tenant_context`, `current_group_name`, `current_group_id`, `roblox_username`, `roblox_id`, `is_roblox_user`, `system_role`, `is_staff`, `is_hct`, `has_permission(perm)`, `url_for`, and `current_theme` into every template render call. |
| **CSS Framework** | Bootstrap 5.3.2 CDN + [`static/css/style.css`](file:///c:/Users/emend/OneDrive/Documentos/TF_System/Taskforce_System/static/css/style.css) | Bootstrap grid/utilities overlaid by 1,212 lines of custom CSS variables and `!important` overrides. |
| **Typography** | Google Fonts (`Outfit` + `JetBrains Mono`) | Loaded in `base.html`; migrating to **Geist Sans** + **Geist Mono**. |
| **Iconography** | FontAwesome 6.4.0 (`all.js`) | Loaded via defer script in `base.html`; migrating to **Lucide Icons** with FontAwesome fallback for brand glyphs (`fa-roblox`, `fa-discord`). |
| **Charts** | Chart.js CDN | Used exclusively in `templates/stats.html` for 30-day growth and rank distribution charts. |

---

## 3. Complete Route & Template Inventory (31 Templates Across 8 Routers)

### 3.1 Public & Compliance Module ([`routers/public.py`](file:///c:/Users/emend/OneDrive/Documentos/TF_System/Taskforce_System/routers/public.py))
| Route | Endpoint Name | Template | Auth / Clearance | Current Condition & Debt |
|---|---|---|---|---|
| `GET /` | `landing_page` | `landing.html` | Public | Heavy radial purple blurs (`filter: blur(60px)`), inline gradient text, oversized pills. |
| `GET /roster` | `public_roster` | `public_roster.html` | Authenticated Sector Member | Uses `.tf-card` and `.tf-table`; inline purple badge styles; lacks rank filter pills. |
| `GET /public/member/{member_id}` | `public_member` | `public_member.html` | Authenticated Sector Member | Uses default Bootstrap `.card` and `.list-group-item` without tactical styling; minimal layout hierarchy. |
| `GET /ac_progress` | `public_ac_progress` | `public_ac_progress.html` | Authenticated Sector Member | Displays member quota progress bars; heavy inline badge styles; lacks status filtering or search. |
| `GET /privacy` | `privacy_policy` | `privacy.html` | Public | Compliance text page; inherits top navbar. |
| `GET /terms` | `terms_of_service` | `terms.html` | Public | Compliance text page; inherits top navbar. |

### 3.2 Authentication & Multi-Tenant Portal ([`routers/roblox_auth.py`](file:///c:/Users/emend/OneDrive/Documentos/TF_System/Taskforce_System/routers/roblox_auth.py), [`routers/auth.py`](file:///c:/Users/emend/OneDrive/Documentos/TF_System/Taskforce_System/routers/auth.py))
| Route | Endpoint Name | Template | Auth / Clearance | Current Condition & Debt |
|---|---|---|---|---|
| `GET /auth/roblox/login` | `roblox_login` | *(Redirect)* | Public | Initiates Roblox OAuth2 flow or redirects to `/auth/dev/login` when OAuth credentials are unset. |
| `GET /auth/roblox/callback` | `roblox_callback` | *(Redirect)* | Public | Syncs Roblox user & group memberships, sets `tf_user_token` cookie, redirects to `/portal/select-group`. |
| `GET\|POST /auth/dev/login` | `dev_login` | `portal/dev_login.html` | Public (Dev Mode) | Developer simulation portal for testing multi-tenant roles. |
| `GET /portal/select-group` | `select_group_portal` | `portal/select_group.html` | Level 1 JWT (`tf_user_token`) | Renders registered sector cards and `#registerGroupModal`; uses inline purple accents. |
| `GET\|POST /portal/select-group/{group_id}` | `enter_group` | *(Redirect)* | Level 1 JWT (`tf_user_token`) | Evaluates sector permissions, issues Level 2 JWT (`tf_tenant_token`), redirects to `/dashboard`. |
| `POST /portal/register-group` | `register_new_group` | *(Redirect)* | Level 1 JWT (`tf_user_token`) | Provisions a new tenant group and imports Roblox ranks. |
| *(Deprecated)* | `staff_login`, `hct_login`, `update_cookie` | `login.html`, `staff_login.html`, `hct_login.html`, `update_cookie.html` | Retired | Routes in `routers/auth.py` now redirect to `/auth/roblox/login` or `/group/settings`; templates are dead legacy artifacts. |

### 3.3 Overview, Members & Staff Analytics ([`routers/members.py`](file:///c:/Users/emend/OneDrive/Documentos/TF_System/Taskforce_System/routers/members.py))
| Route | Endpoint Name | Template | Auth / Clearance | Current Condition & Debt |
|---|---|---|---|---|
| `GET /dashboard` | `dashboard` | `dashboard.html` | `@staff_required` | **Debt:** Oversized KPI cards; `recent_activities` is passed from backend but only `{{ recent_activities\|length }}` is rendered—the actual activity feed is never shown. |
| `GET /members` | `members` | `members.html` | `@staff_required` | Personnel table with search bar and View/Edit/Remove actions; inline purple badge styles. |
| `GET /member/{member_id}` | `member_detail` | `member_detail.html` | `@staff_required` | **Critical Debt:** 28 lines of raw unstyled HTML (`<h2 style="color: white;">`, plain `<ul><li>` lists) with no cards, tables, or actions for edit/promote. |
| `GET\|POST /add_member` | `add_member` | `add_member.html` | `@staff_required` | **Critical Debt:** 15 lines of raw unstyled HTML form inputs with no container card or validation layout. |
| `GET\|POST /member/{member_id}/edit` | `edit_member` | `edit_member.html` | `@staff_required` | **Critical Debt:** 23 lines of raw unstyled HTML form inputs. |
| `GET\|POST /member/{member_id}/delete` | `delete_member` | `confirm_delete.html` | `@staff_required` | Uses default Bootstrap `.card-header.bg-danger` without tactical styling. |
| `GET\|POST /promote` | `promote` | `promote_member.html` | `@staff_required` | **Critical Debt:** 24 lines of raw unstyled HTML form inputs (`<h3 style="color: white;">`). |
| `GET /stats` | `stats` | `stats.html` | `@staff_required` | **Critical Debt:** Uses `card bg-primary`, `card-header bg-white`, and `Math.random()` colors in Chart.js doughnut chart. |

### 3.4 Activities, AC & Quotas, and Rank Requirements ([`routers/ac.py`](file:///c:/Users/emend/OneDrive/Documentos/TF_System/Taskforce_System/routers/ac.py))
| Route | Endpoint Name | Template | Auth / Clearance | Current Condition & Debt |
|---|---|---|---|---|
| `GET /ac/` | `ac_dashboard` | `ac/ac_dashboard.html` (or `ac/ac_setup.html`) | `@hct_required` | When no active cycle exists, renders `ac/ac_setup.html` (12 lines of raw unstyled HTML). Active dashboard has 6+ small action buttons crowded in header and inline purple styling. |
| `GET\|POST /ac/create_period` | `create_ac_period` | `ac/create_period.html` | `@hct_required` | **Critical Debt:** 13 lines of raw unstyled HTML form inputs. |
| `GET\|POST /ac/edit_period` | `edit_ac_period` | `ac/edit_period.html` | `@hct_required` | **Critical Debt:** 15 lines of raw unstyled HTML form inputs. |
| `GET\|POST /ac/log_activity` | `log_ac_activity` | `ac/log_activity.html` | `@hct_required` | **Critical Debt:** 55 lines of raw unstyled HTML form inputs. |
| `GET /ac/quick_log` | `quick_log` | `ac/ac_quick_log.html` | `@hct_required` | **Critical Debt:** Unstyled raw `<table class="table">`, no search/filter bar, uses blocking browser `alert()` dialogs and full `window.location.reload()` on every click. |
| `GET /ac/member/{member_id}` | `ac_member_detail` | `ac/member_detail.html` | `@hct_required` | **Functional Bug & Debt:** Raw HTML list; renders `<button id="ia-toggle">` and `<button id="exempt-toggle">` with **no JavaScript event listeners attached**! |
| `GET /ac/title_rewards` | `title_rewards` | `ac/title_rewards.html` | `@hct_required` | Heavy inline purple gradients and glassmorphism. |
| `GET /ac/config` | `ac_config` | `ac/ac_config.html` | `@hct_required` | 41KB monolithic template with hundreds of inline purple/glass styles for Activity Types, Rank Quotas, and Titles. |

### 3.5 Group Configuration & Roblox Sync ([`routers/group_settings.py`](file:///c:/Users/emend/OneDrive/Documentos/TF_System/Taskforce_System/routers/group_settings.py), [`routers/sync.py`](file:///c:/Users/emend/OneDrive/Documentos/TF_System/Taskforce_System/routers/sync.py))
| Route | Endpoint Name | Template | Auth / Clearance | Current Condition & Debt |
|---|---|---|---|---|
| `GET /group/settings` | `group_settings` | `group/group_settings.html` | `@hct_required` | 30KB template with extensive inline `rgba(15, 23, 42, 0.75) !important` cards, 8-theme visual picker (to be retired in favor of unified Nexus theme), Discord channel IDs, bot cookie form, and rank permissions matrix. |
| `GET /roblox/rank_mappings` | `manage_rank_mappings` | `roblox/rank_mappings.html` | `@staff_required` | `GET` redirects to `/group/settings`; `POST` actions handle legacy rank mapping updates. |

### 3.6 Documentation Hub ([`routers/docs.py`](file:///c:/Users/emend/OneDrive/Documentos/TF_System/Taskforce_System/routers/docs.py))
| Route | Endpoint Name | Template | Auth / Clearance | Current Condition & Debt |
|---|---|---|---|---|
| `GET /docs` | `docs_hub` | `docs/index.html` | Public (Sec 0) + 3-Tier Rank Gated | Comprehensive content and 7 verified screenshots; uses inline dark-purple card styles that need alignment with Nexus semantic tokens. |

---

## 4. Backend API & AJAX Contracts (Must Be Preserved)

All existing form submission routes and JSON endpoints remain authoritative and must not be broken:

1. **Quick Log Activity**: `POST /ac/quick_log_activity`
   - Request JSON: `{ "member_id": int, "activity_type": str, "activity_date": "YYYY-MM-DD", "logged_by": str, "quantity": int }`
   - Response JSON: `{ "success": bool, "points": float, "count": int, "activity_ids": list[int] }`
2. **Toggle Inactivity Notice (IA)**: `POST /ac/quick_log_ia`
   - Request JSON: `{ "member_id": int, "reason": str, "approved_by": str }`
   - Response JSON: `{ "success": bool, "is_ia": bool, "message": str }`
3. **Toggle AC Exemption**: `POST /ac/quick_log_exempt`
   - Request JSON: `{ "member_id": int, "reason": str, "approved_by": str }`
   - Response JSON: `{ "success": bool, "is_exempt": bool, "message": str }`
4. **Delete Logged Activity**: `POST /ac/activity/{activity_id}/delete`
   - Headers: `X-Requested-With: XMLHttpRequest`, `Accept: application/json`
   - Response JSON: `{ "success": true, "message": "Activity deleted" }`
5. **Excel Export & Workbook Merge**: `GET|POST /ac/export_excel`
   - `GET`: Streams `.xlsx` report for `period_id`.
   - `POST`: Multipart file upload (`workbook`) merged and streamed back.

---

## 5. CSS & Visual System Technical Debt Register

| ID | Location | Issue Description | Remediation in Phase 1 & 2 |
|---|---|---|---|
| **CSS-01** | `style.css:495-507` | `.text-muted, .text-white-50, .text-secondary` forced to `color: #ffffff !important; text-shadow: 0 1px 4px rgba(0,0,0,0.7); opacity: 0.9;`. Completely flattens typographic hierarchy. | Map secondary text strictly to `--nx-text-secondary` (`#98A8B6`) and muted text to `--nx-text-muted` (`#6E7F8D`) with zero text-shadow. |
| **CSS-02** | `style.css:5-355` | 8 divergent theme blocks (`neon_purple`, `clean_light`, etc.) using `--tf-purple-*` naming and radial glow patterns. | Consolidate to the authoritative Nexus Tactical Operations token system (`#11151B`, `#1B222B`, `#232D38`, `#303B47`, `#32C5E8`) and alias `--tf-*` variables for backwards compatibility. |
| **CSS-03** | `style.css:514-537` | Universal `.card, .tf-card` forces `backdrop-filter: blur(20px)`, `border-radius: 16px !important`, and heavy glow shadows. | Replace with crisp `8px` radius (`--nx-radius-md`), solid `#1B222B` surface, `1px solid #303B47` border, and restrained elevation shadow. |
| **CSS-04** | `style.css:1196-1201` | `@media (max-width: 768px) { [class*="col-"] { flex-basis: 100%; max-width: 100%; } }` breaks Bootstrap responsive grid columns (`col-6`, `col-sm-6`). | Remove destructive wildcard column override and use standard responsive grid breakpoints. |
| **NAV-01** | `base.html:20-107` | Single horizontal top navbar with up to 10 links, no active route indicator, no role grouping, and no command palette. | Replace with the Phase 2 Application Shell: Left Sidebar (`240px`) + Context-Aware Topbar (`56px`) + `Ctrl+K` Command Palette. |
| **BUG-01** | `dashboard.html:78` | Dashboard receives `recent_activities` list from `member_service.get_dashboard_data()` but only displays `{{ recent_activities\|length }}` (always `0` to `5`) instead of rendering the recent operational activity feed. | Render the actual recent activity log table in the Overview module alongside operational metrics. |
| **BUG-02** | `ac/member_detail.html:8-9` | `#ia-toggle` and `#exempt-toggle` buttons exist in DOM with no JavaScript handlers attached. | Wire buttons to `POST /ac/quick_log_ia` and `POST /ac/quick_log_exempt` with instant status badge updates. |

