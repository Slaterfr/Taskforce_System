# Environment Variables Setup

## Quick Start

1. **Copy the example file:**
   ```bash
   cp env.example .env
   ```
   Or manually create a `.env` file in the `Taskforce_System` folder.

2. **Fill in your values** (see below)

3. **Never commit `.env` to git!** It contains sensitive information.

## Required Values

### 1. Get Your Roblox Group ID
- Go to your Roblox group page
- Look at the URL: `https://www.roblox.com/groups/{GROUP_ID}/...`
- Copy the number from the URL

### 2. Get Your Bot Account Cookie
Since you've already created the bot account and set it to Marshal:

1. **Log into your bot account** in a browser
2. **Open Developer Tools** (F12)
3. Go to **Application** tab → **Cookies** → `https://www.roblox.com`
4. Find the **`.ROBLOSECURITY`** cookie
5. **Copy its value** (it's a long string)

### 3. Fill in `.env` file:

```env
# Flask Configuration
SECRET_KEY=Cev_Is_Swifts_Fav_Aparently
STAFF_PASSWORD=task2025

# Roblox API Configuration
ROBLOX_GROUP_ID=your_group_id_here
ROBLOX_COOKIE=your_cookie_value_here

# Enable sync
ROBLOX_SYNC_ENABLED=true

# Sync every 10 minutes
ROBLOX_SYNC_INTERVAL=600
```

## Next Steps After Setting Up .env

1. **Start your Flask app** - it will automatically load the `.env` file
2. **Go to `/roblox/rank_mappings`** in your browser
3. **Set up rank mappings** - map each system rank to its Roblox role ID
4. **Test it!** - Try changing a member's rank in the system

## Security Reminder

- ✅ `.env` is already in `.gitignore` (if you have one)
- ❌ Never commit `.env` to git
- 🔒 Keep your cookie secure
- 🔄 Rotate cookie if it's ever exposed

