from app import create_app
import time

app = create_app()

if __name__ == "__main__":
    print("🚀 Starting Background Scheduler Service...")
    # The scheduler is started in create_app() if ROBLOX_BACKGROUND_SYNC_ENABLED is True
    
    # Keep the main thread alive
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("🛑 Stopping Scheduler Service...")
