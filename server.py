"""
Simple HTTP server to serve landing page and route to Streamlit
"""

from http.server import SimpleHTTPRequestHandler, HTTPServer
import os
import subprocess
import threading
import time
import webbrowser

PORT = 8000
STREAMLIT_PORT = 8506


class Handler(SimpleHTTPRequestHandler):
    def do_GET(self):
        """Handle GET requests"""
        # Route root to landing.html
        if self.path == "/" or self.path == "/index.html":
            self.path = "/landing.html"

        # API redirect to Streamlit
        if self.path == "/app":
            self.send_response(302)
            self.send_header("Location", f"http://localhost:{STREAMLIT_PORT}")
            self.end_headers()
            return

        # Serve static files
        return super().do_GET()

    def log_message(self, format, *args):
        """Log requests"""
        print(f"[{self.client_address[0]}] {format % args}")


def start_streamlit():
    """Start Streamlit in background"""
    print(f"Starting Streamlit on port {STREAMLIT_PORT}...")
    subprocess.Popen([
        "python", "-m", "streamlit", "run", "app_modern.py",
        "--server.port", str(STREAMLIT_PORT),
        "--logger.level", "error"
    ])
    time.sleep(3)
    print(f"[OK] Streamlit started on http://localhost:{STREAMLIT_PORT}")


def start_http_server():
    """Start HTTP server"""
    print(f"Starting HTTP server on port {PORT}...")
    server = HTTPServer(("localhost", PORT), Handler)
    print(f"[OK] Server running on http://localhost:{PORT}")
    print("\nAccess:")
    print(f"  Landing page: http://localhost:{PORT}")
    print(f"  OSINT App: http://localhost:{STREAMLIT_PORT}")
    print(f"  Or click: http://localhost:{PORT}/app")
    print("\nPress Ctrl+C to stop\n")
    server.serve_forever()


if __name__ == "__main__":
    # Start Streamlit in background
    streamlit_thread = threading.Thread(target=start_streamlit, daemon=True)
    streamlit_thread.start()

    # Start HTTP server
    try:
        start_http_server()
    except KeyboardInterrupt:
        print("\n\nShutting down...")
        exit(0)
