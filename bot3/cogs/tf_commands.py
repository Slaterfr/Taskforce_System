"""
Discord Bot Commands for TF System Integration

"""

import discord
from discord.ext import commands
from discord import app_commands
import os
from groq import Groq
import json
import asyncio
from dotenv import load_dotenv

# Load .env from parent bot directory
env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
load_dotenv(env_path)
print(f"[TF Commands] Loaded .env from: {env_path}")

# Import the TF API client (from parent directory)
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tf_api_client import TFSystemAPI

# Get Groq configuration from environment
GROQ_API_KEY = os.getenv('GROQ_API_KEY')
GROQ_MODEL = os.getenv('GROQ_MODEL')
ALLOWED_GUILD_ID = os.getenv('ALLOWED_GUILD_ID')

# Debug: Show which model is being used
print(f"[TF Commands] Using Groq model: {GROQ_MODEL}")

# Initialize Groq client
groq_client = Groq(api_key=GROQ_API_KEY)

# Initialize TF System API
tf_api = TFSystemAPI(
    api_url=os.getenv('TF_SYSTEM_API_URL'),
    api_key=os.getenv('TF_SYSTEM_API_KEY')
)

# Define allowed roles (Commander, Marshal, General)
ALLOWED_ROLES = ['Staff Team', 'Prospect', 'Commander', 'Marshal', 'General']


def has_tf_permissions():
    """Decorator to check if user has permission to manage TF"""
    async def predicate(interaction: discord.Interaction):
        # Check if user has any of the allowed roles
        user_roles = [role.name for role in interaction.user.roles]
        has_permission = any(role in ALLOWED_ROLES for role in user_roles)
        
        if not has_permission:
            await interaction.response.send_message(
                "❌ You don't have permission to use this command. "
                f"Required roles: {', '.join(ALLOWED_ROLES)}",
                ephemeral=True
            )
        
        return True
    
    return app_commands.check(predicate)


async def parse_intent_with_groq(user_message: str) -> dict:
    """
    Use Groq AI to parse user intent and extract entities
    
    Args:
        user_message: The user's natural language command
    
    Returns:
        dict: Parsed intent with action, parameters, etc.
    """
    system_prompt = """You are a command parser for a Taskforce Management System.
Parse user commands and extract the intent and entities.

Valid actions:
- change_rank: Change a member's rank
- get_member_info: Get information about a member
- list_members: List all members or filter by rank
- add_member: Add a new member
- remove_member: Remove a member
- log_activity: Log an activity for a member
- remove_activity: Remove/delete an activity entry for a member

Valid ranks: Aspirant, Novice, Adept, Crusader, Paladin, Exemplar, Prospect, Commander, Marshal, General, Chief General
Valid activity types: Raid, Patrol, Training, Mission, Tryout, Canceled Training, Cancelled Tryout

IMPORTANT: Recognize these variations for listing members:
- "show all members" -> list_members with no rank filter
- "list all members" -> list_members with no rank filter
- "show all [rank]" -> list_members with rank filter (e.g., "show all generals" -> rank: "General")
- "list all [rank]s" -> list_members with rank filter (e.g., "list all commanders" -> rank: "Commander")
- "show [rank]s" -> list_members with rank filter
- "list generals" -> list_members with rank: "General"
- "show commanders" -> list_members with rank: "Commander"
- "what rank is [member name]" -> get_member_info with member name
- "what rank is [member name]" -> get_member_info, look up for members with similar letters, people may use nicknames, if i say "slater" i refer to slaterjl2006 for example

Note: Always use SINGULAR form of rank names (General, not Generals; Commander, not Commanders)

CRITICAL: Activity Type Spelling
- "cancelled training" or "canceled training" -> MUST map to "Canceled Training" (one L)
- "cancelled tryout" or "canceled tryout" -> MUST map to "Cancelled Tryout" (two Ls)
- You should also consider "cancelled" or "cancelled event" to map to "Canceled Training"
- This is extremely important for the database to recognize the activity.

IMPORTANT: Activity Removal Recognition
Recognize these patterns for removing activities:
- "remove activity from [member]" -> remove_activity with member name (will need to specify which activity if multiple)
- "remove [activity type] for [member]" -> remove_activity with activity type and member name
- "undo [activity type] for [member]" -> remove_activity with activity type and member name
- "delete activity for [member]" -> remove_activity with member name
- "remove [number] points from [member]" -> May need clarification which activity to remove

Examples of correct parsing:
1. "show all generals" -> {"action": "list_members", "parameters": {"rank": "General"}}
2. "list all commanders" -> {"action": "list_members", "parameters": {"rank": "Commander"}}
3. "show paladins" -> {"action": "list_members", "parameters": {"rank": "Paladin"}}
4. "list everyone" -> {"action": "list_members", "parameters": {}}
5. "change John to Commander" -> {"action": "change_rank", "parameters": {"member_name": "John", "new_rank": "Commander"}}
6. "what rank is Sarah?" -> {"action": "get_member_info", "parameters": {"member_name": "Sarah"}}
7. "log a cancelled training for Clicky" -> {"action": "log_activity", "parameters": {"member_name": "Clicky", "activity_type": "Canceled Training"}}
8. "log a canceled training for Bob" -> {"action": "log_activity", "parameters": {"member_name": "Bob", "activity_type": "Canceled Training"}}
9. "log a cancelled tryout for Steve" -> {"action": "log_activity", "parameters": {"member_name": "Steve", "activity_type": "Cancelled Tryout"}}
10. "remove training for John" -> {"action": "remove_activity", "parameters": {"member_name": "John", "activity_type": "Training"}}
11. "undo raid for Sarah" -> {"action": "remove_activity", "parameters": {"member_name": "Sarah", "activity_type": "Raid"}}

Respond ONLY with a JSON object in this format:
{
  "action": "action_name",
  "parameters": {
    "member_name": "extracted name",
    "new_rank": "rank name",
    "rank": "rank filter",
    "activity_type": "activity type",
    etc.
  },
  "confidence": 0.0-1.0
}

If you can't parse the command, set action to "unknown" and explain in a "reason" field."""

    try:
        completion = groq_client.chat.completions.create(
            model=GROQ_MODEL,  # Use model from environment variable
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            temperature=0.1,
            max_tokens=500
        )
        
        response_text = completion.choices[0].message.content
        
        # Extract JSON from response (in case there's extra text)
        json_start = response_text.find('{')
        json_end = response_text.rfind('}') + 1
        if json_start != -1 and json_end != 0:
            response_text = response_text[json_start:json_end]
        
        intent = json.loads(response_text)
        return intent
        
    except Exception as e:
        # Log the error for debugging but don't expose technical details to users
        print(f"Error parsing intent with Groq: {e}")
        return {
            "action": "unknown",
            "reason": "I had trouble understanding that command",
            "confidence": 0.0
        }



