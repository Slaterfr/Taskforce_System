# Discord Bot Integration - Setup Guide

## 📋 Overview

This guide will help you integrate your Discord bot (with Groq AI) with the TF_System using the REST API we just created.

**Your Configuration:**
- ✅ Project Structure: **Separate Repos** (Option B)
- ✅ Discord Library: **discord.py**
- ✅ AI: **Groq API**  
- ✅ Permissions: **Commander, Marshal, General** roles
- ✅ Notifications: Channel `cortex-notis` (ID: `1446175728025735393`)
- ✅ Deployment: **Both on Render** (separate services)

---

## 🚀 Part 1: Flask API Setup (TF_System)

### Step 1: Generate API Key

Run this command in your TF_System directory:

```bash
cd Taskforce_System
python generate_api_key.py
```

This will output something like:
```
DISCORD_BOT_API_KEY=IHfR9mXy3kL8nP2qT6vZ9wB4cF7jM0xN5sA1dG8eK4hU
```

**Copy this key** - you'll need it in both Flask app and Discord bot.

### Step 2: Create Discord Webhook

1. Go to your Discord server
2. Go to **Server Settings** → **Integrations** → **Webhooks**
3. Click **New Webhook**
4. Name it: `TF System Notifications`
5. Select channel: **#cortex-notis**
6. **Copy Webhook URL** (it looks like: `https://discord.com/api/webhooks/123456789/ABC...`)

### Step 3: Update Flask App `.env`

Add these lines to your `TF_System/Taskforce_System/.env` file:

```bash
# Discord Bot API Configuration
DISCORD_BOT_API_KEY=IHfR9mXy3kL8nP2qT6vZ9wB4cF7jM0xN5sA1dG8eK4hU
API_RATE_LIMIT=100
API_ENABLE_LOGGING=true

# Discord Notifications
DISCORD_NOTIFICATION_WEBHOOK_URL=https://discord.com/api/webhooks/YOUR_WEBHOOK_URL_HERE
```

### Step 4: Deploy Flask App to Render

1. Commit and push changes to GitHub:
```bash
git add .
git commit -m "Add Discord bot API integration"
git push
```

2. Render will auto-deploy (or manually trigger deploy)

3. **Important:** Add environment variables in Render dashboard:
   - Go to your Render service → Environment
   - Add all variables from your `.env` file
   - Especially: `DISCORD_BOT_API_KEY` and `DISCORD_NOTIFICATION_WEBHOOK_URL`

4. After deployment, note your Flask app URL:
   ```
   https://your-tf-system.onrender.com
   ```

---

## 🤖 Part 2: Discord Bot Setup

### Step 1: Copy API Client to Your Bot

1. Copy these files to your Discord bot project:
   - `tf_api_client.py` (from `BOT_CLIENT_EXAMPLE/`)
   - `discord_bot_example.py` (reference for implementing commands)

2. Your bot structure should look like:
```
your-discord-bot/
├── bot.py                    # Your main bot file
├── cogs/
│   └── tf_commands.py       # TF management commands (use discord_bot_example.py as reference)
├── utils/
│   └── tf_api_client.py     # API client (copy from BOT_CLIENT_EXAMPLE)
├── .env
├── requirements.txt
└── README.md
```

### Step 2: Install Dependencies

Add to your bot's `requirements.txt`:
```
discord.py>=2.0.0
aiohttp>=3.8.0
groq>=0.4.0
python-dotenv>=0.19.0
```

Install:
```bash
pip install -r requirements.txt
```

### Step 3: Configure Bot `.env`

Add these to your Discord bot's `.env` file:

```bash
# Discord Bot Token
DISCORD_TOKEN=your-discord-bot-token

# Groq API
GROQ_API_KEY=your-groq-api-key

# TF System API
TF_SYSTEM_API_URL=https://your-tf-system.onrender.com/api/v1
TF_SYSTEM_API_KEY=IHfR9mXy3kL8nP2qT6vZ9wB4cF7jM0xN5sA1dG8eK4hU
```

**⚠️ Important:** Use the SAME API key you generated in Part 1!

### Step 4: Integrate with Your Bot

#### Option A: Use the Example Cog (Recommended)

