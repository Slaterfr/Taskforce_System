"""
Quick script to fix all url_for() references in templates to use blueprint prefixes
"""
import re
import os

# Define the replacements: (old_endpoint, new_endpoint)
URL_REPLACEMENTS = [
    # Auth blueprint
    (r"url_for\('staff_login'", "url_for('auth.staff_login'"),
    (r"url_for\('staff_logout'", "url_for('auth.staff_logout'"),
    (r"url_for\('update_cookie'", "url_for('auth.update_cookie'"),
    
    # Public blueprint
    (r"url_for\('public_roster'", "url_for('public.public_roster'"),
    (r"url_for\('public_member'", "url_for('public.public_member'"),
    
    # Members blueprint
    (r"url_for\('dashboard'", "url_for('members.dashboard'"),
    (r"url_for\('members'", "url_for('members.members'"),
    (r"url_for\('add_member'", "url_for('members.add_member'"),
    (r"url_for\('edit_member'", "url_for('members.edit_member'"),
    (r"url_for\('delete_member'", "url_for('members.delete_member'"),
    (r"url_for\('member_detail'", "url_for('members.member_detail'"),
    (r"url_for\('promote_member'", "url_for('members.promote_member'"),
    
    # AC blueprint (only if not already prefixed)
    (r"url_for\('ac_dashboard'", "url_for('ac.ac_dashboard'"),
    (r"url_for\('create_ac_period'", "url_for('ac.create_ac_period'"),
    (r"url_for\('edit_ac_period'", "url_for('ac.edit_ac_period'"),
    (r"url_for\('log_ac_activity'", "url_for('ac.log_ac_activity'"),
    (r"url_for\('quick_log'", "url_for('ac.quick_log'"),
    (r"url_for\('quick_log_activity'", "url_for('ac.quick_log_activity'"),
    (r"url_for\('quick_log_ia'", "url_for('ac.quick_log_ia'"),
    (r"url_for\('quick_log_exempt'", "url_for('ac.quick_log_exempt'"),
    (r"url_for\('title_rewards'", "url_for('ac.title_rewards'"),
    (r"url_for\('send_title_webhook'", "url_for('ac.send_title_webhook'"),
    (r"url_for\('export_ac_excel'", "url_for('ac.export_ac_excel'"),
    (r"url_for\('ac_member_detail'", "url_for('ac.ac_member_detail'"),
    (r"url_for\('delete_ac_activity'", "url_for('ac.delete_ac_activity'"),
    (r"url_for\('clear_member_activities'", "url_for('ac.clear_member_activities'"),
    (r"url_for\('clear_all_activities'", "url_for('ac.clear_all_activities'"),
    
    # Sync blueprint
    (r"url_for\('manage_rank_mappings'", "url_for('sync.manage_rank_mappings'"),
    (r"url_for\('sync_now'", "url_for('sync.sync_now'"),
]

def fix_template(filepath):
    """Fix url_for() references in a single template file"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_content = content
        changes_made = 0
        
        for old_pattern, new_text in URL_REPLACEMENTS:
            new_content, count = re.subn(old_pattern, new_text, content)
            if count > 0:
                content = new_content
                changes_made += count
        
        if content != original_content:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"✓ Fixed {filepath.replace(TEMPLATES_DIR, '')} - {changes_made} change(s)")
            return changes_made
        else:
            print(f"- Skipped {filepath.replace(TEMPLATES_DIR, '')} - no changes needed")
            return 0
    except Exception as e:
        print(f"✗ Error processing {filepath}: {e}")
        return 0

# Main execution
TEMPLATES_DIR = r"c:\Users\emend\OneDrive\Documentos\TF_System\Taskforce_System\templates"
total_changes = 0

print("Starting template URL fixes...")
print("=" * 60)

for root, dirs, files in os.walk(TEMPLATES_DIR):
    for file in files:
        if file.endswith('.html'):
            filepath = os.path.join(root, file)
            total_changes += fix_template(filepath)

print("=" * 60)
print(f"✓ Complete! Total changes made: {total_changes}")
