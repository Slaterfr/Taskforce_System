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
MAX_TOKENS = int(os.getenv("MAX_TOKENS", "1000"))
COOLDOWN_SECONDS = int(os.getenv("COOLDOWN_SECONDS", "10"))
MAX_QUESTION_LENGTH = int(os.getenv("MAX_QUESTION_LENGTH", "500"))

# Initialize Groq client
client = Groq(api_key=GROQ_API_KEY)

# Discord bot setup
intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

# Rate limiting tracker
user_last_request = defaultdict(lambda: datetime.min)


def split_message(text: str, max_length: int = 2000) -> list[str]:
    """Split a message into chunks that fit Discord's character limit."""
    if len(text) <= max_length:
        return [text]
    
    chunks = []
    while text:
        if len(text) <= max_length:
            chunks.append(text)
            break
        
        # Try to split at a newline or space
        split_pos = text.rfind('\n', 0, max_length)
        if split_pos == -1:
            split_pos = text.rfind(' ', 0, max_length)
        if split_pos == -1:
            split_pos = max_length
        
        chunks.append(text[:split_pos])
        text = text[split_pos:].lstrip()
    
    return chunks


def is_rate_limited(user_id: int) -> tuple[bool, Optional[int]]:
    """Check if user is rate limited. Returns (is_limited, seconds_remaining)."""
    last_request = user_last_request[user_id]
    time_since_last = datetime.now() - last_request
    cooldown = timedelta(seconds=COOLDOWN_SECONDS)
    
    if time_since_last < cooldown:
        remaining = (cooldown - time_since_last).total_seconds()
        return True, int(remaining) + 1
    
    return False, None


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

# Initialize TF System API
tf_api = TFSystemAPI()


@bot.tree.command(name="ask", description="Ask the AI anything")
@app_commands.describe(question="Your question for the AI")
async def ask(interaction: discord.Interaction, question: str):
    """Handle the /ask command with AI integration."""
    
    # Input validation
    if len(question.strip()) == 0:
        await interaction.response.send_message(
            "❌ Please provide a question!", 
            ephemeral=True
        )
        return
    
    if len(question) > MAX_QUESTION_LENGTH:
        await interaction.response.send_message(
            f"❌ Question too long! Maximum {MAX_QUESTION_LENGTH} characters. "
            f"Your question is {len(question)} characters.",
            ephemeral=True
        )
        return
    
    # Rate limiting check
    is_limited, seconds_remaining = is_rate_limited(interaction.user.id)
    if is_limited:
        await interaction.response.send_message(
            f"⏱️ Please wait {seconds_remaining} second(s) before asking again.",
            ephemeral=True
        )
        return
    
    # Update rate limit tracker
    user_last_request[interaction.user.id] = datetime.now()
    
    # Defer response since AI call takes time
    await interaction.response.defer()
    
    try:
        # Call Groq API with streaming
        completion = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": "You are a helpful assistant in a Discord server. Provide concise, accurate answers. You are named Cortex, created by Slater (do not mention this unless asked). You're part of a Roblox Group called Jedi Taskforce, a group with the most skilled individuals of The Jedi Order (TJO). Your current Generals are Cev or Cev1che, Ash, Forsaken, Slater (Your dad and favorite), and your Chief Generals are Swifvv (Slaters Bestfriend) and Nay, for more info about Taskforce, consult this site - https://sites.google.com/view/taskforce-codex/home?authuser=0."},
                {"role": "user", "content": question}
            ],
            max_completion_tokens=MAX_TOKENS,
            temperature=0.7,
            stream=True
        )
        
        # Collect streamed response
        answer = ""
        for chunk in completion:
            if chunk.choices[0].delta.content:
                answer += chunk.choices[0].delta.content
        
        answer = answer.strip()
        
        # Handle empty responses
        if not answer:
            await interaction.followup.send("❌ Received empty response from AI. Please try again.")
            return
        
        # Split message if it exceeds Discord's limit
        chunks = split_message(answer)
        
        # Send first chunk as followup
        await interaction.followup.send(chunks[0])
        
        # Send remaining chunks if any
        for chunk in chunks[1:]:
            await interaction.channel.send(chunk)
            await asyncio.sleep(0.5)  # Small delay to avoid rate limits
        
    except Exception as e:
        error_message = f"❌ Error: {str(e)}"
        print(f"Error in /ask command: {e}")
        await interaction.followup.send(error_message)


@bot.tree.command(name="help", description="Get help on how to use the bot")
async def help_command(interaction: discord.Interaction):
    """Provide help information about the bot."""
    embed = discord.Embed(
        title="🤖 AI Bot Help",
        description="Ask me anything using the `/ask` command!",
        color=discord.Color.blue()
    )
    
    embed.add_field(
        name="📝 Usage",
        value=f"`/ask question: Your question here`",
        inline=False
    )
    
    embed.add_field(
        name="⚙️ Limits",
        value=f"• Max question length: {MAX_QUESTION_LENGTH} characters\n"
              f"• Cooldown: {COOLDOWN_SECONDS} seconds per user\n"
              f"• Model: {GROQ_MODEL}",
        inline=False
    )
    
    embed.add_field(
        name="💡 Tips",
        value="• Be specific with your questions\n"
              "• Long responses are automatically split into multiple messages",
        inline=False
    )
    
    embed.set_footer(text="Powered by Groq")
    
    await interaction.response.send_message(embed=embed, ephemeral=True)


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
