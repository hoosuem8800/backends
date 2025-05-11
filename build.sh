#!/bin/bash
set -e

# Update pip
pip install --upgrade pip

# Install Pillow with binary option
pip install --only-binary :all: Pillow==9.5.0

# Install other requirements
pip install -r requirements.txt

# Run Django collectstatic
python manage.py collectstatic --noinput 