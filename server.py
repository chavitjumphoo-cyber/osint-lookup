"""
Simple HTTP server to serve landing page and route to Streamlit
"""

from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import subprocess
import sys
from urllib.parse import urlsplit

PORT = 8000
STREAMLIT_PORT = 8506
ROOT = Path(__file__).resolve().parent
PUBLIC_FILES = {"/landing.html", "/features.html", "/tools.html", "/about.html"}


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("directory", str(ROOT))
        super().__init__(*args, **kwargs)

    def send_head(self):
        """Apply the same public-file allowlist to GET and HEAD requests."""
        path = urlsplit(self.path).path
        # Route root to landing.html
        if path in ("/", "/index.html"):
            path = "/landing.html"

        # API redirect to Streamlit
        if path == "/app":
            self.send_response(302)
            self.send_header("Location", f"http://localhost:{STREAMLIT_PORT}")
            self.end_headers()
            return

        if path not in PUBLIC_FILES:
            self.send_error(404, "File not found")
            return None
        self.path = path
        return super().send_head()

    def log_message(self, format, *args):
        """Log requests"""
        print(f"[{self.client_address[0]}] {format % args}")


def start_streamlit():
    """Start Streamlit in background"""
    print(f"Starting Streamlit on port {STREAMLIT_PORT}...")
    return subprocess.Popen([
        sys.executable, "-m", "streamlit", "run", "app_modern.py",
        "--server.port", str(STREAMLIT_PORT),
        "--server.address", "127.0.0.1",
        "--server.headless", "true",
        "--browser.gatherUsageStats", "false",
        "--logger.level", "error"
    ], cwd=ROOT)


def start_http_server():
    """Start HTTP server"""
    print(f"Starting HTTP server on port {PORT}...")
    server = ThreadingHTTPServer(("localhost", PORT), Handler)
    print(f"[OK] Server running on http://localhost:{PORT}")
    print("\nAccess:")
    print(f"  Landing page: http://localhost:{PORT}")
    print(f"  OSINT App: http://localhost:{STREAMLIT_PORT}")
    print(f"  Or click: http://localhost:{PORT}/app")
    print("\nPress Ctrl+C to stop\n")
    try:
        server.serve_forever()
    finally:
        server.server_close()


if __name__ == "__main__":
    process = start_streamlit()

    # Start HTTP server
    try:
        start_http_server()
    except KeyboardInterrupt:
        print("\n\nShutting down...")
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
