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
from tf_api_client import TFSystemAPI


load_dotenv()


# Environment variables
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

ALLOWED_GUILD_ID = os.getenv("ALLOWED_GUILD_ID")

# Initialize Groq client
client = Groq(api_key=GROQ_API_KEY)

# Discord bot setup
# Discord bot setup
intents = discord.Intents.default()
intents.message_content = True  # Required for on_message and mentions
bot = commands.Bot(command_prefix="!", intents=intents)

# Rate limiting tracker



@bot.event
async def on_ready():
    """Called when the bot is ready."""
    # Load TF commands cog
    try:
        await bot.load_extension('cogs.tf_commands')
        print("✓ Loaded TF commands cog")
    except Exception as e:
        print(f"✗ Error loading TF commands: {e}")
        import traceback
        traceback.print_exc()
    
    # Load Mission Tracker cog
    try:
        await bot.load_extension('cogs.mission_tracker')
        print("✓ Loaded Mission Tracker cog")
    except Exception as e:
        print(f"✗ Error loading Mission Tracker cog: {e}")
        import traceback
        traceback.print_exc()
    
    try:
        synced = await bot.tree.sync()
        print(f"✓ Synced {len(synced)} slash command(s)")
    except Exception as e:
        print(f"✗ Error syncing commands: {e}")
    
    print(f"✓ Bot ready as {bot.user}")
    print(f"✓ Message Content Intent: {bot.intents.message_content}")

# Initialize TF System API
tf_api = TFSystemAPI()




@bot.event
async def on_message(message):
    # Process commands needed if using message commands too
    await bot.process_commands(message)

@bot.event
async def on_error(event, *args, **kwargs):
    """Global error handler."""
    print(f"Error in {event}: {args} {kwargs}")


if __name__ == "__main__":
    if not DISCORD_TOKEN:
        print("❌ ERROR: DISCORD_TOKEN not found in environment variables!")
        exit(1)
    
    if not GROQ_API_KEY:
        print("❌ ERROR: GROQ_API_KEY not found in environment variables!")
        exit(1)
    
    print("🚀 Starting bot...")
    bot.run(DISCORD_TOKEN)
