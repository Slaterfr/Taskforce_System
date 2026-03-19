# Supabase Database Migration Guide

## Overview
This guide will help you migrate the Taskforce System from SQLite to Supabase (PostgreSQL).

## Prerequisites
- ✅ Supabase account created
- ✅ Database project created in Supabase
- 📝 Have your Supabase connection string ready

## Step 1: Get Your Supabase Connection String

1. Go to your Supabase project dashboard
2. Click **Settings** → **Database**
3. Copy the **Connection String** (it looks like: `postgresql://[user]:[password]@[host]/[database]`)
4. Keep this safe - you'll need it for the `.env` file

## Step 2: Create Tables in Supabase

Go to your Supabase SQL Editor and run the following SQL scripts in order:

### Script 1: Create Members Table
```sql
CREATE TABLE members (
    id SERIAL PRIMARY KEY,
    discord_username VARCHAR(100) NOT NULL UNIQUE,
    discord_id VARCHAR(50) UNIQUE,
    roblox_username VARCHAR(100),
    roblox_id VARCHAR(50),
    current_rank VARCHAR(100) NOT NULL DEFAULT 'Aspirant',
    join_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_updated TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT true
);

CREATE INDEX idx_members_discord_username ON members(discord_username);
CREATE INDEX idx_members_discord_id ON members(discord_id);
```

### Script 2: Create Activity Logs Table
```sql
CREATE TABLE activity_logs (
    id SERIAL PRIMARY KEY,
    member_id INTEGER NOT NULL REFERENCES members(id) ON DELETE CASCADE,
    activity_type VARCHAR(100) NOT NULL,
    description TEXT,
    logged_by VARCHAR(100) NOT NULL,
    log_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_activity_logs_member_id ON activity_logs(member_id);
CREATE INDEX idx_activity_logs_log_date ON activity_logs(log_date);
```

### Script 3: Create Promotion Logs Table
```sql
CREATE TABLE promotion_logs (
    id SERIAL PRIMARY KEY,
    member_id INTEGER NOT NULL REFERENCES members(id) ON DELETE CASCADE,
    from_rank VARCHAR(100) NOT NULL,
    to_rank VARCHAR(100) NOT NULL,
    reason TEXT,
    promoted_by VARCHAR(100) NOT NULL,
    promotion_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_promotion_logs_member_id ON promotion_logs(member_id);
CREATE INDEX idx_promotion_logs_promotion_date ON promotion_logs(promotion_date);
```

### Script 4: Create Rank Mappings Table
```sql
CREATE TABLE rank_mappings (
    id SERIAL PRIMARY KEY,
    system_rank VARCHAR(100) NOT NULL UNIQUE,
    roblox_role_id INTEGER NOT NULL,
    roblox_role_name VARCHAR(100),
    is_active BOOLEAN DEFAULT true,
    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_rank_mappings_system_rank ON rank_mappings(system_rank);
```

### Script 5: Create Member Stats Table
```sql
CREATE TABLE member_stats (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    total_members INTEGER NOT NULL,
    rank_counts JSONB NOT NULL
);

CREATE INDEX idx_member_stats_timestamp ON member_stats(timestamp);
```

### Script 6: Create AC Periods Table
```sql
CREATE TABLE ac_periods (
    id SERIAL PRIMARY KEY,
    period_name VARCHAR(100) NOT NULL,
    start_date TIMESTAMP NOT NULL,
    end_date TIMESTAMP NOT NULL,
    is_active BOOLEAN DEFAULT true,
    is_finalized BOOLEAN DEFAULT false,
    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_ac_periods_is_active ON ac_periods(is_active);
CREATE INDEX idx_ac_periods_start_date ON ac_periods(start_date);
```

### Script 7: Create Activity Entries Table
```sql
CREATE TABLE activity_entries (
    id SERIAL PRIMARY KEY,
    member_id INTEGER NOT NULL REFERENCES members(id) ON DELETE CASCADE,
    ac_period_id INTEGER NOT NULL REFERENCES ac_periods(id) ON DELETE CASCADE,
    activity_type VARCHAR(50) NOT NULL,
    points FLOAT NOT NULL,
    description TEXT,
    activity_date TIMESTAMP NOT NULL,
    logged_by VARCHAR(100) NOT NULL,
    logged_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_limited_activity BOOLEAN DEFAULT false
);

CREATE INDEX idx_activity_entries_member_id ON activity_entries(member_id);
CREATE INDEX idx_activity_entries_ac_period_id ON activity_entries(ac_period_id);
CREATE INDEX idx_activity_entries_activity_type ON activity_entries(activity_type);
CREATE INDEX idx_activity_entries_activity_date ON activity_entries(activity_date);
```

### Script 8: Create Monthly Activity Entries Table
```sql
CREATE TABLE monthly_activity_entries (
    id SERIAL PRIMARY KEY,
    member_id INTEGER NOT NULL REFERENCES members(id) ON DELETE CASCADE,
    ac_period_id INTEGER NOT NULL REFERENCES ac_periods(id) ON DELETE CASCADE,
    activity_type VARCHAR(50) NOT NULL,
    points FLOAT NOT NULL,
    description TEXT,
    activity_date TIMESTAMP NOT NULL,
    logged_by VARCHAR(100) NOT NULL,
    logged_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_monthly_activity_entries_member_id ON monthly_activity_entries(member_id);
CREATE INDEX idx_monthly_activity_entries_ac_period_id ON monthly_activity_entries(ac_period_id);
CREATE INDEX idx_monthly_activity_entries_activity_type ON monthly_activity_entries(activity_type);
```

