# Quick Start Guide - Roblox Sync Setup

## ✅ You've Done:
- Created bot account
- Set bot account to Marshal rank

## 📋 Next Steps:

### Step 1: Create `.env` File

1. **Copy the example file:**
   - Copy `env.example` to `.env` in the `Taskforce_System` folder
   - Or create a new file called `.env` in `Taskforce_System` folder

2. **Get Your Roblox Group ID:**
   - Go to your Roblox group page
   - Look at the URL: `https://www.roblox.com/groups/12345678/...`
   - The number (e.g., `12345678`) is your GROUP ID

3. **Get Your Bot Account Cookie:**
   - **Log into your bot account** in a browser (the one you set to Marshal)
   - Press **F12** to open Developer Tools
   - Go to **Application** tab (or **Storage** in Firefox)
   - Click **Cookies** → `https://www.roblox.com`
   - Find **`.ROBLOSECURITY`** cookie
   - **Copy the entire value** (it's a long string like `_|WARNING:-DO-NOT-SHARE-THIS...`)

4. **Fill in your `.env` file:**

```env
# Flask Configuration (already set, but you can change these)
SECRET_KEY=Cev_Is_Swifts_Fav_Aparently
STAFF_PASSWORD=task2025

# Roblox API Configuration
ROBLOX_GROUP_ID=12345678
ROBLOX_COOKIE=_|WARNING:-DO-NOT-SHARE-THIS...paste-your-cookie-here

# Enable sync
ROBLOX_SYNC_ENABLED=true

# Sync every 10 minutes (600 seconds)
ROBLOX_SYNC_INTERVAL=600
```

**Replace:**
- `12345678` with your actual group ID
- `_|WARNING:-DO-NOT-SHARE-THIS...` with your actual cookie value

### Step 2: Install APScheduler (if not already installed)

```bash
pip install apscheduler
```

### Step 3: Start Your Flask App

```bash
python app.py
```

You should see a message like:
```
Roblox sync scheduler started (interval: 600s)
```

### Step 4: Set Up Rank Mappings

1. **Open your browser** and go to: `http://localhost:5000/roblox/rank_mappings`
   - Or add a link in your dashboard to this page

2. **For each rank in your system**, add a mapping:
   - **System Rank**: The rank name (e.g., "Aspirant", "Novice", "Marshal", etc.)
   - **Roblox Role ID**: The numeric ID from your Roblox group
   - **Roblox Role Name**: The role name in Roblox (optional)

**How to find Roblox Role IDs:**
- The rank mappings page should show available roles if your group ID is configured
- Or check your Roblox group settings → Roles
- Or use: `https://groups.roblox.com/v1/groups/{YOUR_GROUP_ID}/roles`

**Example mappings:**
```
System Rank: Aspirant → Roblox Role ID: 123 → Role Name: Aspirant
System Rank: Novice → Roblox Role ID: 124 → Role Name: Novice
System Rank: Marshal → Roblox Role ID: 130 → Role Name: Marshal
... (continue for all ranks)
```

### Step 5: Test It!

1. **Test System → Roblox:**
   - Go to a member's page
   - Change their rank in the system
   - Check your Roblox group - their role should update automatically!

2. **Test Roblox → System:**
   - Manually change someone's rank in Roblox
   - Click "Sync Now from Roblox" on the rank mappings page
   - Check the member's rank in your system - it should update!

## 🔍 Troubleshooting

### "No authentication cookie provided"
- Your `ROBLOX_COOKIE` is empty or missing
- Make sure you copied the ENTIRE cookie value (it's very long)

### "No role mapping found for rank"
- You need to add a rank mapping in `/roblox/rank_mappings`
- Make sure the system rank name matches exactly (case-sensitive)

### "Permission denied"
- Your bot account needs permissions to manage the group
- Make sure the bot account is an Admin/Officer with "Change member rank" permission
- Marshal rank might not have these permissions - you may need to promote the bot account

### Sync not working?
- Check Flask logs for error messages
- Verify `ROBLOX_SYNC_ENABLED=true` in your `.env`
- Make sure your cookie hasn't expired (get a fresh one if needed)

## ⚠️ Important Notes

- **Never commit `.env` to git!** It contains your cookie
- Cookies expire - if sync stops working, get a fresh cookie
- The bot account needs **group management permissions** (not just Marshal rank)
- If Marshal doesn't have permission, promote the bot to a rank that does (or make it an Admin/Officer)

## 🎉 You're Done!

Once rank mappings are set up, the sync will work automatically:
- Changes in system → Update Roblox immediately
- Changes in Roblox → Sync to system every 10 minutes

Good luck! 🚀

