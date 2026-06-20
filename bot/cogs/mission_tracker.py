"""
Discord Bot Cog for Mission Completion Tracking

Automatically detects mission posts and tracks completions when the "Passed:" field is edited.
Uses HTTP API calls to communicate with Flask backend instead of direct database access.
"""

import discord
from discord.ext import commands
import re
from datetime import datetime
from typing import List, Optional
import os
import requests
import logging

# Setup logging
logger = logging.getLogger('MissionTracker')
logger.setLevel(logging.DEBUG)

if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

# Environment variables
TF_SYSTEM_API_URL = os.getenv('TF_SYSTEM_API_URL', 'http://localhost:5000/api/v1')
TF_SYSTEM_API_KEY = os.getenv('TF_SYSTEM_API_KEY', '')
MISSION_CHANNEL_ID = int(os.getenv('MISSION_CHANNEL_ID', '1446175728025735393'))


class MissionTracker(commands.Cog):
    """Cog for tracking mission completions from Discord messages via HTTP API"""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.mission_channel_id = MISSION_CHANNEL_ID
        self.api_url = TF_SYSTEM_API_URL.rstrip('/')
        
        # Validate configuration
        if not TF_SYSTEM_API_KEY:
            logger.warning("[MissionTracker] ⚠️ TF_SYSTEM_API_KEY not set! API calls will fail.")
        if not self.api_url or 'localhost' not in self.api_url and 'http' not in self.api_url:
            logger.warning("[MissionTracker] ⚠️ Using default TF_SYSTEM_API_URL. Update if needed.")
        
        logger.info(f"[MissionTracker] ✅ Initialized with mission channel: {self.mission_channel_id}")
        logger.info(f"[MissionTracker] 🔗 API URL: {self.api_url}")
    
    def _get_headers(self) -> dict:
        """Get authorization headers for API requests"""
        return {
            'Authorization': f'Bearer {TF_SYSTEM_API_KEY}',
            'Content-Type': 'application/json'
        }
    
    @commands.hybrid_command(name="sync_missions", description="Sync mission completions from a date range")
    @commands.has_role(729817672585314305)
    async def sync_missions(self, ctx, month: Optional[int] = None, year: Optional[int] = None):
        """
        Sync mission completions from the start of a specified month.
        
        Usage:
        /sync_missions - Syncs current month
        /sync_missions 5 2026 - Syncs May 2026
        """
        try:
            # Default to current month/year
            now = datetime.now()
            if month is None:
                month = now.month
            if year is None:
                year = now.year
            
            # Validate month
            if not 1 <= month <= 12:
                await ctx.send("❌ Invalid month. Use 1-12.")
                return
            
            # Create start date (first day of month)
            start_date = datetime(year, month, 1)
            
            # Show progress
            print(f"\n🔄 [SYNC MISSIONS]")
            print(f"   ├─ Start Date: {start_date.strftime('%B %d, %Y')}")
            print(f"   ├─ Scanning mission channel...")
            
            await ctx.send(f"🔄 Syncing missions from {start_date.strftime('%B %Y')}... (this may take a moment)")
            
            # Get the mission channel
            channel = self.bot.get_channel(self.mission_channel_id)
            if not channel:
                await ctx.send("❌ Mission channel not found!")
                return
            
            # Fetch all messages from start of month onwards
            synced_count = 0
            error_count = 0
            
            async for message in channel.history(after=start_date, oldest_first=True):
                # Parse mission from message
                mission_data = self._parse_mission_message(message.content)
                if not mission_data:
                    continue
                
                # Extract current passed usernames
                passed_usernames = self._extract_passed_usernames(message.content)
                
                if not passed_usernames:
                    continue
                
                # Try to log completions
                try:
                    await self._sync_mission_completions(
                        message.id,
                        passed_usernames,
                        message.author
                    )
                    synced_count += 1
                except Exception as e:
                    error_count += 1
                    logger.error(f"[MissionTracker] Error syncing mission {message.id}: {e}")
            
            # Report results
            print(f"   ├─ ✅ Synced: {synced_count}")
            print(f"   └─ ❌ Errors: {error_count}\n")
            
            await ctx.send(f"✅ Sync complete! Processed {synced_count} missions (Errors: {error_count})")
            
        except ValueError:
            await ctx.send("❌ Invalid date format. Use: `/sync_missions [month] [year]`")
        except Exception as e:
            logger.error(f"[MissionTracker] Sync error: {e}")
            await ctx.send(f"❌ Sync error: {e}")
    
    async def _sync_mission_completions(self, message_id: int, current_passed: List[str], message_author: discord.Member):
        """
        Sync mission completions for a message.
        Compares current passed list with what's in the database.
        """
        try:
            # Get mission by message ID
            response = requests.get(
                f'{self.api_url}/missions/by-message/{message_id}',
                headers=self._get_headers(),
                timeout=10
            )
            
            if response.status_code == 404:
                # Mission doesn't exist yet, skip
                return
            
            if response.status_code != 200:
                logger.error(f"[MissionTracker] Failed to fetch mission: {response.status_code}")
                return
            
            mission_data = response.json()
            mission_id = mission_data['id']
            
            # Prepare payload with all current passed members
            payload = {
                'mission_id': mission_id,
                'verified_by_username': message_author.name,
                'completers': [
                    {'member_username': username, 'discord_username': username}
                    for username in current_passed
                ]
            }
            
            # Send to API
            response = requests.post(
                f'{self.api_url}/missions/completions',
                json=payload,
                headers=self._get_headers(),
                timeout=10
            )
            
            if response.status_code != 200:
                logger.error(f"[MissionTracker] Failed to sync completions: {response.status_code}")
        
        except Exception as e:
            logger.error(f"[MissionTracker] Error syncing: {e}")
    
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Listen for mission posts in the designated channel"""
        # Ignore bot messages
        if message.author.bot:
            return
        
        # Only process in mission channel
        if message.channel.id != self.mission_channel_id:
            return
        
        logger.debug(f"[MissionTracker] 📨 Message received in mission channel from {message.author.name}")
        print(f"\n🔔 [MESSAGE DETECTED]")
        print(f"   ├─ Author: {message.author.name}#{message.author.discriminator}")
        print(f"   ├─ Channel: {message.channel.name if hasattr(message.channel, 'name') else 'DM'}")
        print(f"   ├─ Message ID: {message.id}")
        content_preview = message.content[:100] + "..." if len(message.content) > 100 else message.content
        print(f"   └─ Content: {content_preview}")
        
        # Try to parse mission from message
        mission_data = self._parse_mission_message(message.content)
        if mission_data:
            logger.info(f"[MissionTracker] 🔍 Mission parsed: {mission_data.get('title')}")
            print(f"   ✓ Mission format detected!\n")
            await self._create_mission_from_message(message, mission_data)
        else:
            print(f"   ✗ Not a mission format\n")
            logger.debug(f"[MissionTracker] ⏭️ Message doesn't match mission format")
    
    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        """Listen for edits in the mission channel to detect completions"""
        # Ignore bot messages
        if after.author.bot:
            return
        
        # Only process in mission channel
        if after.channel.id != self.mission_channel_id:
            return
        
        # Log all edits for visibility
        logger.debug(f"[MissionTracker] 📝 Message edit detected in mission channel from {after.author.name}")
        print(f"\n📝 [MESSAGE EDIT DETECTED] from {after.author.name}#{after.author.discriminator}")
        
        # Extract passed usernames from before and after
        before_passed = self._extract_passed_usernames(before.content)
        after_passed = self._extract_passed_usernames(after.content)
        
        print(f"   ├─ Before Passed: {before_passed if before_passed else 'None'}")
        print(f"   └─ After Passed: {after_passed if after_passed else 'None'}")
        
        # Find new and removed completers
        new_completers = set(after_passed) - set(before_passed)
        deleted_completers = set(before_passed) - set(after_passed)
        
        print(f"   ├─ New: {list(new_completers) if new_completers else 'None'}")
        print(f"   └─ Removed: {list(deleted_completers) if deleted_completers else 'None'}")
        
        if not new_completers and not deleted_completers:
            print(f"   ℹ️ No changes in Passed field detected\n")
            return
        
        if new_completers or deleted_completers:
            logger.info(f"[MissionTracker] ✏️ Mission edited: {len(new_completers)} added, {len(deleted_completers)} removed")
            print(f"✏️ [PASSED FIELD CHANGED]")
            print(f"   ├─ Author: {after.author.name}#{after.author.discriminator}")
            print(f"   ├─ Verifier: {after.author.name}")
            if new_completers:
                print(f"   ├─ ✅ Passed - New Members ({len(new_completers)}):")
                for member in new_completers:
                    print(f"   │  └─ {member}")
            if deleted_completers:
                print(f"   ├─ ❌ Removed Members ({len(deleted_completers)}):")
                for member in deleted_completers:
                    print(f"   │  └─ {member}")
            print(f"   └─ Message ID: {after.id}\n")
            await self._log_mission_completions(
                after.id, 
                new_completers, 
                deleted_completers, 
                after.author
            )
    
    def _parse_mission_message(self, content: str) -> Optional[dict]:
        """
        Parse mission message to extract title, stars (difficulty), expiration, and coords.
        
        Flexible format:
        - Title: First line with # prefix OR first non-empty, non-mention line
        - Difficulty: ⭐⭐⭐ (required - identifies missions)
        - Expiration Date: Optional (Month Day, Year format)
        - Planet Coordinates: Optional (URL link)
        """
        lines = content.split('\n')
        data = {}
        
        # Extract title - prefer line with # prefix, fall back to first non-empty, non-mention line
        for line in lines:
            if line.startswith('# '):
                data['title'] = line[2:].strip()
                break
        
        # If no # prefix found, use first non-empty, non-mention line as title
        if 'title' not in data:
            for line in lines:
                stripped = line.strip()
                # Skip empty lines, @ mentions, and field headers
                if (stripped and 
                    not stripped.startswith('@') and 
                    not any(keyword in line for keyword in ['Objective:', 'Difficulty:', 'Expiration', 'Passed:', 'Coordinates:'])):
                    data['title'] = stripped
                    break
        
        if 'title' not in data or not data['title']:
            return None
        
        # Extract difficulty/stars (required - this identifies a mission)
        for line in lines:
            if 'Difficulty:' in line or '⭐' in line:
                stars_str = line.split(':', 1)[-1].strip() if ':' in line else line
                # Count ⭐ emojis
                stars = stars_str.count('⭐')
                if stars > 0:
                    data['stars'] = stars
                    data['difficulty'] = stars_str
                    break
        
        if 'stars' not in data:
            return None  # Must have stars - this is what identifies a mission
        
        # Extract expiration date (optional)
        for line in lines:
            if 'Expiration' in line:
                expiration_text = line.split(':', 1)[1].strip() if ':' in line else ''
                try:
                    expiration_dt = self._parse_date(expiration_text)
                    if expiration_dt:
                        data['expiration_date'] = expiration_dt.strftime('%Y-%m-%d')
                except:
                    pass
                break
        
        # Extract Planet Coordinates (optional)
        for line in lines:
            if 'Planet Coordinates:' in line or 'Coordinates:' in line:
                coords = line.split(':', 1)[1].strip() if ':' in line else ''
                if coords:
                    data['planet_coordinates'] = coords
                break
        
        # Extract description (optional)
        description_lines = []
        in_description = False
        for line in lines:
            if line.startswith('# ') or (not in_description and line.strip() == data.get('title')):
                in_description = True
                continue
            if any(keyword in line for keyword in ['Objective:', 'Difficulty:', 'Expiration', 'Passed:', 'Coordinates:']):
                break
            if in_description and line.strip():
                description_lines.append(line.strip())
        
        if description_lines:
            data['description'] = '\n'.join(description_lines)
        
        return data
    
    def _extract_passed_usernames(self, content: str) -> List[str]:
        """
        Extract usernames from the "Passed:" field.
        Uses the LAST occurrence of "Passed:" to avoid duplicates in the message.
        Supports formats:
        - Passed: Username (same line)
        - Passed: (next line has Username)
        - @Role Username | @Role Username
        - Username, Username
        - Mixed format
        """
        # Find the LAST Passed: line (to avoid duplicates in message)
        passed_line = None
        lines = content.split('\n')
        
        # Iterate backwards to find the last occurrence
        for i in range(len(lines) - 1, -1, -1):
            line = lines[i]
            if line.startswith('Passed:'):
                # Try to get content from same line first
                passed_line = line.split(':', 1)[1].strip()
                
                # If nothing on same line, check next line
                if not passed_line and i + 1 < len(lines):
                    passed_line = lines[i + 1].strip()
                
                break
        
        if not passed_line or passed_line == '':
            return []
        
        usernames = []
        
        # Split by pipe | for mention format
        if '|' in passed_line:
            parts = passed_line.split('|')
            for part in parts:
                part = part.strip()
                # Remove @Role prefix if present
                match = re.search(r'@\w+\s+(.+)', part)
                if match:
                    username = match.group(1).strip()
                else:
                    username = part
                if username:
                    usernames.append(username)
        
        # Split by comma for comma-separated format
        elif ',' in passed_line:
            parts = passed_line.split(',')
            for part in parts:
                username = part.strip()
                if username:
                    usernames.append(username)
        
        # Single username without separators
        else:
            # Remove @Role prefix if present
            match = re.search(r'@\w+\s+(.+)', passed_line)
            if match:
                username = match.group(1).strip()
            else:
                username = passed_line
            if username:
                usernames.append(username)
        
        return [u for u in usernames if u]  # Filter empty strings
    
    async def _create_mission_from_message(self, message: discord.Message, mission_data: dict):
        """Create a Mission record via HTTP API"""
        try:
            payload = {
                'discord_message_id': str(message.id),
                'title': mission_data.get('title'),
                'stars': mission_data.get('stars', 1),
                'difficulty': mission_data.get('difficulty'),
                'expiration_date': mission_data.get('expiration_date'),
                'planet_coordinates': mission_data.get('planet_coordinates'),
                'created_by_username': message.author.name,
                'description': mission_data.get('description')
            }
            
            print(f"\n📋 [MISSION REGISTRATION]")
            print(f"   ├─ Title: {mission_data.get('title')}")
            print(f"   ├─ Difficulty: {mission_data.get('stars')} ⭐")
            print(f"   ├─ Created by: {message.author.name}#{message.author.discriminator}")
            if mission_data.get('expiration_date'):
                print(f"   ├─ Expires: {mission_data.get('expiration_date')}")
            if mission_data.get('planet_coordinates'):
                print(f"   ├─ Coordinates: {mission_data.get('planet_coordinates')}")
            if mission_data.get('description'):
                desc = mission_data.get('description', '')
                desc_preview = desc[:60] + "..." if len(desc) > 60 else desc
                print(f"   ├─ Description: {desc_preview}")
            print(f"   └─ Message ID: {message.id}")
            
            response = requests.post(
                f'{self.api_url}/missions',
                json=payload,
                headers=self._get_headers(),
                timeout=10
            )
            
            if response.status_code == 201:
                result = response.json()
                print(f"   ✅ SUCCESSFULLY REGISTERED IN DATABASE\n")
                logger.info(f"[MissionTracker] ✅ Created mission: {mission_data.get('title')} (Stars: {mission_data.get('stars')})")
            elif response.status_code == 409:
                print(f"   ℹ️ Mission already exists in database\n")
                logger.info(f"[MissionTracker] ℹ️ Mission already exists (message ID: {message.id})")
            else:
                print(f"   ❌ Failed to register: {response.status_code}\n")
                logger.error(f"[MissionTracker] ❌ Failed to create mission: {response.status_code} - {response.text}")
        
        except requests.exceptions.Timeout:
            print(f"   ❌ API request timeout - is the Flask app running?\n")
            logger.error("[MissionTracker] ❌ API request timeout - is the Flask app running?")
        except requests.exceptions.ConnectionError:
            print(f"   ❌ Connection error - cannot reach {self.api_url}\n")
            logger.error(f"[MissionTracker] ❌ Connection error - cannot reach {self.api_url}")
        except Exception as e:
            print(f"   ❌ Error creating mission: {e}\n")
            logger.error(f"[MissionTracker] ❌ Error creating mission: {e}")
    
    async def _log_mission_completions(
        self, 
        message_id: int, 
        new_completers: set, 
        deleted_completers: set,
        message_author: discord.Member
    ):
        """
        Log mission completions via HTTP API.
        Handles both new completions and removals.
        """
        try:
            # Get mission by message ID
            print(f"\n🔍 [FETCHING MISSION]")
            print(f"   ├─ Message ID: {message_id}")
            print(f"   └─ API Call: GET {self.api_url}/missions/by-message/{message_id}")
            
            response = requests.get(
                f'{self.api_url}/missions/by-message/{message_id}',
                headers=self._get_headers(),
                timeout=10
            )
            
            print(f"   └─ Response Status: {response.status_code}")
            
            if response.status_code == 404:
                print(f"   ❌ Mission not found - API endpoint or mission doesn't exist\n")
                logger.warning(f"[MissionTracker] ⚠️ Mission not found for message {message_id}")
                return
            
            if response.status_code != 200:
                print(f"   ❌ Failed to fetch mission: {response.status_code}")
                print(f"   └─ Response: {response.text[:200]}\n")
                logger.error(f"[MissionTracker] ❌ Failed to fetch mission: {response.status_code}")
                return
            
            mission_data = response.json()
            mission_id = mission_data['id']
            mission_title = mission_data['title']
            mission_stars = mission_data['stars']
            
            print(f"   ✅ Mission found: {mission_title}\n")
            
            # Prepare payload
            payload = {
                'mission_id': mission_id,
                'verified_by_username': message_author.name
            }
            
            if new_completers:
                payload['completers'] = [
                    {'member_username': username, 'discord_username': username}
                    for username in new_completers
                ]
            
            if deleted_completers:
                payload['deleted_completers'] = list(deleted_completers)
            
            # Send to API
            print(f"📤 [LOGGING COMPLETION]")
            print(f"   ├─ API Call: POST {self.api_url}/missions/completions")
            print(f"   ├─ Mission ID: {mission_id}")
            print(f"   ├─ New Members: {len(new_completers)}")
            print(f"   ├─ Removed Members: {len(deleted_completers)}")
            
            response = requests.post(
                f'{self.api_url}/missions/completions',
                json=payload,
                headers=self._get_headers(),
                timeout=10
            )
            
            print(f"   └─ Response Status: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                stats = result.get('stats', {})
                print(f"\n✅ [MISSION COMPLETION LOGGED]")
                print(f"   ├─ Mission: {mission_title}")
                print(f"   ├─ Difficulty: {mission_stars} ⭐")
                print(f"   ├─ Members Added: {stats.get('added', 0)}")
                print(f"   ├─ Members Removed: {stats.get('deleted', 0)}")
                print(f"   └─ Verified by: {message_author.name}#{message_author.discriminator}\n")
                logger.info(
                    f"[MissionTracker] ✅ {mission_title}: "
                    f"+{stats.get('added', 0)} added, -{stats.get('deleted', 0)} deleted"
                )
            else:
                print(f"   ❌ Failed to log completions: {response.status_code}")
                print(f"   └─ Response: {response.text[:200]}\n")
                logger.error(f"[MissionTracker] ❌ Failed to log completions: {response.status_code}")
        
        except requests.exceptions.Timeout:
            print(f"   ❌ API request timeout\n")
            logger.error("[MissionTracker] ❌ API request timeout")
        except requests.exceptions.ConnectionError:
            print(f"   ❌ Connection error - cannot reach {self.api_url}\n")
            logger.error(f"[MissionTracker] ❌ Connection error - cannot reach {self.api_url}")
        except Exception as e:
            print(f"   ❌ Error logging completions: {e}\n")
            logger.error(f"[MissionTracker] ❌ Error logging completions: {e}")
    
    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """Parse date string like "May 11th, 2026" to datetime"""
        try:
            # Remove ordinal suffix (st, nd, rd, th)
            date_str_clean = re.sub(r'(\d+)(st|nd|rd|th)', r'\1', date_str)
            
            # Try parsing with various formats
            formats = [
                '%B %d, %Y',  # May 11, 2026
                '%b %d, %Y',  # May 11, 2026
                '%B %d %Y',   # May 11 2026
                '%b %d %Y',   # May 11 2026
            ]
            
            for fmt in formats:
                try:
                    return datetime.strptime(date_str_clean, fmt)
                except ValueError:
                    continue
            
            return None
        except:
            return None


async def setup(bot: commands.Bot):
    """Setup function for loading this cog"""
    await bot.add_cog(MissionTracker(bot))
    logger.info("[MissionTracker] ✅ Cog loaded successfully")
