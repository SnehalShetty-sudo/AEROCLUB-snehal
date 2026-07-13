"""
run_app.py — Standalone Desktop Wrapper for the Drone Dashboard
"""

import sys
import os
import logging
import time

# Auto-install pywebview if it doesn't exist
try:
    import webview
except ImportError:
    print("pywebview is not installed. Installing it now...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pywebview"])
    import webview

# Import the server start function
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dashboard.server import start_server_in_thread, DASHBOARD_PORT

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    
    print("Starting dashboard server in the background...")
    server_thread = start_server_in_thread()
    
    # Wait briefly for server startup
    time.sleep(0.5)
    
    url = f"http://127.0.0.1:{DASHBOARD_PORT}"
    print(f"Opening desktop frame for: {url}")
    
    # Open the native desktop window wrapping the web app
    webview.create_window(
        "Drone Ground Control System",
        url,
        width=1366,
        height=768,
        resizable=True,
        min_size=(1024, 768)
    )
    webview.start()
