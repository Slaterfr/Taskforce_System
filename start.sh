#!/bin/bash
set -e
echo "Starting TF System (FastAPI + uvicorn)..."
exec uvicorn app:app --host 0.0.0.0 --port 5000 --workers 2
