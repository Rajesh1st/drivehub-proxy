FROM python:3.11-slim

WORKDIR /app

# Install dependencies
RUN apt-get update && apt-get install -y \
    wget \
    curl \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js (required for CFSession)
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Create cache directory
RUN mkdir -p cache

# Expose port
EXPOSE 8080

# Start the application
CMD ["python", "app.py"]
