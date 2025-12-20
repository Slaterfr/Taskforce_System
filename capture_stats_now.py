from app import create_app
from utils.stats_logger import capture_member_stats

app = create_app()
with app.app_context():
    print("📸 Capturing initial Member Stats snapshot...")
    if capture_member_stats():
        print("✅ Success!")
    else:
        print("❌ Failed.")
