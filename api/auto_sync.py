"""
Automated Roblox sync system
Runs periodic syncs to catch new promotions to Aspirant+ automatically
"""

import time
import schedule
import sys
import os
from datetime import datetime
from typing import Optional

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sync_members import MemberSyncer

class AutoSyncManager:
    """Manages automated syncing of Roblox members"""
    
    def __init__(self, group_id: int, sync_interval_minutes: int = 60):
        self.group_id = group_id
        self.sync_interval_minutes = sync_interval_minutes
        self.syncer = MemberSyncer(group_id)
        self.is_running = False
        self.last_sync_time = None
        self.sync_count = 0
        
    def run_sync(self) -> bool:
        """Run a single sync operation"""
        print(f"\n{'='*60}")
        print(f"🔄 AUTO SYNC #{self.sync_count + 1} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*60}")
        
        try:
            # Run the sync (not dry run)
            stats = self.syncer.sync_all_members(dry_run=False)
            
            self.last_sync_time = datetime.now()
            self.sync_count += 1
            
            # Log summary
            if stats['members_added'] > 0 or stats['ranks_changed'] > 0:
                print(f"📈 SYNC RESULTS: +{stats['members_added']} members, {stats['ranks_changed']} rank changes")
                
                # Could add Discord webhook notification here
                if stats['members_added'] > 0:
                    print(f"🎉 NEW ASPIRANTS DETECTED! Added {stats['members_added']} new members")
            else:
                print(f"✅ No changes detected - all up to date")
            
            return stats['errors'] == 0
            
        except Exception as e:
            print(f"❌ Auto sync failed: {e}")
            return False
    
    def start_scheduler(self):
        """Start the automated sync scheduler"""
        print(f"🚀 Starting automated sync for group {self.group_id}")
        print(f"⏰ Sync interval: every {self.sync_interval_minutes} minutes")
        print(f"🎯 Monitoring for new Aspirant+ promotions...")
        print(f"{'='*60}")
        
        # Schedule the sync
        schedule.every(self.sync_interval_minutes).minutes.do(self.run_sync)
        
        # Run initial sync
        print("🔄 Running initial sync...")
        self.run_sync()
        
        self.is_running = True
        
        # Main loop
        try:
            while self.is_running:
                schedule.run_pending()
                time.sleep(30)  # Check every 30 seconds
                
        except KeyboardInterrupt:
            print("\n⏹️  Stopping auto sync...")
            self.is_running = False
    
    def stop_scheduler(self):
        """Stop the automated sync"""
        self.is_running = False
        schedule.clear()
        print("⏹️  Auto sync stopped")

class QuickSyncChecker:
    """Quick checker for recent promotions without full sync"""
    
    def __init__(self, group_id: int):
        self.syncer = MemberSyncer(group_id)
    
    def check_for_new_aspirants(self) -> dict:
        """Quick check specifically for new Aspirant promotions"""
        print("🔍 Quick check for new Aspirants...")
        
        # This could be optimized to only check recent promotions
        # For now, use the full sync but track specifically Aspirant additions
        stats = self.syncer.sync_all_members(dry_run=False)
        
        new_aspirants = []
        if stats['members_added'] > 0:
            # Could track specifically which were Aspirants
            print(f"🎉 Found {stats['members_added']} new Aspirant+ members!")
        
        return {
            'new_members': stats['members_added'],
            'rank_changes': stats['ranks_changed'],
            'errors': stats['errors']
        }

def main():
    """Main function for running auto sync"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Run automated Roblox member sync')
    parser.add_argument('--group-id', type=int, default=8482555, help='Roblox group ID')
    parser.add_argument('--interval', type=int, default=60, help='Sync interval in minutes')
    parser.add_argument('--once', action='store_true', help='Run sync once and exit')
    parser.add_argument('--quick-check', action='store_true', help='Quick check for new Aspirants')
    
    args = parser.parse_args()
    
    if args.quick_check:
        # Quick check mode
        checker = QuickSyncChecker(args.group_id)
        results = checker.check_for_new_aspirants()
        print(f"✅ Quick check complete: {results['new_members']} new members, {results['rank_changes']} changes")
        sys.exit(0 if results['errors'] == 0 else 1)
    
    elif args.once:
        # Single sync mode
        syncer = MemberSyncer(args.group_id)
        stats = syncer.sync_all_members(dry_run=False)
        print(f"✅ Single sync complete")
        sys.exit(0 if stats['errors'] == 0 else 1)
    
    else:
        # Continuous auto sync mode
        auto_sync = AutoSyncManager(args.group_id, args.interval)
        try:
            auto_sync.start_scheduler()
        except KeyboardInterrupt:
            print("\n👋 Auto sync stopped by user")
            sys.exit(0)

if __name__ == "__main__":
    main()