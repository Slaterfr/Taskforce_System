"""
Discord webhook notifications for Roblox sync events
Sends notifications when new Aspirants are detected
"""

import requests
import json
from datetime import datetime
from typing import List, Optional

class DiscordWebhookNotifier:
    """Sends Discord webhook notifications for sync events"""
    
    def __init__(self, webhook_url: Optional[str] = None):
        self.webhook_url = webhook_url
        self.enabled = bool(webhook_url)
    
    def notify_new_aspirants(self, new_members: List[dict], sync_stats: dict):
        """Send notification about new Aspirants"""
        if not self.enabled:
            return
        
        if not new_members:
            return
        
        embed = {
            "title": "🎉 New Aspirants Detected!",
            "description": f"Found {len(new_members)} new members who reached Aspirant rank",
            "color": 0x00ff00,  # Green
            "timestamp": datetime.utcnow().isoformat(),
            "fields": []
        }
        
        # Add member list
        member_list = "\n".join([
            f"• **{member['username']}** ({member['rank']})" 
            for member in new_members[:10]  # Limit to 10 for space
        ])
        
        if len(new_members) > 10:
            member_list += f"\n... and {len(new_members) - 10} more"
        
        embed["fields"].append({
            "name": "New Members",
            "value": member_list,
            "inline": False
        })
        
        # Add stats
        embed["fields"].append({
            "name": "Sync Statistics",
            "value": f"Total Added: {sync_stats.get('members_added', 0)}\n" +
                    f"Rank Changes: {sync_stats.get('ranks_changed', 0)}\n" +
                    f"Errors: {sync_stats.get('errors', 0)}",
            "inline": True
        })
        
        embed["footer"] = {
            "text": "Jedi Taskforce Management System",
            "icon_url": "https://cdn.discordapp.com/emojis/example.png"  # Optional
        }
        
        self._send_webhook(embed)
    
    def notify_rank_changes(self, rank_changes: List[dict]):
        """Send notification about rank changes"""
        if not self.enabled or not rank_changes:
            return
        
        embed = {
            "title": "📈 Rank Changes Detected",
            "description": f"Detected {len(rank_changes)} rank changes",
            "color": 0x0099ff,  # Blue
            "timestamp": datetime.utcnow().isoformat(),
            "fields": []
        }
        
        changes_text = "\n".join([
            f"• **{change['username']}**: {change['from_rank']} → {change['to_rank']}"
            for change in rank_changes[:10]
        ])
        
        if len(rank_changes) > 10:
            changes_text += f"\n... and {len(rank_changes) - 10} more"
        
        embed["fields"].append({
            "name": "Rank Changes",
            "value": changes_text,
            "inline": False
        })
        
        self._send_webhook(embed)
    
    def notify_sync_error(self, error_message: str):
        """Send notification about sync errors"""
        if not self.enabled:
            return
        
        embed = {
            "title": "❌ Sync Error",
            "description": "An error occurred during automated sync",
            "color": 0xff0000,  # Red
            "timestamp": datetime.utcnow().isoformat(),
            "fields": [
                {
                    "name": "Error Details",
                    "value": error_message[:1000],  # Limit length
                    "inline": False
                }
            ]
        }
        
        self._send_webhook(embed)
    
    def _send_webhook(self, embed: dict):
        """Send webhook with embed"""
        if not self.webhook_url:
            return
        
        payload = {
            "username": "Taskforce Manager",
            "embeds": [embed]
        }
        
        try:
            response = requests.post(
                self.webhook_url,
                data=json.dumps(payload),
                headers={'Content-Type': 'application/json'},
                timeout=10
            )
            
            if response.status_code == 204:
                print("✅ Webhook notification sent successfully")
            else:
                print(f"⚠️ Webhook failed: {response.status_code}")
                
        except requests.exceptions.RequestException as e:
            print(f"❌ Webhook error: {e}")

def create_notifier_from_config() -> DiscordWebhookNotifier:
    """Create webhook notifier from environment config"""
    import os
    
    webhook_url = os.environ.get('DISCORD_WEBHOOK_URL')
    if not webhook_url:
        print("💡 Tip: Set DISCORD_WEBHOOK_URL environment variable for notifications")
    
    return DiscordWebhookNotifier(webhook_url)