1. Copy `discord_bot_example.py` to your bot's `cogs/` folder as `tf_commands.py`

2. Modify it to fit your existing bot structure (it's well-commented)

3. Load the cog in your main bot file:
```python
# In your bot.py
await bot.load_extension('cogs.tf_commands')
```

#### Option B: Manual Integration

If you already have command handlers, just import and use the API client:

```python
from utils.tf_api_client import TFSystemAPI

# Initialize
tf_api = TFSystemAPI()

# Use in your commands
@bot.command()
async def change_rank(ctx, member_name: str, new_rank: str):
    result = await tf_api.change_rank_by_name(
        member_name=member_name,
        new_rank=new_rank,
        discord_user_id=str(ctx.author.id)
    )
    
    if result['success']:
        await ctx.send(f"✅ Changed {member_name}'s rank to {new_rank}!")
    else:
        await ctx.send(f"❌ Error: {result['message']}")
```

### Step 5: Modify Groq Integration

Your Groq AI should parse user intent. Here's the system prompt to use:

```python
from groq import Groq
import json


async def parse_command(user_message: str):
    system_prompt = """You are a command parser for a Taskforce Management System.
Parse commands and return JSON with:
{
  "action": "change_rank|get_member_info|list_members|add_member|remove_member|log_activity",
  "parameters": {
    "member_name": "name",
    "new_rank": "rank",
    "activity_type": "Raid|Patrol|Training|Mission|Tryout"
  }
}

Valid ranks: Aspirant, Novice, Adept, Crusader, Paladin, Exemplar, Prospect, Commander, Marshal, General, Chief General"""
    
    completion = groq_client.chat.completions.create(
        model="llama-3.1-70b-versatile",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ],
        temperature=0.1
    )
    
    return json.loads(completion.choices[0].message.content)
```

### Step 6: Set Up Role Permissions

In your Discord server:

1. Create/verify these roles exist:
   - **Commander**
   - **Marshal**
   - **General**

2. Assign roles to staff members who should manage TF

3. The bot will check these roles before executing commands

### Step 7: Deploy Bot to Render

1. Push your bot code to GitHub

2. Create new Web Service on Render:
   - Connect your bot repository
   - Set build command: `pip install -r requirements.txt`
   - Set start command: `python bot.py`

3. Add environment variables:
   - `DISCORD_TOKEN`
   - `GROQ_API_KEY`
   - `TF_SYSTEM_API_URL` (Flask app URL + `/api/v1`)
   - `TF_SYSTEM_API_KEY`

4. Deploy!

---

## 🧪 Part 3: Testing

### Test Locally First

Before deploying, test locally:

1. Start Flask app:
```bash
cd TF_System/Taskforce_System
python app.py
```

2. In another terminal, start your Discord bot:
```bash
cd your-discord-bot
python bot.py
```

3. Test commands in Discord:
```
/tf change João's rank to Commander
/tf show all members with rank Paladin
/tf what rank is Sarah?
```

### Test API Directly

You can test the API with curl:

```bash
# Test status
curl -H "Authorization: Bearer YOUR_API_KEY" \
  https://your-tf-system.onrender.com/api/v1/status

# Get members
curl -H "Authorization: Bearer YOUR_API_KEY" \
  https://your-tf-system.onrender.com/api/v1/members

# Change rank
curl -X PATCH \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"rank":"Commander","reason":"Test"}' \
  https://your-tf-system.onrender.com/api/v1/members/1/rank
```

---

## 📊 Part 4: Monitoring

### Check API Logs

In your Flask app, logs will show:
```
API Access - GET /members | User: 123456789 | Status: 200 | Success: True | IP: 1.2.3.4
```

### Rate Limiting

- Default: 100 requests per minute
- Headers in response:
  - `X-RateLimit-Limit: 100`
  - `X-RateLimit-Remaining: 99`
  - `X-RateLimit-Reset: 1638360000`

If exceeded:
```json
{
  "success": false,
  "error": "rate_limit_exceeded",
  "message": "Rate limit exceeded. Try again in 60 seconds."
}
```

### Discord Notifications

When ranks change, you'll see notifications in #cortex-notis:

```
🔔 Rank Update
Member: João
Old Rank: Paladin
New Rank: Commander
Changed by: Discord Bot
Reason: Promoted via Discord by User#1234
Roblox Sync: ✅ Success
```

---

## ❓ Troubleshooting

### Bot Can't Connect to API

**Error:** `Failed to connect to TF System`

**Solutions:**
1. Check `TF_SYSTEM_API_URL` is correct (should end with `/api/v1`)
2. Verify Flask app is running on Render
3. Test API URL in browser: `https://your-app.onrender.com/api/v1/status`

### Authentication Failed

**Error:** `Invalid API key`

**Solutions:**
1. Verify API keys match in both `.env` files
2. Check for extra spaces or quotes around key
3. Regenerate key if needed: `python generate_api_key.py`

### Rank Change Fails

**Error:**` Invalid rank "XYZ"`

**Solutions:**
1. Check rank spelling (case-sensitive)
2. Valid ranks: Aspirant, Novice, Adept, Crusader, Paladin, Exemplar, Prospect, Commander, Marshal, General, Chief General
3. Use exact spelling from list

### Roblox Sync Fails

**Error:** `Roblox sync failed`

**Solutions:**
1. Check `ROBLOX_COOKIE` is valid in Flask app
2. Update cookie: Go to `/staff/update_cookie` in web app
3. Verify Roblox group permissions

### No Notifications in Discord

**Error:** Notifications not appearing

**Solutions:**
1. Check `DISCORD_NOTIFICATION_WEBHOOK_URL` in Flask app .env
2. Verify webhook is for `cortex-notis` channel
3. Test webhook manually:
```bash
curl -X POST \
  -H "Content-Type: application/json" \
  -d '{"content":"Test notification"}' \
  YOUR_WEBHOOK_URL
```

### Permission Denied

**Error:** User gets "no permission" message

**Solutions:**
1. Verify user has Commander, Marshal, or General role
2. Check role names match exactly (case-sensitive in code)
3. Bot needs permission to read roles

---

## 📝 Example Commands

Once everything is set up, users can use natural language:

```
/tf change João's rank to Commander
→ ✅ Updated João's rank from Paladin to Commander

/tf show all members
→ 📋 Shows member list grouped by rank

/tf show all Commanders
→ 📋 Shows only members with Commander rank

/tf what rank is Sarah?
→ 📊 Sarah is currently a Crusader

/tf add member Mike with rank Aspirant
→ ✅ Added Mike as Aspirant

/tf log a raid for Alice
→ ✅ Logged Raid (3 points) for Alice

/tf remove member Bob
→ ✅ Successfully removed Bob
```

---

## 🔐 Security Checklist

Before going to production:

- [ ] API key is strong and random (use `generate_api_key.py`)
- [ ] API key is in `.env` files (NOT committed to git)
- [ ] `.env` is in `.gitignore`
- [ ] Using HTTPS in production (Render provides this)
- [ ] Rate limiting is enabled
- [ ] Only allowed Discord roles can use commands
- [ ] Webhook URL is secure and not publicly shared
- [ ] Different API keys for dev and production (optional but recommended)

---

## 🎉 You're Done!

Your Discord bot should now be able to:
- ✅ Change member ranks
- ✅ View member information
- ✅ List members by rank
- ✅ Add/remove members
- ✅ Log activities
- ✅ Send notifications to #cortex-notis
- ✅ Sync changes to Roblox

All using natural language thanks to Groq AI! 🚀

---

## 📚 Additional Resources

- [Full API Documentation](./DISCORD_BOT_INTEGRATION.md)
- [API Client Reference](./BOT_CLIENT_EXAMPLE/tf_api_client.py)
- [Bot Example Code](./BOT_CLIENT_EXAMPLE/discord_bot_example.py)
- [Implementation Plan](./implementation_plan.md) (in brain folder)

## 💬 Need Help?

If you encounter issues:
1. Check logs in both Flask app and Discord bot
2. Test API endpoints with curl
3. Verify environment variables are set correctly
4. Check Discord bot has proper permissions
5. Review this guide step-by-step

---

**Last Updated:** 2025-12-04
**Version:** 1.0.0