class ResponseHandler:
    """Abstracts the difference between Interaction and Message responses"""
    def __init__(self, context, is_interaction=True):
        self.context = context
        self.is_interaction = is_interaction

    async def send(self, content=None, embed=None):
        if self.is_interaction:
            # For interactions, use followup (assumes defer was called)
            await self.context.followup.send(content=content, embed=embed)
        else:
            # For messages, use channel.send
            await self.context.channel.send(content=content, embed=embed)

    @property
    def user(self):
        return self.context.user if self.is_interaction else self.context.author


class TFSystemCog(commands.Cog):
    """Cog for TF System management commands"""
    
    def __init__(self, bot):
        self.bot = bot
    
    # Helper to check permissions synchronously for message events
    def check_permissions(self, user):
        user_roles = [role.name for role in user.roles]
        return any(role in ALLOWED_ROLES for role in user_roles)

    @commands.Cog.listener()
    async def on_message(self, message):
        # Ignore messages from self
        if message.author == self.bot.user:
            return

        # Check if bot is mentioned
        if self.bot.user.mentioned_in(message) and not message.mention_everyone:
            # Check for allowed guild
            if ALLOWED_GUILD_ID and str(message.guild.id) != str(ALLOWED_GUILD_ID):
               # Optional: log or ignore. Ignoring is usually safer to avoid spam.
               return
            # Clean content: remove mention
            content = message.content.replace(f'<@{self.bot.user.id}>', '').strip()
            # Also handle nickname mentions if any
            content = content.replace(f'<@!{self.bot.user.id}>', '').strip()
            
            if not content:
                await message.channel.send("👋 Hello! How can I help you with the Taskforce System?")
                return

            # Show typing indicator
            async with message.channel.typing():
                # Create a handler wrapper
                handler = ResponseHandler(message, is_interaction=False)
                await self.process_command(handler, content)

    @app_commands.command(name="tf", description="Natural language TF management command")
    @has_tf_permissions()
    async def tf_command(self, interaction: discord.Interaction, command: str):
        if ALLOWED_GUILD_ID and str(interaction.guild_id) != str(ALLOWED_GUILD_ID):
            await interaction.response.send_message(
                "❌ This bot is restricted to the Taskforce server.",
                ephemeral=True
            )
            return

        await interaction.response.defer()  # Processing may take a moment
        handler = ResponseHandler(interaction, is_interaction=True)
        await self.process_command(handler, command)

    async def process_command(self, handler: ResponseHandler, command_text: str):
        """Unified command processing logic"""
        try:
            # Parse intent using Groq
            intent = await parse_intent_with_groq(command_text)
            
            if intent['action'] == 'unknown':
                # Just return a simple error message instead of chatting
                await handler.send("❌ I didn't understand that command. Try rephrasing you request, or contacting a General for support.")
                return
            
            # Execute based on action
            # For actions that modify state, check permissions
            protected_actions = ['change_rank', 'add_member', 'remove_member', 'log_activity', 'remove_activity']
            
            if intent['action'] in protected_actions:
                 if not self.check_permissions(handler.user):
                    await handler.send(
                        f"❌ You don't have permission to perform this action. "
                        f"Required roles: {', '.join(ALLOWED_ROLES)}"
                    )
                    return

            if intent['action'] == 'change_rank':
                await self._handle_change_rank(handler, intent['parameters'])
                
            elif intent['action'] == 'get_member_info':
                await self._handle_get_member_info(handler, intent['parameters'])
            
            elif intent['action'] == 'list_members':
                await self._handle_list_members(handler, intent['parameters'])
            
            elif intent['action'] == 'add_member':
                await self._handle_add_member(handler, intent['parameters'])
            
            elif intent['action'] == 'remove_member':
                await self._handle_remove_member(handler, intent['parameters'])
            
            elif intent['action'] == 'log_activity':
                await self._handle_log_activity(handler, intent['parameters'])
            
            elif intent['action'] == 'remove_activity':
                await self._handle_remove_activity(handler, intent['parameters'])
            
            else:
                # Should not happen if unknown is handled
                await handler.send("❌ Unknown action returned from parser.")
        
        except Exception as e:
            print(f"Error executing TF command: {e}")
            await handler.send(
                f"❌ An error occurred: {str(e)}"
            )


    
    async def _handle_change_rank(self, handler: ResponseHandler, params: dict):
        """Handle rank change requests"""
        member_name = params.get('member_name')
        new_rank = params.get('new_rank')
        
        if not member_name or not new_rank:
            await handler.send(
                "❌ I need both a member name and a new rank."
            )
            return
        
        # Call API to change rank
        result = await tf_api.change_rank_by_name(
            member_name=member_name,
            new_rank=new_rank,
            reason=f"Promoted via Discord by {handler.user.name}",
            discord_user_id=str(handler.user.id)
        )
        
        if result.get('success'):
            member = result['member']
            roblox_sync = result.get('roblox_sync', {})
            
            embed = discord.Embed(
                title="✅ Rank Updated",
                description=f"Successfully updated **{member['discord_username']}**'s rank",
                color=discord.Color.green()
            )
            embed.add_field(name="Old Rank", value=member['old_rank'], inline=True)
            embed.add_field(name="New Rank", value=member['new_rank'], inline=True)
            embed.add_field(name="Roblox Sync", 
                          value="✅ Success" if roblox_sync.get('success') else "❌ Failed",
                          inline=False)
            embed.set_footer(text=f"Changed by {handler.user.name}")
            
            await handler.send(embed=embed)
        else:
            await handler.send(
                f"❌ Failed to change rank: {result.get('message', 'Unknown error')}"
            )
    
    async def _handle_get_member_info(self, handler: ResponseHandler, params: dict):
        """Handle member info requests"""
        member_name = params.get('member_name')
        
        if not member_name:
            await handler.send("❌ I need a member name.")
            return
        
        # Search for member
        member = await tf_api.find_member_by_name(member_name)
        
        if not member:
            await handler.send(
                f"❌ Could not find member **{member_name}**"
            )
            return
        
        # Get detailed info
        detailed_info = await tf_api.get_member(member['id'])
        
        if detailed_info.get('success'):
            member_data = detailed_info['member']
            
            embed = discord.Embed(
                title=f"📊 Member Info: {member_data['discord_username']}",
                color=discord.Color.blue()
            )
            embed.add_field(name="Discord", value=member_data['discord_username'], inline=True)
            embed.add_field(name="Roblox", value=member_data.get('roblox_username') or 'Not set', inline=True)
            embed.add_field(name="Current Rank", value=member_data['current_rank'], inline=True)
            embed.add_field(name="System join Date", 
                          value=member_data.get('join_date', 'Unknown')[:10] if member_data.get('join_date') else 'Unknown',
                          inline=True)
            
            # Add recent activities
            if member_data.get('recent_activities'):
                activities_text = "\n".join([
                    f"• {a['type']} ({a['points']} pts) - {a['date'][:10] if a.get('date') else 'N/A'}"
                    for a in member_data['recent_activities'][:5]
                ])
                embed.add_field(name="Recent Activities", value=activities_text or "None", inline=False)
            
            await handler.send(embed=embed)
        else:
            await handler.send(
                f"❌ Failed to get member info: {detailed_info.get('message')}"
            )
    
    async def _handle_list_members(self, handler: ResponseHandler, params: dict):
        """Handle list members requests"""
        rank_filter = params.get('rank')
        
        # Get members
        result = await tf_api.get_members(rank=rank_filter)
        
        if result.get('success'):
            members = result['members']
            
            if not members:
                await handler.send(
                    f"No members found" + (f" with rank **{rank_filter}**" if rank_filter else "")
                )
                return
            
            # Create embeds (Discord has limits, so paginate if needed)
            embed = discord.Embed(
                title=f"📋 Members" + (f" - Rank: {rank_filter}" if rank_filter else ""),
                description=f"Total: {len(members)} members",
                color=discord.Color.blue()
            )
            
            # Group by rank
            members_by_rank = {}
            for member in members:
                rank = member['current_rank']
                if rank not in members_by_rank:
                    members_by_rank[rank] = []
                members_by_rank[rank].append(member['discord_username'])
            
            # Add fields for each rank
            for rank, member_list in sorted(members_by_rank.items()):
                members_text = ", ".join(member_list[:10])  # Limit to avoid overflow
                if len(member_list) > 10:
                    members_text += f" ... +{len(member_list) - 10} more"
                embed.add_field(name=f"{rank} ({len(member_list)})", value=members_text, inline=False)
            
            await handler.send(embed=embed)
        else:
            await handler.send(
                f"❌ Failed to get members: {result.get('message')}"
            )
    
    async def _handle_add_member(self, handler: ResponseHandler, params: dict):
        """Handle add member requests"""
        discord_username = params.get('discord_username')
        roblox_username = params.get('roblox_username')
        rank = params.get('rank', 'Aspirant')
        
        if not discord_username:
            await handler.send("❌ I need a Discord username.")
            return
        
        # Add member
        result = await tf_api.add_member(
            discord_username=discord_username,
            roblox_username=roblox_username,
            current_rank=rank,
            discord_user_id=str(handler.user.id)
        )
        
        if result.get('success'):
            member = result['member']
            
            embed = discord.Embed(
                title="✅ Member Added",
                description=f"Successfully added **{member['discord_username']}**",
                color=discord.Color.green()
            )
            embed.add_field(name="Discord", value=member['discord_username'], inline=True)
            embed.add_field(name="Roblox", value=member.get('roblox_username') or 'Not set', inline=True)
            embed.add_field(name="Rank", value=member['current_rank'], inline=True)
            embed.set_footer(text=f"Added by {handler.user.name}")
            
            await handler.send(embed=embed)
        else:
            await handler.send(
                f"❌ Failed to add member: {result.get('message')}"
            )
    
    async def _handle_remove_member(self, handler: ResponseHandler, params: dict):
        """Handle remove member requests"""
        member_name = params.get('member_name')
        
        if not member_name:
            await handler.send("❌ I need a member name.")
            return
        
        # Find member first
        member = await tf_api.find_member_by_name(member_name)
        
        if not member:
            await handler.send(
                f"❌ Could not find member **{member_name}**"
            )
            return
        
        # Remove member
        result = await tf_api.remove_member(
            member_id=member['id'],
            discord_user_id=str(handler.user.id)
        )
        
        if result.get('success'):
            await handler.send(
                f"✅ Successfully removed **{member_name}** from the system."
            )
        else:
            await handler.send(
                f"❌ Failed to remove member: {result.get('message')}"
            )
    
    async def _handle_log_activity(self, handler: ResponseHandler, params: dict):
        """Handle log activity requests"""
        member_name = params.get('member_name')
        activity_type = params.get('activity_type')
        description = params.get('description')
        
        if not member_name or not activity_type:
            await handler.send(
                "❌ I need both a member name and an activity type."
            )
            return
        
        # Find member
        member = await tf_api.find_member_by_name(member_name)
        
        if not member:
            await handler.send(
                f"❌ Could not find member **{member_name}**"
            )
            return
        
        # Log activity
        try:
            result = await tf_api.log_activity(
                member_id=member['id'],
                activity_type=activity_type,
                description=description or f"{activity_type} logged via Discord",
                discord_user_id=str(handler.user.id)
            )
            
            if result.get('success'):
                activity = result.get('activity', {})
                points = activity.get('points', 0)
                # Format points (remove .0 if integer)
                points_str = f"{int(points)}" if isinstance(points, (int, float)) and points == int(points) else f"{points}"
                
                # Get quota progress information
                quota_progress = result.get('quota_progress', {})
                total_points = quota_progress.get('total_points', 0)
                quota = quota_progress.get('quota', 0)
                
                # Format total_points and quota (remove .0 if integer)
                total_str = f"{int(total_points)}" if isinstance(total_points, (int, float)) and total_points == int(total_points) else f"{total_points}"
                quota_str = f"{int(quota)}" if isinstance(quota, (int, float)) and quota == int(quota) else f"{quota}"
                
                await handler.send(
                    f"✅ Logged {activity_type} ({points_str} pts) for **{member_name}**, they now have {total_str}/{quota_str} points."
                )
            else:
                await handler.send(
                    f"❌ Failed to log activity: {result.get('message', 'Unknown API error')}"
                )
        except Exception as e:
            await handler.send(f"❌ Error processing log response: {str(e)}")
            print(f"Full result: {locals().get('result', 'No result')}")

    async def _handle_remove_activity(self, handler: ResponseHandler, params: dict):
        """Handle remove activity requests"""
        member_name = params.get('member_name')
        activity_type = params.get('activity_type')
        
        if not member_name:
            await handler.send(
                "❌ I need a member name to find which activity to remove."
            )
            return
        
        # Find member
        member = await tf_api.find_member_by_name(member_name)
        
        if not member:
            await handler.send(
                f"❌ Could not find member **{member_name}**"
            )
            return
        
        # Get member's activities to find the one to remove
        activities_result = await tf_api.get_member_activities(member['id'], limit=50)
        
        if not activities_result.get('success'):
            await handler.send(
                f"❌ Could not retrieve activities for **{member_name}**"
            )
            return
        
        activities = activities_result.get('activities', [])
        
        if not activities:
            await handler.send(
                f"❌ No activities found for **{member_name}**"
            )
            return
        
        # Find the activity to remove
        activity_to_remove = None
        
        if activity_type:
            # Find most recent activity of this type
            for activity in activities:
                if activity['activity_type'] == activity_type:
                    activity_to_remove = activity
                    break
        else:
            # If no activity type specified, remove the most recent
            activity_to_remove = activities[0]
            activity_type = activity_to_remove['activity_type']
        
        if not activity_to_remove:
            await handler.send(
                f"❌ Could not find {f'**{activity_type}** activity' if activity_type else 'an activity'} for **{member_name}**"
            )
            return
        
        # Remove the activity
        try:
            result = await tf_api.remove_activity(
                activity_id=activity_to_remove['id'],
                discord_user_id=str(handler.user.id)
            )
            
            if result.get('success'):
                activity = result.get('activity', {})
                points = activity.get('points', 0)
                activity_type = activity.get('type', activity_type)
                
                # Format points (remove .0 if integer)
                points_str = f"{int(points)}" if isinstance(points, (int, float)) and points == int(points) else f"{points}"
                
                # Get quota progress information
                quota_progress = result.get('quota_progress', {})
                total_points = quota_progress.get('total_points', 0)
                quota = quota_progress.get('quota', 0)
                
                # Format total_points and quota (remove .0 if integer)
                total_str = f"{int(total_points)}" if isinstance(total_points, (int, float)) and total_points == int(total_points) else f"{total_points}"
                quota_str = f"{int(quota)}" if isinstance(quota, (int, float)) and quota == int(quota) else f"{quota}"
                
                await handler.send(
                    f"✅ Removed {activity_type} ({points_str} pts) from **{member_name}**, they now have {total_str}/{quota_str} points."
                )
            else:
                await handler.send(
                    f"❌ Failed to remove activity: {result.get('message', 'Unknown API error')}"
                )
        except Exception as e:
            await handler.send(f"❌ Error removing activity: {str(e)}")
            print(f"Full result: {locals().get('result', 'No result')}")

# Setup function for adding the cog to your bot
async def setup(bot):
    await bot.add_cog(TFSystemCog(bot))


# Example: Add this to your main bot file
"""
# In your main bot.py file:

import discord
from discord.ext import commands
import os
from dotenv import load_dotenv

load_dotenv()

# Create bot
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f'Bot is ready! Logged in as {bot.user}')
    # Sync commands
    await bot.tree.sync()

# Load TF System cog
async def main():
    async with bot:
        await bot.load_extension('tf_commands')  # Load this file
        await bot.start(os.getenv('DISCORD_TOKEN'))

if __name__ == '__main__':
    import asyncio
    asyncio.run(main())
"""

