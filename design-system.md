# NEXUS — Tactical Operations Design System

**Version:** 1.0  
**Design Direction:** Tactical Operations  
**Visual Density:** Balanced  
**Primary Accent:** Electric Cyan (`#32C5E8`)

---

## 1. Visual Philosophy

Nexus is an enterprise multi-group operational management platform. Every surface, control, and data table is engineered to prioritize:

- **Operational Intelligence & Precision:** High signal-to-noise ratio, crisp 1px borders (`#303B47`), and structured data alignment.
- **Restrained Elevation:** Solid architectural surfaces (`#11151B` → `#1B222B` → `#232D38`) instead of heavy radial blurs or neon glassmorphism.
- **Strict Semantic Hierarchy:** Primary text (`#EDF3F7`) vs. secondary metadata (`#98A8B6`), with Electric Cyan (`#32C5E8`) reserved strictly for active states, primary actions, and focal highlights.
- **Technical Monospace Discipline:** All IDs, Roblox/Discord identifiers, rank numbers, point values, percentages, and timestamps use `Geist Mono` with `font-variant-numeric: tabular-nums`.

---

## 2. Semantic Color Tokens

All components reference semantic `--nx-*` CSS custom properties rather than hardcoded hex values:

| Category | CSS Token | Hex / Value | Usage |
|---|---|---|---|
| **Background** | `--nx-bg` | `#11151B` | Root viewport & workspace canvas background |
| **Surface** | `--nx-surface` | `#1B222B` | Primary cards, data tables, sidebar, and form containers |
| **Elevated Surface** | `--nx-surface-elevated` | `#232D38` | Modals, dropdowns, table headers, hover rows, command palette |
| **Interactive Hover** | `--nx-surface-hover` | `#283340` | Row hover states and interactive list items |
| **Border** | `--nx-border` | `#303B47` | Standard 1px structural dividers and card borders |
| **Subtle Border** | `--nx-border-subtle` | `rgba(48, 59, 71, 0.6)` | Internal table row dividers |
| **Primary Text** | `--nx-text-primary` | `#EDF3F7` | Headings, primary data cells, active labels |
| **Secondary Text** | `--nx-text-secondary` | `#98A8B6` | Subtitles, column headers, descriptions, form labels |
| **Muted Text** | `--nx-text-muted` | `#6E7F8D` | Placeholders, disabled controls, secondary captions |
| **Primary Accent** | `--nx-accent` | `#32C5E8` | Primary buttons, active nav indicators, focus rings, key links |
| **Accent Subtle** | `--nx-accent-subtle` | `rgba(50, 197, 232, 0.12)` | Active nav background, cyan badge fill, focus ring halo |
| **Success** | `--nx-success` | `#38C98A` | Passed quota, connected bot status, verified state |
| **Warning** | `--nx-warning` | `#EAB45B` | At-risk quota (`<50%`), unconfigured cookie, IA / Exempt notice |
| **Danger** | `--nx-danger` | `#ED6672` | Failed quota, destructive actions, error alerts, HCT lock |

---

## 3. Typography System

### Font Families
- **Primary UI (`--nx-font-sans`):** `'Geist', -apple-system, BlinkMacSystemFont, 'Inter', 'Segoe UI', sans-serif`
- **Technical Monospace (`--nx-font-mono`):** `'Geist Mono', 'JetBrains Mono', monospace`

### Type Scale & Hierarchy

