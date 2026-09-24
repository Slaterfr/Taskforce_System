# CORTEX // TACTICAL COMMAND NETWORK
## High Command Team (HCT) Briefing & Documentation Architecture Plan

---

### PART 1: HCT Executive Briefing (What Changed & How to Use It)

> **TO:** Taskforce High Command Team (HCT), Marshals & General Staff  
> **FROM:** Command & Engineering  
> **SUBJECT:** System 2.0 Upgrade: Multi-Tenancy, Dynamic Discord Clearances, and Sector Governance

Team,

The Taskforce System has undergone a major core overhaul to transition from a single-group tool into **CORTEX // Tactical Command Network**—a multi-tenant, modular operational platform. Below is a concise briefing on everything that has changed, how operations are affected, and what new capabilities you now control.

---

#### 1. Zero Discord ID Friction (Profile Roles Direct Clearance)
* **The Old Problem:** Previously, the bot required manual Discord ID linking or stored IDs in the database. If an operative’s Discord ID wasn't explicitly linked, the bot refused commands with *"Operative not found on this sector's roster"*.
* **The Upgrade:** **We have completely decoupled database records from Discord IDs.**
  * Operatives on the roster are synced directly from Roblox (`roblox_username` & `roblox_id`).
  * When someone uses `@Cortex` or slash commands in Discord, the bot reads their **server profile roles** directly (e.g., *General*, *Commander*, *Staff Team*, etc.).
  * Their rank and permissions are evaluated on the fly against your sector's active permission matrix.
  * **Result:** No operative ever has to register, link, or type their Discord ID into the system. As long as they have their appropriate role in the Discord server, the system recognizes them instantly.

---

#### 2. Granular Rank Permissions Matrix (`/group/settings`)
* **What It Does:** HCT no longer has to ask developers to change who can log missions or promote personnel.
* **How to Access:** In the web portal navigation, open **Sector Settings** (`/group/settings`).
* **Capabilities:** Every rank mapped to your sector has individual permission toggles:
  * **Can Promote:** Authority to promote/demote or update operative ranks.
  * **Can Log Activity:** Authority to log missions, training, and operational points for operatives.
  * **Can Delete Activity:** Authority to redact, modify, or remove logged entries.
  * **Can View Data:** Permission to view restricted sector rosters and analytics.
  * **Can Manage AC:** Authority to manage Activity Check cycles, quotas, and exemptions.
  * **HCT Clearance:** Master administrative and governance privileges.

---

#### 3. Sector Appearance & 8 Dynamic Visual Themes
* **What It Does:** You can customize the look and feel of the Taskforce portal to suit your team's visual preference.
* **Selectable Themes:**
  1. **Taskforce Classic (`neon_purple`):** The signature obsidian void with neon purple cyber grids and gradients.
  2. **Clean Light (`clean_light`):** Ultra-crisp high-contrast light mode with white frosted cards and royal blue accents.
  3. **Slate Charcoal (`neutral`):** Matte dark charcoal with muted steel accents and zero neon glare.
  4. **Deep Graphite (`dark_matte`):** Stealth matte obsidian with titanium borders.
  5. **Tactical Steel (`slate_gray`):** Cool industrial steel gray with steel-blue accents.
  6. **Cyberpunk Grid (`neon_cyan`):** Electric cyan cyberpunk grid with high-tech cyan borders.
  7. **Combat Ops Crimson (`crimson`):** Combat strike red with subtle crimson ambient glows.
  8. **SpecOps Emerald (`emerald`):** Tactical forest green with emerald night-ops glow.
* **How to Change:** Go to **Sector Settings -> Sector Visual Theme**, select your preferred style, and click **Apply Sector Theme**. All operatives accessing the sector portal will automatically experience the selected palette.

---

#### 4. True Multi-Tenancy & Multi-Guild Discord Bot
* **Sector Isolation:** Multiple allied units or sister sectors (e.g., *Delta Sector*, *Strike Groups*) can exist on the same platform with 100% data separation. Roster records, point logs, quotas, and cookies never overlap.
* **Smart Bot Routing:** The Discord bot automatically detects which Discord server a command came from and routes the action to that specific sector's database.

---

### PART 2: Full User & Staff Documentation Plan

To ensure operatives, staff, and leadership can use the system without needing direct assistance, we are structuring a self-contained **3-Tier Documentation Manual**.

```
┌─────────────────────────────────────────────────────────────┐
│                 CORTEX DOCUMENTATION SUITE                  │
├─────────────────┬───────────────────────────┬───────────────┤
│ Tier 1: Members │ Tier 2: Staff & Officers  │ Tier 3: HCT   │
│ (Operative)     │ (Commanders & Loggers)    │ (Leadership)  │
├─────────────────┼───────────────────────────┼───────────────┤
│ • Login/Access  │ • Natural Language Bot    │ • AC Cycles   │
│ • Quota Checks  │ • Single & Bulk Logging   │ • Rank Matrix │
│ • Mission Views │ • Promotions & Demotions  │ • Theme Setup │
│ • Titles/Badges │ • Activity Redactions     │ • Cookie/Sync │
└─────────────────┴───────────────────────────┴───────────────┘
```

#### Detailed Breakdown of the Documentation Modules

#### Module 1: Operative Quickstart Guide (Tier 1)
* **Target Audience:** All taskforce personnel (Aspirants through Adepts/Paladins).
* **Contents:**
  1. **How to Access the Portal:** Logging in via Roblox OAuth or viewing public sector rosters.
  2. **Checking Your Standing:** Understanding your points, active AC cycle status, and rank quota progress.
  3. **Bot Interactions:** How to ping `@Cortex` to check points (`@Cortex points for [username]`) or check rank status (`@Cortex info [username]`).
  4. **Title & Medal Qualifications:** How to qualify for specialty commendations and badges.

#### Module 2: Staff & Field Officer Operational Manual (Tier 2)
* **Target Audience:** NCOs, Staff Team, Prospect, Commanders, and Marshals.
* **Contents:**
  1. **Natural Language Logging with `@Cortex`:**
     * Single: `@Cortex log 1 patrol for [username]`
     * Multi-quantity: `@Cortex log 3 raids for [username]`
     * Contextual notes: `@Cortex log a scouting mission for [username] handled outpost defense`
  2. **Roster Promotions & Rank Updates:**
     * `@Cortex promote [username] to [RankName]`
     * Verifying Roblox group synchronization.
  3. **Activity Adjustments & Redactions:**
     * How to redact accidental entries: `@Cortex remove 1 raid from [username]`.
  4. **Managing Activity Check Submissions:**
     * How to review member logs and ensure accuracy before cycle closeouts.

#### Module 3: High Command Team (HCT) Administration & Governance Guide (Tier 3)
* **Target Audience:** Marshals, Generals, Sector Administrators.
* **Contents:**
  1. **Sector Visual Identity & Themes:** Setting sector name, call sign, crest image, and selecting from the 8 visual themes.
  2. **Configuring the Rank Permission Matrix:** Controlling which server roles can promote, log, delete, view, or manage AC.
  3. **Roblox Automation & Cookie Integration:** How to add, validate, test, or refresh the `.ROBLOSECURITY` automation cookie safely.
  4. **Managing Activity Cycles (AC):** Opening a new period, setting monthly point requirements per rank, configuring exemptions, and executing cycle closeouts.
  5. **Dynamic Activity Types & Quota Setup:** Adding new mission types, setting custom point values, and adjusting rank quotas.
