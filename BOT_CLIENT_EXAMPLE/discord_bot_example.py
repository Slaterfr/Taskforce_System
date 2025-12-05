"""
Example Discord Bot Commands for TF System Integration
This shows how to integrate the TF API client with discord.py and Groq AI

IMPORTANT: This is example code to help you integrate. Copy these patterns into your bot.
"""

import discord
from discord.ext import commands
from discord import app_commands
import os
from groq import Groq
import json
import asyncio

# Import the TF API client
from tf_api_client import TFSystemAPI

# Initialize Groq client
groq_client = Groq(api_key=os.getenv('GROQ_API_KEY'))

# Initialize TF System API
tf_api = TFSystemAPI(
    api_url=os.getenv('TF_SYSTEM_API_URL'),
    api_key=os.getenv('TF_SYSTEM_API_KEY')
)

# Define allowed roles (Commander, Marshal, General)
ALLOWED_ROLES = ['Commander', 'Marshal', 'General']


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
        
        return has_permission
    
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

Valid ranks: Aspirant, Novice, Adept, Crusader, Paladin, Exemplar, Prospect, Commander, Marshal, General, Chief General
Valid activity types: Raid, Patrol, Training, Mission, Tryout

Respond ONLY with a JSON object in this format:
{
  "action": "action_name",
  "parameters": {
    "member_name": "extracted name",
    "new_rank": "rank name",
    "activity_type": "activity type",
    etc.
  },
  "confidence": 0.0-1.0
}

