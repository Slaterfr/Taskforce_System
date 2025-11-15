# Roblox Two-Way Sync Setup Guide

## Overview
This system now supports two-way synchronization between your management system and Roblox group:
- **System → Roblox**: When you change ranks/add/remove members in the system, it automatically updates Roblox
- **Roblox → System**: Background polling syncs changes from Roblox to your system every 10 minutes (configurable)

## What You Need to Do

### 1. Install Dependencies
You need to install `APScheduler` for background polling:
```bash
pip install apscheduler
```

### 2. Set Up Roblox Account & Get Cookie

**You need a Roblox account that has permission to manage your group** (change roles, add/remove members). This can be:
- Your personal account (if you're the group owner/admin)
- **Recommended**: A dedicated bot account (better for security)

**Steps:**
1. Log into the Roblox account that has group management permissions
2. Open Developer Tools (F12)
3. Go to Application/Storage → Cookies → `https://www.roblox.com`
4. Find the `.ROBLOSECURITY` cookie
5. Copy its value

**⚠️ SECURITY WARNING**: 
- This cookie gives full access to that Roblox account
- If using your personal account, be extra careful
- **Recommended**: Create a dedicated bot account with only the necessary group permissions
- Keep the cookie secure and never commit it to git!

### 3. Configure Environment Variables
Add these to your `.env` file or set them as environment variables:

```env
# Required for sync to work
ROBLOX_GROUP_ID=your_group_id_here
ROBLOX_COOKIE=your_roblox_cookie_here

# Enable sync (set to 'true' to enable)
ROBLOX_SYNC_ENABLED=true

# Sync interval in seconds (default: 600 = 10 minutes)
ROBLOX_SYNC_INTERVAL=600
```

### 4. Set Up Rank Mappings
1. Start your Flask app
2. Log in as staff
3. Navigate to `/roblox/rank_mappings` (or add a link in your dashboard)
4. For each rank in your system, add a mapping:
   - **System Rank**: The rank name in your system (e.g., "Aspirant")
   - **Roblox Role ID**: The numeric role ID from your Roblox group
   - **Roblox Role Name**: The role name in Roblox (optional, but helpful)

**How to find Roblox Role IDs:**
- The rank mappings page will show available roles if your group ID is configured
- Or use the Roblox API: `https://groups.roblox.com/v1/groups/{GROUP_ID}/roles`
- Or check in your Roblox group settings

### 5. Run Database Migration
The new `RankMapping` table needs to be created. If you're using SQLite, it should auto-create. Otherwise, run:
```python
from app import create_app
from database.models import db

app = create_app()
with app.app_context():
    db.create_all()
```

## How It Works

### System → Roblox Sync (Immediate)
When you:
- **Promote a member** (`/promote_member`)
- **Edit a member's rank** (`/member/<id>/edit`)
- **Add a new member** (`/add_member`)
- **Delete a member** (`/member/<id>/delete`)

The system will automatically:
1. Check if sync is enabled
2. Look up the Roblox role ID for the member's rank
3. Update/add/remove the member in Roblox group
4. Show a warning if sync fails (but the system change still saves)

### Roblox → System Sync (Background Polling)
Every 10 minutes (or your configured interval), the system:
1. Fetches all members from your Roblox group
2. Compares with your database
3. Updates ranks if they changed in Roblox
4. Adds new members (Aspirant+ only)
5. Marks members as inactive if they left the Roblox group

### Preventing Sync Loops
The system uses a flag to prevent infinite loops:
- When syncing FROM Roblox, it sets a flag
- System → Roblox sync checks this flag and skips if syncing from Roblox
- This prevents changes made by Roblox sync from triggering another sync

## Testing

### Test System → Roblox Sync
1. Make sure sync is enabled and rank mappings are set up
2. Edit a member's rank in the system
3. Check your Roblox group - the member's role should update

### Test Roblox → System Sync
1. Manually change someone's rank in Roblox
2. Wait for the next sync cycle (or click "Sync Now" on the rank mappings page)
3. Check the member's rank in your system - it should update

### Manual Sync
You can manually trigger a sync from Roblox by:
- Going to `/roblox/rank_mappings`
- Clicking "Sync Now from Roblox"

## Troubleshooting

### Sync not working?
1. Check that `ROBLOX_SYNC_ENABLED=true` is set
2. Verify your `ROBLOX_COOKIE` is valid (cookies expire!)
3. Check that rank mappings are configured
4. Look at Flask logs for error messages

### "No authentication cookie provided"
- Your `ROBLOX_COOKIE` is missing or empty
- Get a fresh cookie from your browser

### "No role mapping found for rank"
- You need to add a rank mapping in `/roblox/rank_mappings`
- Make sure the system rank name matches exactly

### "Permission denied" errors
- Your Roblox account needs permissions to manage the group
- Make sure you're a group owner/admin with role management permissions

### Background sync not running
- Check that APScheduler is installed: `pip install apscheduler`
- Check Flask logs for scheduler startup messages
- Verify `ROBLOX_SYNC_ENABLED=true`

## Security Notes

1. **Never commit your `.ROBLOSECURITY` cookie to git**
2. **Use environment variables** for sensitive data
3. **Rotate your cookie** if it's ever exposed
4. **Use a dedicated bot account** - Recommended approach:
   - Create a separate Roblox account specifically for the bot
   - Give it only the minimum permissions needed (group management)
   - Don't use it for anything else
   - This way, if the cookie is compromised, your personal account is safe
5. **Monitor logs** for unauthorized access attempts

## Account Setup (Recommended)

**Best Practice: Create a Dedicated Bot Account**

1. Create a new Roblox account (e.g., "YourGroupName-Bot")
2. Add it to your group with appropriate permissions:
   - Group Owner can add it as an Admin/Officer
   - Give it permissions to: "Change member rank" and "Remove members"
3. Log into this bot account and get its `.ROBLOSECURITY` cookie
4. Use this cookie in your environment variables

**Why?**
- If the cookie leaks, your personal account stays safe
- Clear separation between bot actions and personal actions
- Easier to audit what the bot did vs. what you did manually

## API Rate Limits

Roblox has rate limits. The system includes:
- 100ms delay between requests
- Automatic retry on rate limit (429) errors
- Background sync runs every 10 minutes (configurable)

If you hit rate limits frequently, increase `ROBLOX_SYNC_INTERVAL`.

## Files Added/Modified

- `api/roblox_api.py` - Extended with write operations
- `utils/roblox_sync.py` - New sync module
- `database/models.py` - Added `RankMapping` model
- `app.py` - Added sync hooks and background scheduler
- `config.py` - Added sync configuration
- `templates/roblox/rank_mappings.html` - New management page

## Next Steps

1. Install APScheduler: `pip install apscheduler`
2. Set up environment variables
3. Configure rank mappings
4. Test with a single member first
5. Monitor logs for any issues
6. Enable full sync once confident

Good luck! 🚀

