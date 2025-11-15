"""
Quick script to run the app accessible on your local network.
Share the IP address shown with your teammates.
"""
import socket
from app import app

def get_local_ip():
    """Get the local IP address"""
    try:
        # Connect to a remote address to determine local IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

if __name__ == '__main__':
    local_ip = get_local_ip()
    port = 5000
    
    print("=" * 60)
    print("Taskforce System - Local Network Server")
    print("=" * 60)
    print(f"\nLocal access:  http://127.0.0.1:{port}")
    print(f"Network access: http://{local_ip}:{port}")
    print("\nShare this URL with your teammates:")
    print(f"  👉 http://{local_ip}:{port}")
    print("\nPress Ctrl+C to stop the server")
    print("=" * 60)
    print()
    
    app.run(host='0.0.0.0', port=port, debug=True)


