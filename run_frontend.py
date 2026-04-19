#!/usr/bin/env python
"""
Frontend development server for LinkedIn Content Generator SaaS
Serves static HTML/CSS/JS files with CORS headers
"""

import os
import sys
from pathlib import Path
from http.server import HTTPServer, SimpleHTTPRequestHandler
import json

# Change to frontend directory
frontend_dir = Path(__file__).parent / "frontend"
os.chdir(frontend_dir)

class CORSRequestHandler(SimpleHTTPRequestHandler):
    """HTTP handler with CORS headers"""
    
    def end_headers(self):
        # Add CORS headers to allow requests from backend
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate')
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def log_message(self, format, *args):
        # Custom logging
        print(f"[{self.log_date_time_string()}] {format % args}")

if __name__ == '__main__':
    port = int(os.getenv('FRONTEND_PORT', 3000))
    host = '0.0.0.0'
    
    server = HTTPServer((host, port), CORSRequestHandler)
    
    print("[INFO] ===== LinkedIn Content Generator - Frontend Server =====")
    print(f"[INFO] Server running at: http://localhost:{port}")
    print(f"[INFO] Landing page: http://localhost:{port}/index.html")
    print(f"[INFO] Dashboard: http://localhost:{port}/dashboard.html")
    print(f"[INFO] Backend API: http://localhost:8000/docs")
    print("[INFO]")
    print("[INFO] Press CTRL+C to stop")
    print("[INFO] =========================================================")
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[INFO] Server stopped")
        sys.exit(0)