| Element / Class | Size | Weight | Line Height | Tracking | Font Family |
|---|---|---|---|---|---|
| **Page Title (`.nx-title`)** | `1.375rem` (22px) | `600` | `1.25` | `-0.02em` | `--nx-font-sans` |
| **Section Heading (`.nx-h2`)** | `1.0625rem` (17px) | `600` | `1.35` | `-0.01em` | `--nx-font-sans` |
| **Card Title (`.nx-card-title`)** | `0.9375rem` (15px) | `600` | `1.4` | `-0.01em` | `--nx-font-sans` |
| **Body Default** | `0.875rem` (14px) | `400` | `1.5` | `0` | `--nx-font-sans` |
| **Table Header (`th`)** | `0.75rem` (12px) | `600` | `1.2` | `0.06em` (Uppercase) | `--nx-font-sans` |
| **Eyebrow / Overline (`.nx-eyebrow`)** | `0.6875rem` (11px) | `600` | `1.2` | `0.08em` (Uppercase) | `--nx-font-mono` |
| **Technical Data (`.nx-mono`)** | `0.8125rem` (13px) | `500` | `1.4` | `0` (`tabular-nums`) | `--nx-font-mono` |

---

## 4. Geometry, Spacing & Motion

- **Border Radius:**
  - `--nx-radius-sm`: `6px` (Badges, buttons, form inputs, code chips)
  - `--nx-radius-md`: `8px` (Cards, tables, panels, alerts)
  - `--nx-radius-lg`: `10px` (Modals, command palette, large containers)
- **Shadows:**
  - `--nx-shadow-sm`: `0 1px 2px rgba(0, 0, 0, 0.35)`
  - `--nx-shadow-md`: `0 4px 12px rgba(0, 0, 0, 0.4)`
  - `--nx-shadow-lg`: `0 12px 32px rgba(0, 0, 0, 0.55)`
- **Transitions:**
  - `--nx-transition`: `150ms cubic-bezier(0.16, 1, 0.3, 1)` (All hover, focus, and active state changes execute within the `120–180ms` tactical window; no bouncy vertical transforms).

---

## 5. Core UI Primitives (`templates/components/_macros.html`)

Import the shared macro library in any Jinja2 template:
```jinja2
{% from "components/_macros.html" import nx_page_header, nx_stat_card, nx_badge, nx_empty_state, nx_progress_bar %}
```

### 5.1 Page Header (`nx_page_header`)
Renders a consistent module header with an optional monospace eyebrow, title, subtitle, and right-aligned action slot (`caller()`).
```jinja2
{% call nx_page_header(title="Personnel Directory", subtitle="Active sector roster and rank assignments.", eyebrow="OPERATIONS // ROSTER", icon="users") %}
  <a href="{{ url_for('add_member') }}" class="nx-btn nx-btn-primary">
    <i data-lucide="user-plus"></i> Add Operative
  </a>
{% endcall %}
```

### 5.2 Tactical Telemetry Card (`nx_stat_card`)
Balanced-density KPI card (`padding: 1rem 1.25rem`, `8px` radius, `1px solid #303B47`) with status indicator, monospace metric value, and contextual subtext.
```jinja2
{{ nx_stat_card(label="Total Personnel", value=member_count, meta="Active registry", icon="users", accent="cyan") }}
```

### 5.3 Semantic Status Badge (`nx_badge`)
Compact badge (`6px` radius) supporting `cyan`, `success`, `warning`, `danger`, and `neutral` variants, with optional monospace typography.
```jinja2
{{ nx_badge(member.current_rank, variant="cyan", mono=True) }}
```

### 5.4 Precision Progress Bar (`nx_progress_bar`)
Tabular numeric quota progress bar with automatic semantic color mapping (`success` ≥ 100%, `cyan` ≥ 50%, `warning` / `danger` < 50%, `info` for Protected IA / Exempt).
```jinja2
{{ nx_progress_bar(percentage=progress.percentage, is_exempt=progress.is_exempt, is_protected=progress.is_protected) }}
```

### 5.5 Structured Empty State (`nx_empty_state`)
Replaces bare text messages with a bordered tactical empty state panel, Lucide icon, explanation, and optional primary CTA.
```jinja2
{{ nx_empty_state(icon="search-x", title="No Matching Personnel", description="No operatives matched your current filter criteria.", action_url=url_for('members'), action_label="Reset Filters") }}
```

