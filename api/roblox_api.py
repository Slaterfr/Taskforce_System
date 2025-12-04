"""
Roblox API integration for Taskforce Management System
Handles fetching group members and their ranks from Roblox
"""

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
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
    
    def __init__(self, group_id: int, cookie: str = None):
        self.group_id = group_id
        self.base_url = "https://groups.roblox.com/v1"
        self.users_url = "https://users.roblox.com/v1"
        self.cookie = cookie  # Roblox authentication cookie for write operations
        
        # Rate limiting
        self.last_request = 0
        self.min_delay = 0.1  # 100ms between requests
        
        # Initialize session with retries
        self.session = requests.Session()
        
        # Configure robust retry strategy
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS", "POST", "PATCH", "DELETE"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)
        
    def _get_headers(self) -> Dict:
        """Get headers for authenticated requests"""
        headers = {
            'Content-Type': 'application/json',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': 'https://www.roblox.com/',
            'Origin': 'https://www.roblox.com'
        }
        return headers
    
    def _get_cookies(self) -> Dict:
        """Get cookies for authenticated requests"""
        cookies = {}
        if self.cookie:
            cookies['.ROBLOSECURITY'] = self.cookie
        return cookies
    
    def _get_csrf_token(self) -> Optional[str]:
        """Get CSRF token from Roblox (required for write operations)
        Roblox returns the CSRF token in the X-CSRF-TOKEN header when you make
        a request that requires authentication, even if it fails.
        """
        if not self.cookie:
            return None
        
        # Method 1: Try using the logout endpoint (most reliable)
        try:
            url = "https://auth.roblox.com/v2/logout"
            response = self.session.post(
                url,
                headers=self._get_headers(),
                cookies=self._get_cookies(),
                timeout=10
            )
            csrf_token = response.headers.get('X-CSRF-TOKEN')
            if csrf_token:
                return csrf_token
        except Exception as e:
            print(f"⚠️ Error getting CSRF token from logout endpoint: {e}")
        
        # Method 2: Try making a request to the groups API that would require CSRF
        try:
            # Make a PATCH request that will likely fail, but will return the CSRF token
            url = f"{self.base_url}/groups/{self.group_id}/users/1"
            response = self.session.patch(
                url,
                json={"roleId": 1},
                headers=self._get_headers(),
                cookies=self._get_cookies(),
                timeout=10
            )
            csrf_token = response.headers.get('X-CSRF-TOKEN')
            if csrf_token:
                return csrf_token
        except Exception as e:
            print(f"⚠️ Error getting CSRF token from groups API: {e}")
        
        return None
    
    def _make_request(self, url: str, method: str = 'GET', params: Dict = None, 
                     json_data: Dict = None, headers: Dict = None, retry_count: int = 0) -> Optional[Dict]:
        """Make a rate-limited request to Roblox API"""
        
        # Rate limiting
        time_since_last = time.time() - self.last_request
        if time_since_last < self.min_delay:
            time.sleep(self.min_delay - time_since_last)
        
        request_headers = self._get_headers()
        if headers:
            request_headers.update(headers)
        
        request_cookies = self._get_cookies()
        
        try:
            # Use session instead of direct requests
            response = self.session.request(
                method=method,
                url=url,
                params=params,
                json=json_data,
                headers=request_headers,
                cookies=request_cookies,
                timeout=30  # Increased timeout
            )
            
            self.last_request = time.time()
            
            if response.status_code in [200, 204]:
                if response.content:
                    return response.json()
                return {'success': True}
            elif response.status_code == 429:  # Rate limited
                if retry_count < 3:
                    print("⚠️  Rate limited by Roblox API, waiting 60 seconds...")
                    time.sleep(60)
                    return self._make_request(url, method, params, json_data, headers, retry_count + 1)
                else:
                    print("❌ Max retries reached for rate limit")
                    return None
            elif response.status_code == 401:
                print("❌ Authentication failed - check your Roblox cookie")
                return None
            elif response.status_code == 403:
                # Don't print for CSRF checks which expect failure
                if 'X-CSRF-TOKEN' not in request_headers:
                    print(f"❌ Permission denied - you may not have permission to perform this action")
                return None
            else:
                error_msg = response.text if hasattr(response, 'text') else 'Unknown error'
                print(f"❌ API request failed: {response.status_code} - {error_msg[:200]}")
                return None
                
        except (requests.exceptions.ConnectionError, requests.exceptions.ChunkedEncodingError, requests.exceptions.Timeout) as e:
            if retry_count < 3:
                wait_time = 2 * (retry_count + 1)
                print(f"⚠️  Connection error: {e}. Retrying in {wait_time}s...")
                time.sleep(wait_time)
                # Re-initialize session on connection error
                self.session = requests.Session()
                retry_strategy = Retry(
                    total=3,
                    backoff_factor=1,
                    status_forcelist=[500, 502, 503, 504],
                    allowed_methods=["HEAD", "GET", "OPTIONS", "POST", "PATCH", "DELETE"]
                )
                adapter = HTTPAdapter(max_retries=retry_strategy)
                self.session.mount("https://", adapter)
                self.session.mount("http://", adapter)
                
                return self._make_request(url, method, params, json_data, headers, retry_count + 1)
            else:
                print(f"❌ Request error after retries: {e}")
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
            data = self._make_request(url, method='GET', params=params)
            
            if not data:
                print(f"❌ Failed to fetch page {page_count}")
                break
                
            # Process members from this page
            page_members = data.get('data', [])
            if not page_members:
                print(f"📄 Page {page_count} has no members, stopping")
                break
                
            for member_data in page_members:
                # Safely extract role name
                role_data = member_data.get('role', {})
                if isinstance(role_data, dict):
                    role_name = role_data.get('name', '')
                else:
                    role_name = str(role_data) if role_data else ''
                
                # Ensure role_name is a string
                if not isinstance(role_name, str):
                    role_name = str(role_name) if role_name else ''
                
                member = RobloxMember(
                    user_id=member_data['user']['userId'],
                    username=member_data['user']['username'], 
                    display_name=member_data['user']['displayName'],
                    role_id=member_data['role']['id'],
                    role_name=role_name,
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
            # Use session
            response = self.session.post(url, json=payload, timeout=10)
            self.last_request = time.time()
            
            if response.status_code == 200:
                data = response.json()
                users = data.get('data', [])
                return users[0] if users else None
            
        except requests.exceptions.RequestException as e:
            print(f"❌ Error fetching user {username}: {e}")
        
        return None
    
    def update_member_role(self, user_id: int, role_id: int):
        """Update a member's role in the group (requires authentication)
        Returns: (success: bool, error_message: str)
        """
        if not self.cookie:
            return False, "No authentication cookie provided"
        
        # Get CSRF token first
        csrf_token = self._get_csrf_token()
        
        url = f"{self.base_url}/groups/{self.group_id}/users/{user_id}"
        payload = {
            "roleId": role_id
        }
        
        # Prepare headers with CSRF token
        headers = self._get_headers()
        if csrf_token:
            headers['X-CSRF-TOKEN'] = csrf_token
        
        # Make request and capture response details
        try:
            print(f"🔄 Attempting to update user {user_id} to role {role_id}...")
            if csrf_token:
                print(f"🔐 Using CSRF token: {csrf_token[:20]}...")
            
            # Use session
            response = self.session.patch(
                url,
                json=payload,
                headers=headers,
                cookies=self._get_cookies(),
                timeout=10
            )
            
            print(f"📡 Response status: {response.status_code}")
            if response.status_code not in [200, 204]:
                print(f"📄 Response text: {response.text[:300]}")
            
            # If we got a 403, try to get CSRF token from response and retry
            if response.status_code == 403:
                new_csrf_token = response.headers.get('X-CSRF-TOKEN')
                if new_csrf_token and new_csrf_token != csrf_token:
                    print(f"🔐 Got CSRF token from 403 response, retrying...")
                    csrf_token = new_csrf_token
                    headers['X-CSRF-TOKEN'] = csrf_token
                    response = self.session.patch(
                        url,
                        json=payload,
                        headers=headers,
                        cookies=self._get_cookies(),
                        timeout=10
                    )
                    print(f"📡 Retry response status: {response.status_code}")
            
            if response.status_code in [200, 204]:
                # Verify the update actually happened by checking the user's current role
                # Small delay to let Roblox process the change
                time.sleep(0.5)
                user_role = self.get_user_role_in_group(user_id)
                if user_role:
                    current_role_id = user_role.get('role', {}).get('id')
                    current_role_name = user_role.get('role', {}).get('name', 'Unknown')
                    print(f"✅ Verification: User's current role is {current_role_name} (ID: {current_role_id})")
                    if current_role_id == role_id:
                        return True, "Success"
                    else:
                        return False, f"Update appeared successful but role didn't change (expected role ID {role_id}, got {current_role_id})"
                # If we can't verify, assume success but log it
                print("⚠️ Could not verify role change (API returned success)")
                return True, "Success (could not verify)"
            elif response.status_code == 401:
                return False, "Authentication failed - cookie may be expired"
            elif response.status_code == 403:
                # Try to get more details from the response
                error_text = response.text
                try:
                    error_json = response.json()
                    error_msg = error_json.get('errors', [{}])[0].get('message', error_text)
                except:
                    error_msg = error_text
                
                # Log full response for debugging
                print(f"❌ Permission denied response: {response.status_code}")
                print(f"   Response text: {error_text[:500]}")
                print(f"   URL: {url}")
                print(f"   Payload: {payload}")
                
                return False, f"Permission denied: {error_msg[:200]}"
            elif response.status_code == 404:
                return False, f"User {user_id} not found in group"
            elif response.status_code == 400:
                error_text = response.text
                try:
                    error_json = response.json()
                    error_msg = error_json.get('errors', [{}])[0].get('message', error_text)
                except:
                    error_msg = error_text
                return False, f"Bad request: {error_msg[:200]}"
            else:
                error_text = response.text[:200]
                return False, f"API error {response.status_code}: {error_text}"
        except requests.exceptions.RequestException as e:
            return False, f"Request error: {str(e)}"
    
    def add_member_to_group(self, user_id: int, role_id: int) -> bool:
        """Add a user to the group with a specific role (requires authentication)"""
        if not self.cookie:
            print("❌ Cannot add member: No authentication cookie provided")
            return False
        
        # Get CSRF token first
        csrf_token = self._get_csrf_token()
        
        url = f"{self.base_url}/groups/{self.group_id}/users/{user_id}"
        payload = {
            "roleId": role_id
        }
        
        # Prepare headers with CSRF token
        headers = self._get_headers()
        if csrf_token:
            headers['X-CSRF-TOKEN'] = csrf_token
        
        try:
            response = self.session.post(
                url,
                json=payload,
                headers=headers,
                cookies=self._get_cookies(),
                timeout=10
            )
            
            # If we got a 403, try to get CSRF token from response and retry
            if response.status_code == 403:
                new_csrf_token = response.headers.get('X-CSRF-TOKEN')
                if new_csrf_token and new_csrf_token != csrf_token:
                    print(f"🔐 Got CSRF token from 403 response, retrying...")
                    csrf_token = new_csrf_token
                    headers['X-CSRF-TOKEN'] = csrf_token
                    response = self.session.post(
                        url,
                        json=payload,
                        headers=headers,
                        cookies=self._get_cookies(),
                        timeout=10
                    )
                    print(f"📡 Retry response status: {response.status_code}")
            
            return response.status_code in [200, 204]
        except Exception as e:
            print(f"❌ Error adding member to group: {e}")
            return False
    
    def remove_member_from_group(self, user_id: int) -> bool:
        """Remove a member from the group (requires authentication)"""
        if not self.cookie:
            print("❌ Cannot remove member: No authentication cookie provided")
            return False
        
        # Get CSRF token first
        csrf_token = self._get_csrf_token()
        
        url = f"{self.base_url}/groups/{self.group_id}/users/{user_id}"
        
        # Prepare headers with CSRF token
        headers = self._get_headers()
        if csrf_token:
            headers['X-CSRF-TOKEN'] = csrf_token
        
        try:
            response = self.session.delete(
                url,
                headers=headers,
                cookies=self._get_cookies(),
                timeout=10
            )
            
            # If we got a 403, try to get CSRF token from response and retry
            if response.status_code == 403:
                new_csrf_token = response.headers.get('X-CSRF-TOKEN')
                if new_csrf_token and new_csrf_token != csrf_token:
                    print(f"🔐 Got CSRF token from 403 response, retrying...")
                    csrf_token = new_csrf_token
                    headers['X-CSRF-TOKEN'] = csrf_token
                    response = self.session.delete(
                        url,
                        headers=headers,
                        cookies=self._get_cookies(),
                        timeout=10
                    )
                    print(f"📡 Retry response status: {response.status_code}")
            
            return response.status_code in [200, 204]
        except Exception as e:
            print(f"❌ Error removing member from group: {e}")
            return False
    
    def get_user_id_by_username(self, username: str) -> Optional[int]:
        """Get Roblox user ID by username"""
        user_data = self.get_user_by_username(username)
        return user_data.get('id') if user_data else None
    
    def get_current_user(self) -> Optional[Dict]:
        """Get the current authenticated user (to verify which account the cookie belongs to)"""
        if not self.cookie:
            return None
        
        url = "https://users.roblox.com/v1/users/authenticated"
        try:
            response = self.session.get(
                url,
                headers=self._get_headers(),
                cookies=self._get_cookies(),
                timeout=10
            )
            if response.status_code == 200:
                return response.json()
        except:
            pass
        return None
    
    def get_user_role_in_group(self, user_id: int) -> Optional[Dict]:
        """Get a user's role in the group"""
        url = f"{self.base_url}/groups/{self.group_id}/users/{user_id}"
        try:
            response = self.session.get(
                url,
                headers=self._get_headers(),
                cookies=self._get_cookies(),
                timeout=10
            )
            if response.status_code == 200:
                return response.json()
        except:
            pass
        return None
    
    @staticmethod
    def validate_cookie(cookie: str) -> Optional[Dict]:
        """
        Validate a Roblox cookie and return the user info if valid.
        Returns None if invalid.
        """
        if not cookie:
            return None
            
        url = "https://users.roblox.com/v1/users/authenticated"
        headers = {
            'Content-Type': 'application/json',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json'
        }
        cookies = {'.ROBLOSECURITY': cookie}
        
        try:
            response = requests.get(url, headers=headers, cookies=cookies, timeout=10)
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            print(f"Error validating cookie: {e}")
            
        return None

    def test_connection(self) -> bool:
        """Test if we can connect to the Roblox API and fetch group info"""
        print(f"🔍 Testing connection to Roblox group {self.group_id}...")
        
        # Check which account the cookie belongs to
        current_user = self.get_current_user()
        if current_user:
            print(f"🔐 Authenticated as: {current_user.get('name', 'Unknown')} (ID: {current_user.get('id', 'Unknown')})")
        
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