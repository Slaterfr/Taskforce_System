"""
Roblox API integration for Taskforce Management System
Handles fetching group members and their ranks from Roblox
"""

import requests
import time
from typing import List, Dict, Optional
from dataclasses import dataclass

@dataclass
class RobloxMember:
    """Represents a member from Roblox group"""
    user_id: int
    username: str
    display_name: str
    role_id: int
    role_name: str
    joined_date: str

class RobloxAPI:
    """Handles all Roblox API interactions"""
    
    def __init__(self, group_id: int):
        self.group_id = group_id
        self.base_url = "https://groups.roblox.com/v1"
        self.users_url = "https://users.roblox.com/v1"
        
        # Rate limiting
        self.last_request = 0
        self.min_delay = 0.1  # 100ms between requests
        
    def _make_request(self, url: str, params: Dict = None) -> Optional[Dict]:
        """Make a rate-limited request to Roblox API"""
        
        # Rate limiting
        time_since_last = time.time() - self.last_request
        if time_since_last < self.min_delay:
            time.sleep(self.min_delay - time_since_last)
        
        try:
            response = requests.get(url, params=params, timeout=10)
            self.last_request = time.time()
            
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 429:  # Rate limited
                print("⚠️  Rate limited by Roblox API, waiting 60 seconds...")
                time.sleep(60)
                return self._make_request(url, params)  # Retry
            else:
                print(f"❌ API request failed: {response.status_code}")
                return None
                
        except requests.exceptions.RequestException as e:
            print(f"❌ Request error: {e}")
            return None
    
    def get_group_info(self) -> Optional[Dict]:
        """Get basic group information"""
        url = f"{self.base_url}/groups/{self.group_id}"
        return self._make_request(url)
    
    def get_group_roles(self) -> List[Dict]:
        """Get all roles in the group"""
        url = f"{self.base_url}/groups/{self.group_id}/roles"
        data = self._make_request(url)
        return data.get('roles', []) if data else []
    
    def get_group_members(self, limit: int = 10000) -> List[RobloxMember]:
        """
        Get all members in the group
        Note: This might take a while for large groups due to pagination
        """
        members = []
        cursor = ""
        page_count = 0
        
        print(f"🔄 Fetching members from Roblox group {self.group_id}...")
        
        while True:
            page_count += 1
            url = f"{self.base_url}/groups/{self.group_id}/users"
            params = {
                'limit': 100,  # Max 100 per request (Roblox limit)
                'sortOrder': 'Asc'
            }
            
            if cursor:
                params['cursor'] = cursor
            
            print(f"📄 Fetching page {page_count}...")
            data = self._make_request(url, params)
            
            if not data:
                print(f"❌ Failed to fetch page {page_count}")
                break
                
            # Process members from this page
            page_members = data.get('data', [])
            if not page_members:
                print(f"📄 Page {page_count} has no members, stopping")
                break
                
            for member_data in page_members:
                member = RobloxMember(
                    user_id=member_data['user']['userId'],
                    username=member_data['user']['username'], 
                    display_name=member_data['user']['displayName'],
                    role_id=member_data['role']['id'],
                    role_name=member_data['role']['name'],
                    joined_date=member_data.get('joinTime', '')
                )
                members.append(member)
            
            print(f"📥 Fetched {len(page_members)} members from page {page_count} (Total: {len(members)})")
            
            # Check if there are more pages
            cursor = data.get('nextPageCursor')
            if not cursor:
                print(f"📄 No more pages, finished at page {page_count}")
                break
                
            # Don't fetch too many at once (safety limit)
            if len(members) >= limit:
                print(f"⚠️  Reached limit of {limit} members")
                break
            
            # Small delay between pages to be nice to the API
            time.sleep(0.5)
        
        print(f"✅ Retrieved {len(members)} total members from {page_count} pages")
        return members
    
    def get_user_by_username(self, username: str) -> Optional[Dict]:
        """Get user info by username"""
        url = f"{self.users_url}/usernames/users"
        payload = {
            "usernames": [username],
            "excludeBannedUsers": True
        }
        
        try:
            response = requests.post(url, json=payload, timeout=10)
            self.last_request = time.time()
            
            if response.status_code == 200:
                data = response.json()
                users = data.get('data', [])
                return users[0] if users else None
            
        except requests.exceptions.RequestException as e:
            print(f"❌ Error fetching user {username}: {e}")
        
        return None
    
    def test_connection(self) -> bool:
        """Test if we can connect to the Roblox API and fetch group info"""
        print(f"🔍 Testing connection to Roblox group {self.group_id}...")
        
        group_info = self.get_group_info()
        if group_info:
            print(f"✅ Connected to group: {group_info.get('name', 'Unknown')}")
            print(f"📊 Group has {group_info.get('memberCount', 0)} members")
            return True
        else:
            print(f"❌ Failed to connect to group {self.group_id}")
            print("💡 Make sure the group ID is correct and the group is public")
            return False

# Rank mapping - customize this for your specific group
RANK_MAPPING = {
    # Roblox role name -> Your system rank name
    "Aspirant": "Aspirant",
    "Novice": "Novice", 
    "Adept": "Adept",
    "Crusader": "Crusader",
    "Paladin": "Paladin",
    "Exemplar": "Exemplar",
    "Prospect": "Prospect",
    "Commander": "Commander",
    "Marshall": "Marshall",
    "General": "General",
    "Chief General": "Chief General",
    
    # Common Roblox default roles (in case they exist)
    "Guest": "Aspirant",
    "Member": "Novice"
}

def map_roblox_rank_to_system(roblox_rank: str) -> str:
    """Convert Roblox rank to your internal system rank"""
    return RANK_MAPPING.get(roblox_rank, roblox_rank)