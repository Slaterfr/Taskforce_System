from app import create_app
import time

app = create_app()

if __name__ == "__main__":
    print("🚀 Starting Background Scheduler Service...")
    
    # We need to import the scheduler configuration from app.py
    # But since app.py initializes the scheduler within create_app ONLY if not running appropriately,
    # we should likely centralize the scheduler logic or trust create_app to handle it.
    
    # However, the current app.py starts the scheduler inside create_app if config is enabled.
    # Let's verify if we need to add the stats job there or here.
    # Ideally, we should add the job to the scheduler instance in app.py or here.
    
    # Let's modify app.py to include this job instead, as that's where the scheduler is created.
    # This file just keeps the process alive.
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("🛑 Stopping Scheduler Service...")

