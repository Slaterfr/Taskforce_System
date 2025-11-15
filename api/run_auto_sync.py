#!/usr/bin/env python3
"""
Manual Roblox sync trigger (optional)
NOTE: Auto-sync is now built into the Flask app and runs automatically!
This script is only needed if you want to manually trigger a sync outside the web app.

The main auto-sync runs automatically when you start your Flask app (if ROBLOX_SYNC_ENABLED=true).
It syncs every hour and also runs once on startup.
"""

import sys
import os

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from utils.roblox_sync import sync_from_roblox

def main():
    print("🔄 Manual Roblox Sync Trigger")
    print("=" * 50)
    print("NOTE: Auto-sync is built into the Flask app!")
    print("This will run a one-time sync now.")
    print()
    
    app = create_app()
    
    with app.app_context():
        print("🔄 Starting sync from Roblox...")
        result = sync_from_roblox()
        
        if result.get('success'):
            stats = result.get('stats', {})
            print(f"\n✅ Sync completed successfully!")
            print(f"   - {stats.get('added', 0)} new members added")
            print(f"   - {stats.get('updated', 0)} members updated")
            print(f"   - {stats.get('rank_changes', 0)} rank changes")
            print(f"   - {stats.get('errors', 0)} errors")
        else:
            print(f"\n❌ Sync failed: {result.get('message', 'Unknown error')}")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()