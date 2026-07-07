# Configuration file for DriveHub Proxy
import os

class Config:
    # Server configuration
    PORT = int(os.getenv("PORT", 8080))
    HOST = os.getenv("HOST", "0.0.0.0")
    DEBUG = os.getenv("DEBUG", "false").lower() == "true"
    
    # Cache directory
    CACHE_DIR = os.getenv("CACHE_DIR", "./cache")
    
    # Default target URL
    DEFAULT_TARGET = os.getenv("DEFAULT_TARGET", "https://onlykdrama.shop/")
    
    # Request settings
    TIMEOUT = int(os.getenv("TIMEOUT", 30))
    MAX_RETRIES = int(os.getenv("MAX_RETRIES", 3))
    
    # Cloudflare bypass settings
    HEADLESS = os.getenv("HEADLESS", "true").lower() == "true"
    
    # Logging
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
