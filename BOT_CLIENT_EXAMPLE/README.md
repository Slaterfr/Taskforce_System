# Discord Bot Client Example

This folder contains example code for integrating your Discord bot with TF_System API.

## 📁 Files

### `tf_api_client.py`
Complete Python client for TF System API. This provides all the methods you need to interact with the Flask API.

**Features:**
- ✅ Async/await support (works with discord.py)
- ✅ Automatic authentication
- ✅ Error handling
- ✅ Rate limit detection
- ✅ All API endpoints wrapped in easy methods

**Quick Start:**
```python
from tf_api_client import TFSystemAPI

# Initialize
api = TFSystemAPI(
    api_url="https://your-tf-system.onrender.com/api/v1",
    api_key="your-api-key-here"
)

# Use in your bot
result = await api.change_rank_by_name("João", "Commander")
```

---

### `discord_bot_example.py`
Complete Discord bot cog example showing how to:
- Use natural language commands with Groq AI
- Integrate with TF System API
- Handle permissions (Commander/Marshal/General roles)
- Create Discord embeds for responses
- Parse user intent and execute actions

**Includes examples for:**
- ✅ Change member rank
- ✅ Get member info
- ✅ List members (with filters)
- ✅ Add new member
- ✅ Remove member
- ✅ Log activities

---

## 🚀 How to Use

### 1. Copy to Your Bot Project

Copy both files to your Discord bot:
```
your-bot/
├── utils/
│   └── tf_api_client.py      # Copy this
└── cogs/
    └── tf_commands.py         # Rename discord_bot_example.py to this
```

### 2. Install Dependencies

```bash
pip install discord.py aiohttp groq python-dotenv
```

### 3. Configure Environment Variables

Create/update `.env`:
```bash
DISCORD_TOKEN=your-discord-token
GROQ_API_KEY=your-groq-ai-key
TF_SYSTEM_API_URL=https://your-tf-system.onrender.com/api/v1
TF_SYSTEM_API_KEY=your-api-key
```

### 4. Load in Your Bot

```python
# In your main bot.py
await bot.load_extension('cogs.tf_commands')
```

### 5. Test!

In Discord:
```
/tf change João's rank to Commander
/tf show all members
/tf what rank is Sarah?
```

---

## 🎯 Customization Guide

### Modify Allowed Roles

In `discord_bot_example.py`, change line 18:
```python
ALLOWED_ROLES = ['YourRole1', 'YourRole2', 'YourRole3']
```

### Change AI Model

In `parse_intent_with_groq()`, change the model:
```python
completion = groq_client.chat.completions.create(
    model="your-preferred-groq-model",  # Change this
    ...
)
```

### Add Custom Commands

Add new handler methods:
```python
async def _handle_your_custom_action(self, interaction, params):
    """Handle your custom action"""
    # Your code here
    result = await tf_api.your_method(...)
    await interaction.followup.send(f"Result: {result}")
```

Then add to the main command dispatcher:
```python
elif intent['action'] == 'your_custom_action':
    await self._handle_your_custom_action(interaction, intent['parameters'])
```

---

## 📖 API Methods Reference

### Member Management
- `get_members(search, rank, limit)` - List members
- `get_member(member_id)` - Get member details
- `search_member(name, field)` - Search by name
- `change_member_rank(member_id, new_rank, reason, discord_user_id)` - Change rank
- `add_member(discord_username, roblox_username, current_rank, discord_user_id)` - Add member
- `remove_member(member_id, discord_user_id)` - Remove member

### Rank Management
- `get_ranks()` - List all available ranks

### Activity Management
- `log_activity(member_id, activity_type, description, activity_date, discord_user_id)` - Log activity
- `get_member_activities(member_id, limit)` - Get member activities

### System
- `get_status()` - System status
- `verify_auth()` - Verify API key

### Helper Methods
- `find_member_by_name(name)` - Find member by Discord or Roblox name
- `change_rank_by_name(member_name, new_rank, reason, discord_user_id)` - Change rank by name

---

## ⚠️ Important Notes

1. **This is example code** - Modify it to fit your bot's architecture
2. **Error handling** - The examples include basic error handling, enhance as needed
3. **Rate limiting** - API has 100 req/min limit by default
4. **Permissions** - Always check user roles before executing commands
5. **Testing** - Test locally before deploying

---

## 🔗 Related Documentation

- [Full Setup Guide](../DISCORD_BOT_SETUP_GUIDE.md) - Complete setup instructions
- [API Documentation](../DISCORD_BOT_INTEGRATION.md) - All API endpoints
- [Environment Variables](../env.example) - Required configuration

---

## 💡 Tips

- Use the helper methods (`find_member_by_name`, `change_rank_by_name`) for convenience
- Always pass `discord_user_id` for audit logging
- Check API responses for `success` field before assuming it worked
- Customize embed colors and messages to match your server's style
- Add confirmation buttons for destructive actions (remove member)

---

## 🐛 Troubleshooting

**Import Error:**
```bash
pip install discord.py aiohttp groq
```

**API Key Invalid:**
- Check `.env` has correct `TF_SYSTEM_API_KEY`
- Verify it matches Flask app's `DISCORD_BOT_API_KEY`

**Rate Limit:**
- Add delays between bulk operations
- Implement queuing for mass updates

**Permission Denied:**
- User needs Commander, Marshal, or General role
- Check role names match exactly

---

**Need Help?** See the main setup guide: [DISCORD_BOT_SETUP_GUIDE.md](../DISCORD_BOT_SETUP_GUIDE.md)
