"""Authenticated local API for receipt-first shared graph memory."""

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from urllib.parse import urlparse

from memory.shared.service import PendingMemory, SharedMemoryService
from memory.shared.interpreter import TravelInterpreter, HostedClaimInterpreter


def handler_for(service, web_root=None):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            # Avoid recording credentials, source messages or URL identifiers.
            pass

        def send(self, body, status=200, content_type="application/json"):
            encoded = (
                body
                if isinstance(body, bytes)
                else json.dumps(body, allow_nan=False).encode()
            )
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(encoded)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(encoded)

        def do_GET(self):
            if self.path == "/health":
                return self.send({"status": "online"})
            if self.path in {"/", "/index.html"} and web_root:
                return self.send(
                    (Path(web_root) / "index.html").read_bytes(),
                    content_type="text/html; charset=utf-8",
                )
            self.send({"error": "Unknown endpoint"}, 404)

        def do_POST(self):
            try:
                authorization = self.headers.get("Authorization", "")
                if not authorization.startswith("Bearer "):
                    raise PermissionError("Authentication required.")
                principal = service.authenticate(authorization[7:])
                origin = self.headers.get("Origin")
                if origin and urlparse(origin).netloc != self.headers.get("Host"):
                    raise PermissionError("Cross-origin requests are unavailable.")
                if (
                    self.headers.get("Content-Type", "").split(";")[0]
                    != "application/json"
                ):
                    return self.send({"error": "JSON content type required"}, 415)
                size = int(self.headers.get("Content-Length", "0"))
                if not 1 <= size <= 1048576:
                    return self.send(
                        {"error": "Request size must be between 1 byte and 1 MiB"}, 413
                    )

                def invalid(value):
                    raise ValueError("Nonfinite JSON number: " + value)

                body = json.loads(self.rfile.read(size), parse_constant=invalid)
                if not isinstance(body, dict):
                    raise ValueError("Request must be an object.")
                path = urlparse(self.path).path
                routes = {
                    "/v1/events": service.submit,
                    "/v1/events/status": service.receipt,
                    "/v1/events/retry": service.retry,
                    "/v1/events/withdraw": service.withdraw,
                    "/v1/events/forget": service.forget,
                    "/v1/history": service.history,
                    "/v1/identity": service.identity,
                    "/v1/context": service.context,
                    "/v1/context/validate": service.validate_context,
                    "/v1/work/list": service.work_list,
                    "/v1/recall": service.recall,
                    "/v1/recall-path": service.recall_path,
                    "/v1/search": service.search,
                    "/v1/work": service.record_work,
                    "/v1/work/claim": service.claim_work,
                    "/v1/work/complete": service.complete_work,
                    "/v1/handoff": service.handoff,
                }
                if path == "/v1/notifications":
                    if body:
                        raise ValueError("Notification poll takes an empty object.")
                    result = service.journal.notices(principal.tenant, principal.actor)
                elif path == "/v1/notifications/ack":
                    if set(body) != {"id"}:
                        raise ValueError("Acknowledgment requires one notification ID.")
                    service.journal.acknowledge(
                        principal.tenant, principal.actor, body["id"]
                    )
                    result = {"acknowledged": True}
                elif path in routes:
                    result = (
                        routes[path](principal, body)
                        if path == "/v1/events"
                        else routes[path](principal, **body)
                    )
                else:
                    return self.send({"error": "Unknown endpoint"}, 404)
                self.send(result, 202 if path == "/v1/events" else 200)
            except PendingMemory as error:
                self.send(
                    {
                        "status": "pending_memory",
                        "error": str(error),
                        "receipts": error.receipts,
                    },
                    409,
                )
            except PermissionError as error:
                self.send(
                    {"error": str(error)},
                    401
                    if "uthentic" in str(error) or "credentials" in str(error)
                    else 403,
                )
            except (ValueError, TypeError) as error:
                self.send({"error": str(error)}, 400)
            except RuntimeError:
                self.send(
                    {
                        "error": "Operation could not be committed; inspect event status or review task ownership."
                    },
                    409,
                )
            except Exception:
                self.send(
                    {"error": "Internal failure; no completion is asserted."}, 500
                )

    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--port", type=int, default=3351)
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    interpretation = TravelInterpreter() if config.get("travel_interpreter") else None
    if config.get("hosted_interpreter"):
        import os
        from openai import OpenAI

        settings = config["hosted_interpreter"]
        key = os.getenv(settings.get("api_key_env", "NVIDIA_API_KEY"))
        if not key:
            raise ValueError(
                "Configured interpreter credential is unavailable; no fallback inference was asserted."
            )
        interpretation = HostedClaimInterpreter(
            OpenAI(
                api_key=key, base_url=settings["base_url"], timeout=45, max_retries=0
            ),
            settings["model"],
        )
    context_runtime = None
    if config.get("context"):
        from memory.context.runtime import runtime_from_config
        context_runtime = runtime_from_config(config["context"], args.config.resolve().parent)
    service = SharedMemoryService(
        config["runtime"],
        config["principals"],
        namespace=config["namespace"],
        interpreter=interpretation,
        context_runtime=context_runtime,
    )
    server = ThreadingHTTPServer(
        ("127.0.0.1", args.port),
        handler_for(service, Path(__file__).parent / "web/shared"),
    )
    print(
        f"Shared memory listening at http://127.0.0.1:{args.port}; authenticated requests required.",
        flush=True,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        service.close()


if __name__ == "__main__":
    main()
