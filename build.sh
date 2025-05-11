#!/bin/bash
set -e

# Install system dependencies
apt-get update && apt-get install -y \
  build-essential \
  libpq-dev \
  postgresql-client \
  && rm -rf /var/lib/apt/lists/*

# Update pip
pip install --upgrade pip

# Install Pillow with binary option
pip install --only-binary :all: Pillow==9.5.0

# Install other requirements
pip install -r requirements.txt

# Create static directory if it doesn't exist
mkdir -p static

# Run Django collectstatic
python manage.py collectstatic --noinput 