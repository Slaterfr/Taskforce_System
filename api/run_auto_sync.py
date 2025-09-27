#!/usr/bin/env python3
"""
Run automated Roblox sync to catch new Aspirant promotions
Usage: python run_auto_sync.py [options]
"""

from auto_sync import AutoSyncManager, QuickSyncChecker

def main():
    GROUP_ID = 8482555  # Your Jedi Taskforce group
    
    print("🎯 Jedi Taskforce - Automated Member Sync")
    print("=" * 50)
    print("This will automatically detect when someone gets promoted to Aspirant")
    print("and add them to your management system.")
    print()
    
    # Ask user what they want to do
    print("Options:")
    print("1. Run continuous auto-sync (checks every hour)")
    print("2. Quick check for new Aspirants (run once)")
    print("3. Custom interval auto-sync")
    print()
    
    choice = input("Choose option (1-3): ").strip()
    
    if choice == "1":
        # Standard auto-sync every hour
        print("\n🚀 Starting hourly auto-sync...")
        auto_sync = AutoSyncManager(GROUP_ID, sync_interval_minutes=60)
        auto_sync.start_scheduler()
        
    elif choice == "2":
        # Quick check
        print("\n🔍 Running quick check for new Aspirants...")
        checker = QuickSyncChecker(GROUP_ID)
        results = checker.check_for_new_aspirants()
        
        if results['new_members'] > 0:
            print(f"🎉 Found {results['new_members']} new Aspirant+ members!")
        else:
            print("✅ No new Aspirants found")
            
    elif choice == "3":
        # Custom interval
        try:
            interval = int(input("\nEnter sync interval in minutes (default 60): ") or "60")
            print(f"\n🚀 Starting auto-sync every {interval} minutes...")
            auto_sync = AutoSyncManager(GROUP_ID, sync_interval_minutes=interval)
            auto_sync.start_scheduler()
        except ValueError:
            print("❌ Invalid interval. Please enter a number.")
    
    else:
        print("❌ Invalid choice")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
    except Exception as e:
        print(f"❌ Error: {e}")