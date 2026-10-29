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
    
    def __init__(self, webhook_url: Optional[str] = None, channel_id: Optional[str] = None, bot_token: Optional[str] = None):
        import os
        self.webhook_url = webhook_url
        self.channel_id = channel_id
        self.bot_token = bot_token or os.environ.get("DISCORD_TOKEN") or os.environ.get("DISCORD_BOT_TOKEN")
        self.enabled = bool(webhook_url or (channel_id and self.bot_token))
    
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
        """Send embed to Discord webhook or directly to channel via Bot API"""
        payload = {
            "username": "Taskforce Manager",
            "embeds": [embed]
        }

        # 1. Direct Bot Message to channel_id if configured
        if self.channel_id and self.bot_token:
            clean_cid = str(self.channel_id).strip()
            # If accidentally a webhook URL
            if clean_cid.startswith("http"):
                target_url = clean_cid
                headers = {'Content-Type': 'application/json'}
            else:
                target_url = f"https://discord.com/api/v10/channels/{clean_cid}/messages"
                headers = {
                    'Authorization': f'Bot {self.bot_token}',
                    'Content-Type': 'application/json'
                }
            try:
                response = requests.post(target_url, json=payload, headers=headers, timeout=10)
                if response.status_code in (200, 204):
                    print(f"✅ Notification delivered to channel {clean_cid}")
                    return
                else:
                    print(f"⚠️ Channel delivery failed: {response.status_code} - {response.text}")
            except Exception as e:
                print(f"❌ Error sending notification to channel {clean_cid}: {e}")

        # 2. Webhook URL fallback
        if self.webhook_url:
            try:
                response = requests.post(
                    self.webhook_url,
                    json=payload,
                    headers={'Content-Type': 'application/json'},
                    timeout=10
                )
                if response.status_code in (200, 204):
                    print("✅ Webhook notification sent successfully")
                else:
                    print(f"⚠️ Webhook failed: {response.status_code}")
            except requests.exceptions.RequestException as e:
                print(f"❌ Webhook error: {e}")


def create_notifier_from_config() -> DiscordWebhookNotifier:
    """Create webhook notifier from environment config"""
    import os
    webhook_url = os.environ.get('DISCORD_NOTIFICATION_WEBHOOK_URL') or os.environ.get('DISCORD_WEBHOOK_URL')
    channel_id = os.environ.get('NOTIFICATION_CHANNEL_ID')
    bot_token = os.environ.get('DISCORD_TOKEN') or os.environ.get('DISCORD_BOT_TOKEN')
    return DiscordWebhookNotifier(webhook_url=webhook_url, channel_id=channel_id, bot_token=bot_token)


def create_notifier_for_tenant(tenant_id: int) -> DiscordWebhookNotifier:
    """Create a notifier targeted to a specific tenant's webhook_channel_id"""
    import os
    from database.engine import engine
    from sqlmodel import Session
    from database.tenant_models import Group

    channel_id = None
    with Session(engine) as session:
        grp = session.get(Group, tenant_id)
        if grp and grp.webhook_channel_id:
            channel_id = grp.webhook_channel_id

    bot_token = os.environ.get('DISCORD_TOKEN') or os.environ.get('DISCORD_BOT_TOKEN')
    webhook_url = None
    if channel_id and channel_id.startswith("http"):
        webhook_url = channel_id
        channel_id = None

    if not channel_id and not webhook_url:
        webhook_url = os.environ.get('DISCORD_NOTIFICATION_WEBHOOK_URL') or os.environ.get('DISCORD_WEBHOOK_URL')

    return DiscordWebhookNotifier(webhook_url=webhook_url, channel_id=channel_id, bot_token=bot_token)