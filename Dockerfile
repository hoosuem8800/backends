FROM python:3.11-slim

WORKDIR /app

# Install system dependencies including PostgreSQL client
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copy the rest of the application
COPY . .

# Create a startup script with better error handling
RUN echo '#!/bin/bash\n\
set -e\n\
echo "Starting Django application..."\n\
echo "DATABASE_URL: ${DATABASE_URL:-Not set}"\n\
echo "Checking database connection..."\n\
python manage.py check_db\n\
echo "Running migrations..."\n\
python manage.py migrate --noinput\n\
echo "Collecting static files..."\n\
python manage.py collectstatic --noinput\n\
echo "Starting Gunicorn server..."\n\
gunicorn backend_new.wsgi --log-file - --bind 0.0.0.0:8000\n' > /app/start.sh \
    && chmod +x /app/start.sh

# Make sure static directory exists
RUN mkdir -p static media

# Expose the port the app runs on
EXPOSE 8000

# Command to run the application
CMD ["/app/start.sh"] 