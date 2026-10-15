"""Local memory dashboard and JSON API. Report values come only from saved verified runs."""

from __future__ import annotations
import json
import logging
import sys
import time
from pathlib import Path
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse
from memory.engine import MemoryEngine
from memory.models import EngineStorageError

ROOT = Path(__file__).resolve().parent
logger = logging.getLogger(__name__)
_ENGINE = None
_START_TIME = time.time()


def get_engine():
    global _ENGINE
    if _ENGINE is None:
        _ENGINE = MemoryEngine()
    return _ENGINE


def load_verified_reports(directory=None):
    directory = Path(directory) if directory is not None else ROOT / "data/results"
    reports, invalid = [], []
    for path in sorted(directory.rglob("*_summary.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if (
                data.get("protocol") == "local_retrieval_v2"
                and isinstance(data.get("evaluation"), dict)
                and len(data.get("fingerprint", "")) == 64
            ):
                reports.append(data)
        except (ValueError, OSError, AttributeError) as error:
            logger.warning("Unreadable evaluation report %s: %s", path.name, error)
            invalid.append(path.name)
    return dict(
        status="available" if reports else "no_verified_results",
        reports=reports,
        unreadable_reports=invalid,
    )


class IronWebHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT / "web"), **kwargs)

    def _send_json(self, data, status=200):
        encoded = json.dumps(data, ensure_ascii=False, allow_nan=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(encoded)

    def do_GET(self):
        path = urlparse(self.path).path
        try:
            if path == "/api/status":
                engine = get_engine()
                self._send_json(
                    dict(
                        timestamp=int(time.time()),
                        server=dict(
                            status="ONLINE", uptime_sec=int(time.time() - _START_TIME)
                        ),
                        device=engine.get_device_status().model_dump(),
                        storage=engine.storage_status(),
                    )
                )
            elif path in {"/api/results", "/api/ablations"}:
                self._send_json(load_verified_reports())
            elif path == "/api/competitors":
                self._send_json(dict(status="no_verified_comparison", comparisons=[]))
            elif path.startswith("/api/"):
                self._send_json({"error": "Endpoint not found"}, 404)
            else:
                return super().do_GET()
        except Exception:
            logger.exception("GET request failed")
            self._send_json(
                {"error": "Request failed; see the server log for details."}, 500
            )

    def do_POST(self):
        path = urlparse(self.path).path
        if path not in {
            "/api/add",
            "/api/search",
            "/api/recall",
            "/api/recall-path",
            "/api/claim",
            "/api/work",
            "/api/handoff",
            "/api/complete-work",
        }:
            return self._send_json({"error": "Endpoint not found"}, 404)
        origin = self.headers.get("Origin")
        if origin and urlparse(origin).netloc != self.headers.get("Host"):
            return self._send_json(
                {"error": "Cross-origin writes are unavailable."}, 403
            )
        if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
            return self._send_json(
                {"error": "Content-Type must be application/json."}, 415
            )
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if size < 1 or size > 1_048_576:
                return self._send_json(
                    {"error": "Request body must contain at most 1 MiB of JSON."}, 413
                )

            def invalid_number(value):
                raise ValueError("JSON numbers must be finite.")

            body = json.loads(
                self.rfile.read(size).decode("utf-8"), parse_constant=invalid_number
            )
            if not isinstance(body, dict):
                raise ValueError("Request must be a JSON object.")
            if path in {
                "/api/recall",
                "/api/recall-path",
                "/api/claim",
                "/api/work",
                "/api/handoff",
                "/api/complete-work",
            }:
                methods = {
                    "/api/recall": get_engine().recall,
                    "/api/recall-path": get_engine().recall_path,
                    "/api/claim": get_engine().inspect_claim,
                    "/api/work": get_engine().record_work,
                    "/api/handoff": get_engine().handoff,
                    "/api/complete-work": get_engine().complete_work,
                }
                self._send_json(dict(success=True, result=methods[path](**body)))
            elif path == "/api/search":
                allowed = {
                    "query",
                    "k",
                    "temporal_mode",
                    "query_time",
                    "retrieval_mode",
                    "document_ids",
                }
                if set(body) - allowed:
                    raise ValueError("Unknown search fields.")
                if not isinstance(body.get("query"), str) or not body["query"].strip():
                    raise ValueError("Query must be a nonempty string.")
                started = time.perf_counter()
                results = get_engine().search(**body)
                self._send_json(
                    dict(
                        query=body["query"],
                        count=len(results),
                        latency_ms=(time.perf_counter() - started) * 1000,
                        results=[r.model_dump() for r in results],
                    )
                )
            else:
                allowed = {
                    "content",
                    "metadata",
                    "entity_ids",
                    "timestamp",
                    "valid_from",
                    "valid_until",
                    "importance",
                    "memory_id",
                    "claims",
                    "source_info",
                }
                if set(body) - allowed:
                    raise ValueError("Unknown memory fields.")
                mid = get_engine().add(**body)
                self._send_json(dict(success=True, memory_id=mid), 201)
        except (ValueError, TypeError, UnicodeError) as error:
            self._send_json({"error": str(error)}, 400)
        except EngineStorageError as error:
            logger.exception("Storage operation failed")
            self._send_json(
                {
                    "error": "Storage operation failed.",
                    "rolled_back": error.rolled_back,
                },
                500,
            )
        except Exception:
            logger.exception("POST request failed")
            self._send_json(
                {"error": "Request failed; see the server log for details."}, 500
            )


def run_server(port=8080):
    global _ENGINE
    logging.basicConfig(level=logging.INFO)
    server = ThreadingHTTPServer(("127.0.0.1", port), IronWebHandler)
    logger.info("Memory dashboard: http://127.0.0.1:%s/", port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        if _ENGINE is not None:
            _ENGINE.close()
            _ENGINE = None


if __name__ == "__main__":
    run_server(int(sys.argv[1]) if len(sys.argv) > 1 else 8080)
