#!/usr/bin/env python3
"""
Simple internal web server for Ilana team dashboard
Run this to serve the dashboard on your local network
"""

import http.server
import socketserver
import os
import webbrowser
from pathlib import Path

# Configuration
PORT = 9999  # Using high port to avoid conflicts
DASHBOARD_DIR = Path(__file__).parent

class DashboardHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DASHBOARD_DIR, **kwargs)

def start_dashboard_server():
    """Start the internal dashboard server"""
    
    print("🚀 Starting Ilana Team Dashboard Server")
    print(f"📁 Serving from: {DASHBOARD_DIR}")
    print(f"🌐 Port: {PORT}")
    
    # Check if dashboard file exists
    dashboard_file = DASHBOARD_DIR / "team-dashboard-intranet.html"
    if not dashboard_file.exists():
        print(f"❌ Dashboard file not found: {dashboard_file}")
        print("Make sure team-dashboard-intranet.html is in the same directory")
        return
    
    try:
        with socketserver.TCPServer(("", PORT), DashboardHandler) as httpd:
            print(f"✅ Dashboard server running at:")
            print(f"   Local: http://localhost:{PORT}/team-dashboard-intranet.html")
            print(f"   Network: http://{get_local_ip()}:{PORT}/team-dashboard-intranet.html")
            print()
            print("📋 Share this URL with your team for internal access")
            print("🛑 Press Ctrl+C to stop the server")
            print()
            
            # Auto-open in browser
            webbrowser.open(f"http://localhost:{PORT}/team-dashboard-intranet.html")
            
            # Start serving
            httpd.serve_forever()
            
    except KeyboardInterrupt:
        print("\n🛑 Dashboard server stopped")
    except OSError as e:
        if "Address already in use" in str(e):
            print(f"❌ Port {PORT} is already in use")
            print("Try a different port or stop the existing server")
        else:
            print(f"❌ Server error: {e}")

def get_local_ip():
    """Get local IP address for network sharing"""
    import socket
    try:
        # Connect to a dummy address to get local IP
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except:
        return "localhost"

if __name__ == "__main__":
    start_dashboard_server()