#!/usr/bin/env python3
"""
Aegis 3D Command Center Custom HTTP Server with Strict No-Cache Headers
Author: Aegis
"""

import http.server, socketserver, os

PORT = 8590
DIRECTORY = "/home/moos/dev_ws/aegis/science_demo"

class NoCacheHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

    def end_headers(self):
        # Force strict no-cache headers for all static files (GIF, HTML, JS, CSS)
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        self.send_header("Access-Control-Allow-Origin", "*")
        super().end_headers()

if __name__ == "__main__":
    os.chdir(DIRECTORY)
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", PORT), NoCacheHandler) as httpd:
        print(f"🚀 Aegis No-Cache HTTP Server serving at http://0.0.0.0:{PORT}/...")
        httpd.serve_forever()
