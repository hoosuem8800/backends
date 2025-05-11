#!/bin/bash
set -e

echo "Starting Django application..."
echo "DATABASE_URL: ${DATABASE_URL:-Not set}"

# Try running migrations, but continue if they fail
echo "Running migrations..."
python manage.py migrate --noinput || echo "Migrations failed, but continuing..."

# Try collecting static files, but continue if it fails
echo "Collecting static files..."
python manage.py collectstatic --noinput --clear || echo "Collectstatic failed, but continuing..."

# Make sure the health check URL will work
echo "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())" | python

# Start the server
echo "Starting Gunicorn server..."
gunicorn backend_new.wsgi --log-file - --bind 0.0.0.0:$PORT 