### Script 9: Create Inactivity Notices Table
```sql
CREATE TABLE inactivity_notices (
    id SERIAL PRIMARY KEY,
    member_id INTEGER NOT NULL REFERENCES members(id) ON DELETE CASCADE,
    ac_period_id INTEGER NOT NULL REFERENCES ac_periods(id) ON DELETE CASCADE,
    start_date TIMESTAMP NOT NULL,
    end_date TIMESTAMP NOT NULL,
    reason TEXT,
    approved_by VARCHAR(100) NOT NULL,
    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    protects_ac BOOLEAN DEFAULT false
);

CREATE INDEX idx_inactivity_notices_member_id ON inactivity_notices(member_id);
CREATE INDEX idx_inactivity_notices_ac_period_id ON inactivity_notices(ac_period_id);
CREATE INDEX idx_inactivity_notices_start_date ON inactivity_notices(start_date);
```

### Script 10: Create AC Exemptions Table
```sql
CREATE TABLE ac_exemptions (
    id SERIAL PRIMARY KEY,
    member_id INTEGER NOT NULL REFERENCES members(id) ON DELETE CASCADE,
    ac_period_id INTEGER NOT NULL REFERENCES ac_periods(id) ON DELETE CASCADE,
    reason TEXT,
    approved_by VARCHAR(100) NOT NULL,
    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_ac_exemptions_member_id ON ac_exemptions(member_id);
CREATE INDEX idx_ac_exemptions_ac_period_id ON ac_exemptions(ac_period_id);
```

### Script 11: Create Period Statistics Table
```sql
CREATE TABLE period_statistics (
    id SERIAL PRIMARY KEY,
    member_id INTEGER NOT NULL REFERENCES members(id) ON DELETE CASCADE,
    ac_period_id INTEGER NOT NULL REFERENCES ac_periods(id) ON DELETE CASCADE,
    raids_count INTEGER DEFAULT 0,
    patrols_count INTEGER DEFAULT 0,
    trainings_count INTEGER DEFAULT 0,
    missions_count INTEGER DEFAULT 0,
    tryouts_count INTEGER DEFAULT 0,
    evaluations_count INTEGER DEFAULT 0,
    supervision_count INTEGER DEFAULT 0,
    total_points FLOAT DEFAULT 0.0,
    captured_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_period_statistics_member_id ON period_statistics(member_id);
CREATE INDEX idx_period_statistics_ac_period_id ON period_statistics(ac_period_id);
```

## Step 3: Update Environment Variables

Update your `.env` file with your Supabase credentials:

```ini
# Database Configuration - Supabase PostgreSQL
DATABASE_URL=postgresql://[user]:[password]@[host]/[database]

# Other existing variables stay the same
SECRET_KEY=your_secret_key_here
STAFF_PASSWORD=your_staff_password_here
HCT_PASSWORD=your_hct_password_here
ROBLOX_GROUP_ID=your_group_id
ROBLOX_COOKIE=your_cookie
ROBLOX_SYNC_ENABLED=false
ROBLOX_SYNC_INTERVAL=3600
DISCORD_BOT_API_KEY=your-secure-api-key-here
API_RATE_LIMIT=100
API_ENABLE_LOGGING=true
DISCORD_NOTIFICATION_WEBHOOK_URL=your_webhook_url
```

**Example Supabase connection string:**
```
postgresql://postgres:[YOUR_PASSWORD]@db.supabase.co:5432/postgres
```

## Step 4: Update Flask Configuration (Optional - Already Supports This!)

Good news! Your `config.py` already supports dynamic database URLs:

```python
SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///database/taskforce.db'
```

No changes needed! Just set the `DATABASE_URL` environment variable.

## Step 5: Install PostgreSQL Driver

Run this command to install the PostgreSQL adapter for SQLAlchemy:

```bash
pip install psycopg2-binary
```

Or if using the venv:
```bash
.\venv\Scripts\pip install psycopg2-binary
```

## Step 6: Test the Connection

1. Update your `.env` file with the Supabase connection string
2. Start your app: `python app.py`
3. Check the console for any database connection errors
4. Test by logging in and checking that everything still works

## Step 7: Migrate Data (Optional)

If you have existing data in SQLite and want to migrate it:

### Option A: SQLite to Supabase Export
1. Export data from SQLite as SQL/CSV
2. Import into Supabase using SQL Editor or API

### Option B: Python Script (Recommended)
Create a migration script that reads from SQLite and writes to Supabase:

```python
from database.models import db, Member, ActivityLog, PromotionLog, RankMapping, MemberStats
from database.ac_models import (
    ACPeriod, ActivityEntry, MonthlyActivityEntry,
    InactivityNotice, ACExemption, PeriodStatistics
)
from app import create_app

app = create_app()

with app.app_context():
    # SQLite data will be automatically migrated
    # Flask-SQLAlchemy handles schema creation
    db.create_all()
```

## Troubleshooting

### Connection Refused
- Check your Supabase credentials
- Ensure IP whitelist allows your connection
- Verify DATABASE_URL format

### Foreign Key Errors
- Ensure all tables are created in the correct order
- Check that all NOT NULL constraints are satisfied

### Performance Issues
- Supabase provides automatic backups - no need for manual backups
- Monitor your database usage in the Supabase dashboard

## Next Steps

1. ✅ Create Supabase account & database
2. ✅ Run all SQL scripts in Supabase SQL Editor
3. ✅ Update `.env` with DATABASE_URL
4. ✅ Install `psycopg2-binary`
5. ✅ Test the app
6. ✅ Migrate data (if applicable)
7. ✅ Deploy to production

---

**Questions?** Check Supabase docs: https://supabase.com/docs
