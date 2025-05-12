FROM python:3.11-slim

WORKDIR /app

# Install system dependencies including PostgreSQL client and Pillow dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    postgresql-client \
    libjpeg-dev \
    zlib1g-dev \
    libfreetype6-dev \
    liblcms2-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copy the rest of the application
COPY . .

# Make sure static directory exists and make start.sh executable
RUN mkdir -p static media && chmod +x start.sh

# Expose the port the app runs on
EXPOSE 8000

# Add ML_API_URL to the environment variables
ENV ML_API_URL=https://sage-production.up.railway.app

# Command to run the application
CMD ["./start.sh"] 