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

# Make sure static directory exists and make start.sh executable
RUN mkdir -p static media && chmod +x start.sh

# Expose the port the app runs on
EXPOSE 8000

# Command to run the application
CMD ["./start.sh"] 