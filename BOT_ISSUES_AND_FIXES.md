# Discord Bot Issues - Diagnosis & Fixes

## 🐛 Critical Issues Found

I identified **6 major issues** in your Discord bot code that are preventing it from working:

---

## ❌ Issue #1: Wrong API URL in .env

**Location:** `.env` line 36

**Current (WRONG):**
```bash
TF_SYSTEM_API_URL=https://your-tf-system.onrender.com/api/v1
```

**Problem:** This is a placeholder URL, not your actual Flask app URL!

**Fix:**
```bash
# If running locally together:
TF_SYSTEM_API_URL=http://localhost:5000/api/v1

# If Flask is on Render:
TF_SYSTEM_API_URL=https://YOUR-ACTUAL-RENDER-URL.onrender.com/api/v1
```

**Action:** Replace with your actual Render URL for the Flask app

---

## ❌ Issue #2: Wrong Import Statement in bot.py

**Location:** `bot/bot.py` line 11

**Current (WRONG):**
```python
import tf_api_client
```

**Problem:** This imports the module, not the class. Later you try to use `tf_api_client.TFSystemAPI()` which won't work properly.

**Fix:**
```python
from tf_api_client import TFSystemAPI
```

And on line 86, change:
```python
# WRONG:
tf_api = tf_api_client.TFSystemAPI()

# CORRECT:
tf_api = TFSystemAPI()
```

---

## ❌ Issue #3: Cog Loading in Wrong Place

**Location:** `bot/bot.py` line 171

**Current (WRONG):**
```python
# Send first chunk as followup
await interaction.followup.send(chunks[0])
await bot.load_extension('cogs.tf_commands')  # ❌ THIS IS WRONG!

# Send remaining chunks if any
for chunk in chunks[1:]:
```

**Problem:** You're trying to load the cog INSIDE the `/ask` command handler! This is completely wrong - it should load once when the bot starts.

**Fix:** Remove line 171 entirely and add to the `on_ready` event:

```python
@bot.event
async def on_ready():
    """Called when the bot is ready."""
    # Load TF commands cog
    try:
        await bot.load_extension('cogs.tf_commands')
        print("✓ Loaded TF commands cog")
    except Exception as e:
        print(f"✗ Error loading TF commands: {e}")
    
    try:
        synced = await bot.tree.sync()
        print(f"✓ Synced {len(synced)} slash command(s)")
    except Exception as e:
        print(f"✗ Error syncing commands: {e}")
    
    print(f"✓ Bot ready as {bot.user}")
    print(f"✓ Using Groq model: {GROQ_MODEL}")
    print(f"✓ Cooldown: {COOLDOWN_SECONDS}s | Max question length: {MAX_QUESTION_LENGTH} chars")
```

---

## ❌ Issue #4: Duplicate Exception Handlers

**Location:** `bot/bot.py` lines 178-186

**Current (WRONG):**
```python
    except Exception as e:
        error_message = f"❌ Groq API Error: {str(e)}"
        print(f"Groq API Error: {e}")
        await interaction.followup.send(error_message)
        
    except Exception as e:  # ❌ DUPLICATE!
        error_message = f"❌ Unexpected error: {str(e)}"
        print(f"Unexpected error: {e}")
        await interaction.followup.send(error_message)
```

**Problem:** You have TWO `except Exception` blocks! Python will never reach the second one.

**Fix:**
```python
    except Exception as e:
        error_message = f"❌ Error: {str(e)}"
        print(f"Error in /ask command: {e}")
        await interaction.followup.send(error_message)
```

---

## ❌ Issue #5: Wrong import in tf_commands.py  

**Location:** `bot/cogs/tf_commands.py` line 17

**Current (WRONG):**
```python
from tf_api_client import TFSystemAPI
```

**Problem:** The cog is in `cogs/` folder, but `tf_api_client.py` is in parent `bot/` folder. This import will fail!

**Fix:** Change to relative import:
```python
from ..tf_api_client import TFSystemAPI

# OR use sys.path
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from tf_api_client import TFSystemAPI
```

---

## ❌ Issue #6: Deprecated Command Decorator

**Location:** `bot/bot.py` lines 89-90

**Current (WRONG):**
```python
@bot.command(name="change_rank", description="Change a member's rank")
@app_commands.describe(member_name="The member to change the rank of", new_rank="The new rank")
async def change_rank(ctx, member_name: str, new_rank: str):
```

**Problem:** Mixing prefix commands (`@bot.command`) with slash command decorators (`@app_commands.describe`). This won't work and is confusing.

