#!/bin/bash
set -e

echo "Starting Django application..."
echo "DATABASE_URL: ${DATABASE_URL:-Not set}"

echo "Running migrations..."
python manage.py migrate --noinput

echo "Collecting static files..."
python manage.py collectstatic --noinput --clear

echo "Starting Gunicorn server..."
gunicorn backend_new.wsgi --log-file - --bind 0.0.0.0:$PORT 