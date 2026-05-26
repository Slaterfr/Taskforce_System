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
MISSION_CHANNEL_ID = int(os.getenv('MISSION_CHANNEL_ID', '729821327984164964'))


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
        
        # Try to parse mission from message
        mission_data = self._parse_mission_message(message.content)
        if mission_data:
            logger.info(f"[MissionTracker] 🔍 Mission parsed: {mission_data.get('title')}")
            await self._create_mission_from_message(message, mission_data)
        else:
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
        
        # Extract passed usernames from before and after
        before_passed = self._extract_passed_usernames(before.content)
        after_passed = self._extract_passed_usernames(after.content)
        
        # Find new and removed completers
        new_completers = set(after_passed) - set(before_passed)
        deleted_completers = set(before_passed) - set(after_passed)
        
        if new_completers or deleted_completers:
            logger.info(f"[MissionTracker] ✏️ Mission edited: {len(new_completers)} added, {len(deleted_completers)} removed")
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
        Supports formats:
        - @Role Username | @Role Username
        - Username, Username
        - Mixed format
        """
        # Find the Passed: line
        passed_line = None
        for line in content.split('\n'):
            if line.startswith('Passed:'):
                passed_line = line.split(':', 1)[1].strip()
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
            
            response = requests.post(
                f'{self.api_url}/missions',
                json=payload,
                headers=self._get_headers(),
                timeout=10
            )
            
            if response.status_code == 201:
                result = response.json()
                logger.info(f"[MissionTracker] ✅ Created mission: {mission_data.get('title')} (Stars: {mission_data.get('stars')})")
            elif response.status_code == 409:
                logger.info(f"[MissionTracker] ℹ️ Mission already exists (message ID: {message.id})")
            else:
                logger.error(f"[MissionTracker] ❌ Failed to create mission: {response.status_code} - {response.text}")
        
        except requests.exceptions.Timeout:
            logger.error("[MissionTracker] ❌ API request timeout - is the Flask app running?")
        except requests.exceptions.ConnectionError:
            logger.error(f"[MissionTracker] ❌ Connection error - cannot reach {self.api_url}")
        except Exception as e:
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
            response = requests.get(
                f'{self.api_url}/missions/by-message/{message_id}',
                headers=self._get_headers(),
                timeout=10
            )
            
            if response.status_code == 404:
                logger.warning(f"[MissionTracker] ⚠️ Mission not found for message {message_id}")
                return
            
            if response.status_code != 200:
                logger.error(f"[MissionTracker] ❌ Failed to fetch mission: {response.status_code}")
                return
            
            mission_data = response.json()
            mission_id = mission_data['id']
            mission_title = mission_data['title']
            mission_stars = mission_data['stars']
            
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
            response = requests.post(
                f'{self.api_url}/missions/completions',
                json=payload,
                headers=self._get_headers(),
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                stats = result.get('stats', {})
                logger.info(
                    f"[MissionTracker] ✅ {mission_title}: "
                    f"+{stats.get('added', 0)} added, -{stats.get('deleted', 0)} deleted"
                )
            else:
                logger.error(f"[MissionTracker] ❌ Failed to log completions: {response.status_code} - {response.text}")
        
        except requests.exceptions.Timeout:
            logger.error("[MissionTracker] ❌ API request timeout")
        except requests.exceptions.ConnectionError:
            logger.error(f"[MissionTracker] ❌ Connection error - cannot reach {self.api_url}")
        except Exception as e:
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
