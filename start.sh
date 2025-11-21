#!/bin/bash
set -e

# Start the scheduler in the background
echo "🚀 Starting Background Scheduler..."
python run_scheduler.py &

# Start the web application in the foreground
echo "🌐 Starting Web Application..."
exec gunicorn --bind 0.0.0.0:5000 --workers 2 app:app
