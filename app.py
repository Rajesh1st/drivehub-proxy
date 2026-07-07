#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
DriveHub Universal Proxy - VPS Edition
Complete Cloudflare bypass proxy with dynamic target URLs
Deploy on VPS, Termux, or any Linux server
"""

import os
import sys
import json
import time
import logging
import threading
import requests
from flask import Flask, jsonify, request, Response, render_template_string
from flask_cors import CORS
from urllib.parse import urlparse, urljoin

# Try to import CFSession, fallback to custom implementation
try:
    from CFSession import cfSession, cfDirectory
    CFSESSION_AVAILABLE = True
except ImportError:
    CFSESSION_AVAILABLE = False
    logging.warning("CFSession not installed, using requests fallback")

# ============================================================
# CONFIGURATION
# ============================================================

CONFIG = {
    "PORT": int(os.getenv("PORT", 8080)),
    "HOST": os.getenv("HOST", "0.0.0.0"),
    "DEBUG": os.getenv("DEBUG", "false").lower() == "true",
    "CACHE_DIR": os.getenv("CACHE_DIR", "./cache"),
    "DEFAULT_TARGET": os.getenv("DEFAULT_TARGET", "https://onlykdrama.shop/"),
    "TIMEOUT": int(os.getenv("TIMEOUT", 30)),
    "MAX_RETRIES": int(os.getenv("MAX_RETRIES", 3)),
    "HEADLESS": os.getenv("HEADLESS", "true").lower() == "true",
    "LOG_LEVEL": os.getenv("LOG_LEVEL", "INFO")
}

# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    level=getattr(logging, CONFIG["LOG_LEVEL"]),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============================================================
# CUSTOM CFSESSION FALLBACK
# ============================================================

class SimpleCFSession:
    """Simple Cloudflare bypass without CFSession"""
    
    def __init__(self, cache_dir="./cache", headless_mode=True):
        self.cache_dir = cache_dir
        self.headless_mode = headless_mode
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1'
        })
        
        os.makedirs(cache_dir, exist_ok=True)
        
        # Load cookies from cache if available
        self._load_cookies()
    
    def _load_cookies(self):
        """Load cookies from cache file"""
        cookie_file = os.path.join(self.cache_dir, "cookies.json")
        if os.path.exists(cookie_file):
            try:
                with open(cookie_file, 'r') as f:
                    cookies = json.load(f)
                    for name, value in cookies.items():
                        self.session.cookies.set(name, value)
                logger.info(f"Loaded {len(cookies)} cookies from cache")
            except Exception as e:
                logger.warning(f"Failed to load cookies: {e}")
    
    def _save_cookies(self):
        """Save cookies to cache file"""
        cookie_file = os.path.join(self.cache_dir, "cookies.json")
        try:
            cookies = {name: value for name, value in self.session.cookies.items()}
            with open(cookie_file, 'w') as f:
                json.dump(cookies, f)
            logger.info(f"Saved {len(cookies)} cookies to cache")
        except Exception as e:
            logger.warning(f"Failed to save cookies: {e}")
    
    def get(self, url, **kwargs):
        """Make GET request with cookie persistence"""
        response = self.session.get(url, timeout=CONFIG["TIMEOUT"], **kwargs)
        self._save_cookies()
        return response
    
    def post(self, url, **kwargs):
        """Make POST request with cookie persistence"""
        response = self.session.post(url, timeout=CONFIG["TIMEOUT"], **kwargs)
        self._save_cookies()
        return response
    
    def put(self, url, **kwargs):
        """Make PUT request with cookie persistence"""
        response = self.session.put(url, timeout=CONFIG["TIMEOUT"], **kwargs)
        self._save_cookies()
        return response
    
    def delete(self, url, **kwargs):
        """Make DELETE request with cookie persistence"""
        response = self.session.delete(url, timeout=CONFIG["TIMEOUT"], **kwargs)
        self._save_cookies()
        return response

# ============================================================
# SESSION MANAGER
# ============================================================

class SessionManager:
    """Manage Cloudflare sessions for multiple targets"""
    
    def __init__(self):
        self.sessions = {}
        self.renewers = {}
        self.lock = threading.Lock()
    
    def get_session(self, target_url):
        """Get or create session for target URL"""
        with self.lock:
            if target_url not in self.sessions:
                logger.info(f"Creating session for: {target_url}")
                
                if CFSESSION_AVAILABLE:
                    session = cfSession(
                        directory=cfDirectory(CONFIG["CACHE_DIR"]),
                        headless_mode=CONFIG["HEADLESS"]
                    )
                else:
                    session = SimpleCFSession(
                        cache_dir=CONFIG["CACHE_DIR"],
                        headless_mode=CONFIG["HEADLESS"]
                    )
                
                self.sessions[target_url] = session
                self.renewers[target_url] = Renewer(target_url)
            
            return self.sessions[target_url]

# ============================================================
# RENEWER
# ============================================================

class Renewer:
    """Handle cookie renewal for a target"""
    
    def __init__(self, target):
        self.target = target
        self.renewing = False
        self._thread = None
    
    def _renew_backend(self, session):
        """Background renewal process"""
        self.renewing = True
        try:
            logger.info(f"Renewing cookies for: {self.target}")
            resp = session.get(self.target)
            logger.info(f"Renewal completed with status: {resp.status_code}")
        except Exception as e:
            logger.error(f"Renewal failed: {e}")
        finally:
            self.renewing = False
    
    def renew(self, session):
        """Start renewal if needed"""
        if self.renewing:
            return {
                "status": False,
                "reason": "Renewal already in progress"
            }
        
        # Check if cookies are valid
        try:
            response = session.get(self.target)
            if response.status_code == 200:
                return {
                    "status": False,
                    "reason": "Cookies are valid"
                }
        except:
            pass
        
        # Start renewal thread
        self._thread = threading.Thread(
            target=self._renew_backend,
            args=(session,)
        )
        self._thread.start()
        
        return {
            "status": True,
            "reason": "Renewal started"
        }

# ============================================================
# FLASK APPLICATION
# ============================================================

app = Flask(__name__)
CORS(app)

# Initialize session manager
session_manager = SessionManager()

# ============================================================
# API ENDPOINTS
# ============================================================

@app.route("/", methods=["GET"])
def home():
    """Home page with API documentation"""
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>DriveHub Universal Proxy</title>
        <style>
            body { font-family: Arial, sans-serif; max-width: 800px; margin: 50px auto; padding: 20px; }
            h1 { color: #4CAF50; }
            .endpoint { background: #f5f5f5; padding: 15px; margin: 10px 0; border-radius: 5px; }
            .method { display: inline-block; padding: 3px 10px; border-radius: 3px; font-weight: bold; }
            .get { background: #61affe; color: white; }
            .post { background: #49cc90; color: white; }
            .put { background: #fca130; color: white; }
            .delete { background: #f93e3e; color: white; }
            code { background: #eee; padding: 2px 6px; border-radius: 3px; }
        </style>
    </head>
    <body>
        <h1>🚀 DriveHub Universal Proxy</h1>
        <p>Bypass Cloudflare and proxy any website</p>
        
        <h2>📌 Endpoints</h2>
        
        <div class="endpoint">
            <span class="method get">GET</span>
            <code>/proxy?target=https://example.com/path</code>
            <p>Proxy any URL through Cloudflare bypass</p>
        </div>
        
        <div class="endpoint">
            <span class="method post">POST</span>
            <code>/proxy?target=https://example.com/api</code>
            <p>Proxy POST requests</p>
        </div>
        
        <div class="endpoint">
            <span class="method get">GET</span>
            <code>/set_target?url=https://example.com</code>
            <p>Set default target URL</p>
        </div>
        
        <div class="endpoint">
            <span class="method get">GET</span>
            <code>/renew?target=https://example.com</code>
            <p>Force renew cookies for a target</p>
        </div>
        
        <div class="endpoint">
            <span class="method get">GET</span>
            <code>/status</code>
            <p>Check proxy status</p>
        </div>
        
        <h2>📝 Examples</h2>
        <p>Proxy a website:</p>
        <code>https://your-vps:8080/proxy?target=https://multimovies.art/</code>
        
        <p>Set default target:</p>
        <code>https://your-vps:8080/set_target?url=https://new16.drivehub.cfd/</code>
    </body>
    </html>
    """
    return render_template_string(html)