**Fix:** Either use it as a prefix command OR remove it entirely (since you have TF commands in the cog):

**Option 1 - Make it a proper prefix command:**
```python
@bot.command(name="change_rank")
async def change_rank(ctx, member_name: str, new_rank: str):
    """Change a member's rank (prefix command: !change_rank)"""
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

**Option 2 - Remove it completely** (recommended, since you have `/tf` command in cog)

---

## 📋 Summary of All Fixes Needed

### In `.env`:
1. ✅ Update `TF_SYSTEM_API_URL` to your actual URL

### In `bot/bot.py`:
1. ✅ Line 11: Change `import tf_api_client` to `from tf_api_client import TFSystemAPI`
2. ✅ Line 86: Change `tf_api = tf_api_client.TFSystemAPI()` to `tf_api = TFSystemAPI()`
3. ✅ Line 171: **DELETE** `await bot.load_extension('cogs.tf_commands')`
4. ✅ Line 73-84: Add cog loading to `on_ready` event
5. ✅ Lines 178-186: Fix duplicate exception handlers (keep only one)
6. ✅ Lines 89-101: Remove or fix the `change_rank` command

### In `bot/cogs/tf_commands.py`:
1. ✅ Line 17: Fix import path (use relative import)

---

## 🔧 Quick Fix Script

Here's what your corrected `bot.py` should look like for the key sections:

### Imports (top of file):
```python
import os
import discord
from discord.ext import commands
from discord import app_commands
from groq import Groq
from dotenv import load_dotenv
from typing import Optional
import asyncio
from collections import defaultdict
from datetime import datetime, timedelta
from tf_api_client import TFSystemAPI  # ✅ FIXED

load_dotenv()
```

### On Ready Event:
```python
@bot.event
async def on_ready():
    """Called when the bot is ready."""
    # Load TF commands cog  # ✅ ADDED
    try:
        await bot.load_extension('cogs.tf_commands')
        print("✓ Loaded TF commands cog")
    except Exception as e:
        print(f"✗ Error loading TF commands: {e}")
    
    try:
        synced = await bot.tree.sync()
        print(f"✓ Synced {len(synced)} slash command(s)")
    except Exception as e:
        print(f"✗ Error syncing commands: {e}")
    
    print(f"✓ Bot ready as {bot.user}")
    print(f"✓ Using Groq model: {GROQ_MODEL}")
    print(f"✓ Cooldown: {COOLDOWN_SECONDS}s | Max question length: {MAX_QUESTION_LENGTH} chars")
```

### TF API Initialization (around line 86):
```python
# Initialize TF API  # ✅ FIXED
tf_api = TFSystemAPI()
```

### In /ask command (remove line 171):
```python
# Send first chunk as followup
await interaction.followup.send(chunks[0])
# ✅ REMOVED: await bot.load_extension('cogs.tf_commands'

# Send remaining chunks if any
for chunk in chunks[1:]:
    await interaction.channel.send(chunk)
    await asyncio.sleep(0.5)
```

### Fix exception handlers (lines 178+):
```python
except Exception as e:  # ✅ FIXED - Single handler
    error_message = f"❌ Error: {str(e)}"
    print(f"Error in /ask command: {e}")
    await interaction.followup.send(error_message)
```

---

## 🧪 Testing Steps

After fixing:

1. **Update .env** with correct URL
2. **Fix imports** in both files
3. **Remove duplicate code**
4. **Test locally first:**
```bash
cd bot
python bot.py
```

5. **Check console output for:**
   - ✓ Loaded TF commands cog
   - ✓ Synced X slash command(s)
   - ✓ Bot ready as [BotName]

6. **Test in Discord:**
```
/tf show all members
/ask hello
```

---

## 🎯 Expected Behavior After Fixes

When bot starts successfully:
```
✓ Loaded TF commands cog
✓ Synced 3 slash command(s)
✓ Bot ready as YourBot#1234
✓ Using Groq model: llama-3.3-70b-versatile
✓ Cooldown: 10s | Max question length: 500 chars
```

Available commands:
- `/tf <command>` - TF management (requires Commander/Marshal/General role)
- `/ask <question>` - Ask AI anything
- `/help` - Show help

---

## 📝 Files to Edit

1. **`.env`** - Update TF_SYSTEM_API_URL
2. **`bot/bot.py`** - Fix imports, move cog loading, remove duplicates
3. **`bot/cogs/tf_commands.py`** - Fix import path

All fixes are documented above with exact line numbers and code!
