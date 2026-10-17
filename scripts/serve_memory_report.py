"""Serve only explicitly public report artifacts, never credentials/vector data."""

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import mimetypes
from pathlib import Path
from urllib.parse import urlparse


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--port", type=int, default=1306)
    args = parser.parse_args()
    root = args.report.resolve()
    public = {
        "index.html",
        "graph.json",
        "results.json",
        "verification.json",
        "browser-proof.json",
        "README.md",
        "IMPLEMENTATION.md",
        "graph.png",
        "walkthrough.webm",
    }

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_GET(self):
            name = urlparse(self.path).path
            name = "index.html" if name == "/" else name.removeprefix("/")
            if name not in public or not (root / name).is_file():
                return self.send_error(404)
            content = (root / name).read_bytes()
            self.send_response(200)
            self.send_header(
                "Content-Type",
                mimetypes.guess_type(name)[0] or "application/octet-stream",
            )
            self.send_header("Content-Length", str(len(content)))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(content)

    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"Public report preview: http://127.0.0.1:{args.port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