If you can't parse the command, set action to "unknown" and explain in a "reason" field."""

    try:
        completion = groq_client.chat.completions.create(
            model="llama-3.1-70b-versatile",  # Use appropriate Groq model
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
        print(f"Error parsing intent with Groq: {e}")
        return {
            "action": "unknown",
            "reason": f"Failed to parse command: {str(e)}",
            "confidence": 0.0
        }


class TFSystemCog(commands.Cog):
    """Cog for TF System management commands"""
    
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(name="tf", description="Natural language TF management command")
    @has_tf_permissions()
    async def tf_command(self, interaction: discord.Interaction, command: str):
        """
        Main TF management command that accepts natural language
        
        Examples:
            /tf change João's rank to Commander
            /tf show all members with rank Paladin
            /tf add member Mike with rank Aspirant
            /tf what is Sarah's rank?
        """
        await interaction.response.defer()  # Processing may take a moment
        
        try:
            # Parse intent using Groq
            intent = await parse_intent_with_groq(command)
            
            if intent['action'] == 'unknown':
                await interaction.followup.send(
                    f"❌ I couldn't understand that command.\n"
                    f"Reason: {intent.get('reason', 'Unknown error')}\n\n"
                    f"Try something like:\n"
                    f"- Change João's rank to Commander\n"
                    f"- Show all Paladins\n"
                    f"- What rank is Sarah?"
                )
                return
            
            # Execute based on action
            if intent['action'] == 'change_rank':
                await self._handle_change_rank(interaction, intent['parameters'])
            
            elif intent['action'] == 'get_member_info':
                await self._handle_get_member_info(interaction, intent['parameters'])
            
            elif intent['action'] == 'list_members':
                await self._handle_list_members(interaction, intent['parameters'])
            
            elif intent['action'] == 'add_member':
                await self._handle_add_member(interaction, intent['parameters'])
            
            elif intent['action'] == 'remove_member':
                await self._handle_remove_member(interaction, intent['parameters'])
            
            elif intent['action'] == 'log_activity':
                await self._handle_log_activity(interaction, intent['parameters'])
            
            else:
                await interaction.followup.send(
                    f"❌ Unknown action: {intent['action']}"
                )
        
        except Exception as e:
            print(f"Error executing TF command: {e}")
            await interaction.followup.send(
                f"❌ An error occurred: {str(e)}"
            )
    
    async def _handle_change_rank(self, interaction: discord.Interaction, params: dict):
        """Handle rank change requests"""
        member_name = params.get('member_name')
        new_rank = params.get('new_rank')
        
        if not member_name or not new_rank:
            await interaction.followup.send(
                "❌ I need both a member name and a new rank."
            )
            return
        
        # Call API to change rank
        result = await tf_api.change_rank_by_name(
            member_name=member_name,
            new_rank=new_rank,
            reason=f"Promoted via Discord by {interaction.user.name}",
            discord_user_id=str(interaction.user.id)
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
            embed.set_footer(text=f"Changed by {interaction.user.name}")
            
            await interaction.followup.send(embed=embed)
        else:
            await interaction.followup.send(
                f"❌ Failed to change rank: {result.get('message', 'Unknown error')}"
            )
    
    async def _handle_get_member_info(self, interaction: discord.Interaction, params: dict):
        """Handle member info requests"""
        member_name = params.get('member_name')
        
        if not member_name:
            await interaction.followup.send("❌ I need a member name.")
            return
        
        # Search for member
        member = await tf_api.find_member_by_name(member_name)
        
        if not member:
            await interaction.followup.send(
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
            embed.add_field(name="Join Date", 
                          value=member_data.get('join_date', 'Unknown')[:10] if member_data.get('join_date') else 'Unknown',
                          inline=True)
            
            # Add recent activities
            if member_data.get('recent_activities'):
                activities_text = "\n".join([
                    f"• {a['type']} ({a['points']} pts) - {a['date'][:10] if a.get('date') else 'N/A'}"
                    for a in member_data['recent_activities'][:5]
                ])
                embed.add_field(name="Recent Activities", value=activities_text or "None", inline=False)
            
            await interaction.followup.send(embed=embed)
        else:
            await interaction.followup.send(
                f"❌ Failed to get member info: {detailed_info.get('message')}"
            )
    
    async def _handle_list_members(self, interaction: discord.Interaction, params: dict):
        """Handle list members requests"""
        rank_filter = params.get('rank')
        
        # Get members
        result = await tf_api.get_members(rank=rank_filter)
        
        if result.get('success'):
            members = result['members']
            
            if not members:
                await interaction.followup.send(
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
            
            await interaction.followup.send(embed=embed)
        else:
            await interaction.followup.send(
                f"❌ Failed to get members: {result.get('message')}"
            )
    
    async def _handle_add_member(self, interaction: discord.Interaction, params: dict):
        """Handle add member requests"""
        discord_username = params.get('discord_username')
        roblox_username = params.get('roblox_username')
        rank = params.get('rank', 'Aspirant')
        
        if not discord_username:
            await interaction.followup.send("❌ I need a Discord username.")
            return
        
        # Add member
        result = await tf_api.add_member(
            discord_username=discord_username,
            roblox_username=roblox_username,
            current_rank=rank,
            discord_user_id=str(interaction.user.id)
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
            embed.set_footer(text=f"Added by {interaction.user.name}")
            
            await interaction.followup.send(embed=embed)
        else:
            await interaction.followup.send(
                f"❌ Failed to add member: {result.get('message')}"
            )
    
    async def _handle_remove_member(self, interaction: discord.Interaction, params: dict):
        """Handle remove member requests"""
        member_name = params.get('member_name')
        
        if not member_name:
            await interaction.followup.send("❌ I need a member name.")
            return
        
        # Find member first
        member = await tf_api.find_member_by_name(member_name)
        
        if not member:
            await interaction.followup.send(
                f"❌ Could not find member **{member_name}**"
            )
            return
        
        # Confirm removal
        # (In production, you might want to add a confirmation button)
        
        # Remove member
        result = await tf_api.remove_member(
            member_id=member['id'],
            discord_user_id=str(interaction.user.id)
        )
        
        if result.get('success'):
            await interaction.followup.send(
                f"✅ Successfully removed **{member_name}** from the system."
            )
        else:
            await interaction.followup.send(
                f"❌ Failed to remove member: {result.get('message')}"
            )
    
    async def _handle_log_activity(self, interaction: discord.Interaction, params: dict):
        """Handle log activity requests"""
        member_name = params.get('member_name')
        activity_type = params.get('activity_type')
        description = params.get('description')
        
        if not member_name or not activity_type:
            await interaction.followup.send(
                "❌ I need both a member name and an activity type."
            )
            return
        
        # Find member
        member = await tf_api.find_member_by_name(member_name)
        
        if not member:
            await interaction.followup.send(
                f"❌ Could not find member **{member_name}**"
            )
            return
        
        # Log activity
        result = await tf_api.log_activity(
            member_id=member['id'],
            activity_type=activity_type,
            description=description or f"{activity_type} logged via Discord",
            discord_user_id=str(interaction.user.id)
        )
        
        if result.get('success'):
            activity = result['activity']
            await interaction.followup.send(
                f"✅ Logged **{activity_type}** ({activity['points']} points) for **{member_name}**"
            )
        else:
            await interaction.followup.send(
                f"❌ Failed to log activity: {result.get('message')}"
            )


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
