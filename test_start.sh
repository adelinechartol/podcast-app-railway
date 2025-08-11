#!/bin/sh
echo "=== Environment Variables ==="
env | grep -E "PORT|RAILWAY"
echo "=== PORT value: $PORT ==="
echo "=== Starting Gunicorn ==="
exec gunicorn app:app --bind 0.0.0.0:${PORT:-8000} --timeout 120 --workers 1
