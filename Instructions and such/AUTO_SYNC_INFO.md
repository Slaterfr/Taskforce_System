# Auto-Sync Information

## ✅ Auto-Sync is Now Built-In!

The Roblox sync system is **automatically integrated** into your Flask app. You don't need to run any separate scripts!

## How It Works

### Automatic Startup Sync
- When you start your Flask app, it automatically runs a sync **5 seconds after startup**
- This catches any new members or rank changes that happened while the app was down

### Hourly Automatic Sync
- The system automatically syncs from Roblox **every hour** (3600 seconds)
- You can change this interval in your `.env` file with `ROBLOX_SYNC_INTERVAL`

### What Gets Synced
- ✅ **New members** added to Roblox group (Aspirant+ only)
- ✅ **Rank changes** - if someone's rank changes in Roblox, it updates in your system
- ✅ **Member updates** - Roblox username changes, etc.
- ✅ **Inactive members** - members who left the Roblox group are marked inactive

## Configuration

### Enable Auto-Sync
In your `.env` file:
```env
ROBLOX_SYNC_ENABLED=true
ROBLOX_GROUP_ID=8482555
ROBLOX_COOKIE=your_cookie_here
ROBLOX_SYNC_INTERVAL=3600  # 1 hour (in seconds)
```

### Change Sync Interval
- **1 hour (default)**: `ROBLOX_SYNC_INTERVAL=3600`
- **30 minutes**: `ROBLOX_SYNC_INTERVAL=1800`
- **10 minutes**: `ROBLOX_SYNC_INTERVAL=600`
- **5 minutes**: `ROBLOX_SYNC_INTERVAL=300`

**Note:** Don't set it too low (under 5 minutes) or you might hit Roblox API rate limits!

## Monitoring

### Check Logs
When you start your Flask app, you'll see:
```
✅ Roblox sync scheduler started - will sync every 3600s (60 minutes)
🔄 Initial sync scheduled (will run in 5 seconds)
```

During sync, you'll see:
```
🔄 Starting automatic Roblox sync...
✅ Roblox sync completed: 2 added, 5 updated, 1 rank changes
```

### Manual Sync
You can also manually trigger a sync:
1. **Via Web Interface**: Go to `/roblox/rank_mappings` and click "Sync Now from Roblox"
2. **Via Script**: Run `python api/run_auto_sync.py` (optional, not needed if app is running)

## Troubleshooting

### Sync Not Running?
1. Check that `ROBLOX_SYNC_ENABLED=true` in your `.env`
2. Check Flask logs for error messages
3. Make sure `ROBLOX_GROUP_ID` and `ROBLOX_COOKIE` are set correctly

### Sync Errors?
- Check that your cookie hasn't expired
- Verify the bot account has group management permissions
- Check Flask logs for detailed error messages

### Want to Disable Auto-Sync?
Set in `.env`:
```env
ROBLOX_SYNC_ENABLED=false
```

Or remove the environment variable (defaults to false).

## Old Scripts (Deprecated)

The old `api/run_auto_sync.py` and `api/auto_sync.py` scripts are no longer needed. The sync is now built into the Flask app. However, `run_auto_sync.py` has been updated to work as a manual trigger if needed.

## Summary

✅ **Automatic on startup** - Runs 5 seconds after app starts  
✅ **Automatic every hour** - Configurable interval  
✅ **No manual scripts needed** - Everything is built-in  
✅ **Better logging** - See what's happening in Flask logs  
✅ **Error handling** - Continues running even if one sync fails  

Just start your Flask app and it works! 🚀