@app.route("/proxy", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"])
def proxy():
    """Universal proxy endpoint"""
    try:
        # Get target URL from query parameter
        target_url = request.args.get("target")
        
        if not target_url:
            # Use default target if no URL provided
            target_url = CONFIG["DEFAULT_TARGET"]
            logger.info(f"No target provided, using default: {target_url}")
        
        # Validate URL
        if not target_url.startswith(("http://", "https://")):
            target_url = "https://" + target_url
        
        # Get the path from the original request
        path = request.path
        
        # Build full target URL
        if path.startswith("/proxy"):
            path = ""
        
        # Get remaining path from query parameter
        remaining_path = request.args.get("path", "")
        
        if remaining_path:
            # Full URL provided
            if remaining_path.startswith(("http://", "https://")):
                target_url = remaining_path
            else:
                target_url = urljoin(target_url, remaining_path)
        elif path and path != "/proxy" and path != "/":
            target_url = urljoin(target_url, path)
        
        logger.info(f"Proxying to: {target_url}")
        
        # Get session for this target
        session = session_manager.get_session(target_url)
        
        # Prepare request
        method = request.method
        headers = {key: value for key, value in request.headers if key.lower() not in ['host', 'content-length']}
        data = request.get_data()
        params = request.args.to_dict()
        
        # Remove proxy-specific params
        params.pop("target", None)
        params.pop("path", None)
        
        # Make request
        if method == "GET":
            response = session.get(target_url, headers=headers, params=params)
        elif method == "POST":
            response = session.post(target_url, headers=headers, data=data, params=params)
        elif method == "PUT":
            response = session.put(target_url, headers=headers, data=data, params=params)
        elif method == "DELETE":
            response = session.delete(target_url, headers=headers, params=params)
        else:
            response = session.get(target_url, headers=headers, params=params)
        
        # Prepare response
        content = response.content
        content_type = response.headers.get("Content-Type", "text/html")
        
        # Create response
        flask_response = Response(content, status=response.status_code)
        flask_response.headers["Content-Type"] = content_type
        
        # Copy some headers
        for header in ["Content-Encoding", "Cache-Control", "ETag", "Last-Modified"]:
            if header in response.headers:
                flask_response.headers[header] = response.headers[header]
        
        return flask_response
        
    except Exception as e:
        logger.error(f"Proxy error: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route("/set_target", methods=["GET", "POST"])
def set_target():
    """Set default target URL"""
    try:
        new_target = request.args.get("url") or request.json.get("url")
        
        if not new_target:
            return jsonify({
                "success": False,
                "error": "Missing 'url' parameter"
            }), 400
        
        if not new_target.startswith(("http://", "https://")):
            new_target = "https://" + new_target
        
        # Update config
        CONFIG["DEFAULT_TARGET"] = new_target
        
        # Create session for new target
        session_manager.get_session(new_target)
        
        return jsonify({
            "success": True,
            "message": f"Default target set to: {new_target}",
            "target": new_target
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route("/renew", methods=["GET", "POST"])
def renew_cookies():
    """Force renew cookies for a target"""
    try:
        target = request.args.get("target") or request.json.get("target")
        
        if not target:
            target = CONFIG["DEFAULT_TARGET"]
        
        if not target.startswith(("http://", "https://")):
            target = "https://" + target
        
        # Get session and renewer
        session = session_manager.get_session(target)
        renewer = session_manager.renewers.get(target)
        
        if not renewer:
            renewer = Renewer(target)
            session_manager.renewers[target] = renewer
        
        result = renewer.renew(session)
        
        return jsonify({
            "success": True,
            "target": target,
            "renewing": result["status"],
            "reason": result["reason"]
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route("/status", methods=["GET"])
def status():
    """Get proxy status"""
    return jsonify({
        "success": True,
        "status": "running",
        "default_target": CONFIG["DEFAULT_TARGET"],
        "active_sessions": list(session_manager.sessions.keys()),
        "cache_dir": CONFIG["CACHE_DIR"],
        "headless": CONFIG["HEADLESS"],
        "cfsession_available": CFSESSION_AVAILABLE
    })

@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "timestamp": time.time()
    })

# ============================================================
# ERROR HANDLERS
# ============================================================

@app.errorhandler(404)
def not_found(error):
    return jsonify({
        "success": False,
        "error": "Endpoint not found"
    }), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({
        "success": False,
        "error": "Internal server error"
    }), 500

# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("🚀 DriveHub Universal Proxy")
    logger.info("=" * 60)
    logger.info(f"Default Target: {CONFIG['DEFAULT_TARGET']}")
    logger.info(f"Cache Directory: {CONFIG['CACHE_DIR']}")
    logger.info(f"Headless Mode: {CONFIG['HEADLESS']}")
    logger.info(f"CFSession Available: {CFSESSION_AVAILABLE}")
    logger.info("=" * 60)
    logger.info(f"Server running on http://{CONFIG['HOST']}:{CONFIG['PORT']}")
    logger.info("=" * 60)
    
    app.run(
        host=CONFIG["HOST"],
        port=CONFIG["PORT"],
        debug=CONFIG["DEBUG"],
        threaded=True
    )
