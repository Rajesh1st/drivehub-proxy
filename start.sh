#!/bin/bash

# DriveHub Proxy Startup Script

echo "=========================================="
echo "🚀 Starting DriveHub Universal Proxy"
echo "=========================================="

# Create cache directory
mkdir -p cache

# Install dependencies
echo "📦 Installing dependencies..."
pip install -r requirements.txt

# Start the server
echo "🌐 Starting server on port 8080..."
python app.py
