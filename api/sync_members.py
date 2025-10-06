"""
Roblox Member Sync Script
Synchronizes members between Roblox group and local database
Only syncs members with Aspirant rank or higher
"""

import sys
import os
from datetime import datetime
from typing import List, Dict, Set

# Add parent directory to path so we can import our models
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from database.models import db, Member, PromotionLog
from api.roblox_api import RobloxAPI, RobloxMember, map_roblox_rank_to_system

class MemberSyncer:
    """Handles synchronization between Roblox and local database"""
    
    def __init__(self, group_id: int):
        self.roblox_api = RobloxAPI(group_id)
        self.app = create_app()
        
        # Rank hierarchy for filtering (Aspirant and above only)
        self.eligible_ranks = [
            'Aspirant', 'Novice', 'Adept', 'Crusader', 'Paladin', 
            'Exemplar', 'Prospect', 'Commander', 'Marshal', 'General', 'Chief General'
        ]
        
        # Statistics
        self.stats = {
            'total_roblox_members': 0,
            'eligible_roblox_members': 0,
            'total_db_members': 0,
            'members_added': 0,
            'members_updated': 0,
            'ranks_changed': 0,
            'members_skipped': 0,
            'errors': 0
        }
        
        # Track changes for notifications
        self.new_members = []
        self.rank_changes = []
    
    def sync_all_members(self, dry_run: bool = False) -> Dict:
        """
        Main sync function - syncs Aspirant+ members from Roblox to database
        
        Args:
            dry_run: If True, shows what would happen without making changes
        
        Returns:
            Dictionary with sync statistics
        """
        print("🚀 Starting Roblox member synchronization (Aspirant+ only)...")
        print("=" * 70)
        
        if dry_run:
            print("🔍 DRY RUN MODE - No changes will be made")
            print("-" * 70)
        
        # Test connection first
        if not self.roblox_api.test_connection():
            self.stats['errors'] += 1
            return self.stats
        
        with self.app.app_context():
            # Get all members from Roblox
            roblox_members = self.roblox_api.get_group_members()
            self.stats['total_roblox_members'] = len(roblox_members)
            
            if not roblox_members:
                print("❌ No members fetched from Roblox")
                self.stats['errors'] += 1
                return self.stats
            
            # Get all active members from database
            db_members = Member.query.filter_by(is_active=True).all()
            self.stats['total_db_members'] = len(db_members)
            
            # Create lookup maps
            roblox_by_username = {member.username.lower(): member for member in roblox_members}
            db_by_roblox_username = {
                member.roblox_username.lower(): member 
                for member in db_members 
                if member.roblox_username
            }
            
            print(f"📊 Found {len(roblox_members)} total members in Roblox group")
            print(f"📊 Found {len(db_members)} active members in database")
            print("-" * 70)
            
            # Process each Roblox member (only Aspirant+)
            eligible_count = 0
            for roblox_member in roblox_members:
                try:
                    system_rank = map_roblox_rank_to_system(roblox_member.role_name)
                    if self._is_eligible_rank(system_rank):
                        eligible_count += 1
                        self._process_roblox_member(roblox_member, db_by_roblox_username, dry_run)
                    else:
                        self.stats['members_skipped'] += 1
                except Exception as e:
                    print(f"❌ Error processing {roblox_member.username}: {e}")
                    self.stats['errors'] += 1
            
            self.stats['eligible_roblox_members'] = eligible_count
            print(f"📊 {eligible_count} members are Aspirant+ (eligible for database)")
            print(f"📊 {self.stats['members_skipped']} members skipped (below Aspirant)")
            print("-" * 70)
            
            # Find members in database but not in Roblox (potentially left group)
            self._check_inactive_members(roblox_by_username, db_members, dry_run)
            
            if not dry_run:
                db.session.commit()
                print("\n💾 Changes saved to database")
        
        self._print_summary()
        return self.stats
    
    def _is_eligible_rank(self, rank: str) -> bool:
        """Check if rank is Aspirant or above"""
        return rank in self.eligible_ranks
    
    def _process_roblox_member(self, roblox_member: RobloxMember, db_lookup: Dict, dry_run: bool):
        """Process a single Roblox member - only Aspirant+ ranks"""
        username_lower = roblox_member.username.lower()
        system_rank = map_roblox_rank_to_system(roblox_member.role_name)
        
        # Double check eligibility (should already be filtered, but safety first)
        if not self._is_eligible_rank(system_rank):
            return
        
        if username_lower in db_lookup:
            # Member exists - check for updates
            db_member = db_lookup[username_lower]
            self._update_existing_member(db_member, roblox_member, system_rank, dry_run)
        else:
            # New member - add to database
            self._add_new_member(roblox_member, system_rank, dry_run)
    
    def _add_new_member(self, roblox_member: RobloxMember, system_rank: str, dry_run: bool):
        """Add a new member from Roblox to the database"""
        
        print(f"➕ NEW ASPIRANT+: {roblox_member.username} ({system_rank})")
        
        # Track for notifications
        member_info = {
            'username': roblox_member.username,
            'rank': system_rank,
            'user_id': roblox_member.user_id
        }
        self.new_members.append(member_info)
        
        if not dry_run:
            new_member = Member(
                discord_username=roblox_member.username,  # Will be updated when they link Discord
                roblox_username=roblox_member.username,
                roblox_id=str(roblox_member.user_id),
                current_rank=system_rank,
                join_date=datetime.utcnow(),
                last_updated=datetime.utcnow()
            )
            
            db.session.add(new_member)
        
        self.stats['members_added'] += 1
    
    def _update_existing_member(self, db_member: Member, roblox_member: RobloxMember, system_rank: str, dry_run: bool):
        """Update an existing member's information"""
        
        changes = []
        
        # Check if rank changed
        if db_member.current_rank != system_rank:
            changes.append(f"rank: {db_member.current_rank} → {system_rank}")
            
            # Track for notifications
            rank_change = {
                'username': db_member.discord_username,
                'from_rank': db_member.current_rank,
                'to_rank': system_rank
            }
            self.rank_changes.append(rank_change)
            
            if not dry_run:
                # Log the promotion/demotion
                promotion = PromotionLog(
                    member_id=db_member.id,
                    from_rank=db_member.current_rank,
                    to_rank=system_rank,
                    reason="Automatic sync from Roblox group",
                    promoted_by="Roblox Sync Bot"
                )
                db.session.add(promotion)
                
                db_member.current_rank = system_rank
            
            self.stats['ranks_changed'] += 1
        
        # Update Roblox ID if missing
        if not db_member.roblox_id:
            changes.append(f"added Roblox ID: {roblox_member.user_id}")
            if not dry_run:
                db_member.roblox_id = str(roblox_member.user_id)
        
        # Update Roblox username if it changed
        if db_member.roblox_username != roblox_member.username:
            changes.append(f"updated Roblox username: {db_member.roblox_username} → {roblox_member.username}")
            if not dry_run:
                db_member.roblox_username = roblox_member.username
        
        # Update last_updated timestamp
        if not dry_run:
            db_member.last_updated = datetime.utcnow()
        
        if changes:
            print(f"🔄 UPDATED: {db_member.discord_username} ({', '.join(changes)})")
            self.stats['members_updated'] += 1
    
    def _check_inactive_members(self, roblox_lookup: Dict, db_members: List[Member], dry_run: bool):
        """Check for members in database who are no longer in Roblox group"""
        
        potentially_inactive = []
        
        for db_member in db_members:
            if not db_member.roblox_username:
                continue  # Skip members without Roblox usernames
                
            username_lower = db_member.roblox_username.lower()
            
            if username_lower not in roblox_lookup:
                potentially_inactive.append(db_member)
        
        if potentially_inactive:
            print(f"\n⚠️  MEMBERS NOT FOUND IN ROBLOX GROUP ({len(potentially_inactive)}):")
            for member in potentially_inactive[:10]:  # Show first 10
                print(f"   • {member.discord_username} ({member.roblox_username}) - {member.current_rank}")
                print(f"     Last seen: {member.last_updated.strftime('%Y-%m-%d')}")
            
            if len(potentially_inactive) > 10:
                print(f"   ... and {len(potentially_inactive) - 10} more")
            
            print("\n💡 These members might have:")
            print("   - Left the Roblox group")
            print("   - Changed their Roblox username")
            print("   - Been demoted below Aspirant")
            print("   - Account issues/bans")
            print("\n   Manual review recommended - not automatically removed for safety")
    
    def _print_summary(self):
        """Print sync summary"""
        print("\n" + "=" * 70)
        print("📈 SYNC SUMMARY")
        print("=" * 70)
        print(f"Total Roblox members:     {self.stats['total_roblox_members']}")
        print(f"Eligible (Aspirant+):     {self.stats['eligible_roblox_members']}")
        print(f"Skipped (below Aspirant): {self.stats['members_skipped']}")
        print(f"Database members before:  {self.stats['total_db_members']}")
        print("-" * 40)
        print(f"New members added:        {self.stats['members_added']}")
        print(f"Members updated:          {self.stats['members_updated']}")
        print(f"Rank changes made:        {self.stats['ranks_changed']}")
        print(f"Errors encountered:       {self.stats['errors']}")
        print("=" * 70)
        
        if self.stats['errors'] == 0:
            print("✅ Sync completed successfully!")
        else:
            print("⚠️  Sync completed with some errors")
        
        # Highlight important changes
        if self.stats['members_added'] > 0:
            print(f"\n🎉 NEW ASPIRANTS DETECTED: {self.stats['members_added']} new members added!")
        
        if self.stats['ranks_changed'] > 0:
            print(f"📈 RANK CHANGES: {self.stats['ranks_changed']} members promoted/demoted")

def main():
    """Main function to run the sync"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Sync Roblox group members with database (Aspirant+ only)')
    parser.add_argument('group_id', type=int, help='Roblox group ID', nargs='?', default=8482555)
    parser.add_argument('--dry-run', action='store_true', help='Show what would happen without making changes')
    parser.add_argument('--limit', type=int, default=10000, help='Maximum number of members to fetch from Roblox')
    
    args = parser.parse_args()
    
    # Create syncer and run
    syncer = MemberSyncer(args.group_id)
    
    if args.dry_run:
        print("🔍 Running in DRY RUN mode - no changes will be made")
    
    stats = syncer.sync_all_members(dry_run=args.dry_run)
    
    # Return appropriate exit code
    if stats['errors'] > 0:
        sys.exit(1)
    else:
        sys.exit(0)

if __name__ == "__main__":
    main()