"""Small application/agent client for the authenticated shared-memory API."""

import json
import time
from urllib.error import HTTPError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


class SharedRequestError(RuntimeError):
    def __init__(self, status, body):
        super().__init__(body.get("error", "Shared-memory request failed"))
        self.status, self.body = status, body


class SharedMemoryClient:
    def __init__(self, base_url, token, timeout=15):
        parsed = urlparse(base_url)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.netloc
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("Use an HTTP(S) service URL without embedded credentials.")
        self.url, self._token, self.timeout = base_url.rstrip("/"), token, timeout

    def call(self, path, **body):
        if not path.startswith("/v1/") or "?" in path or "#" in path:
            raise ValueError("Use a shared-memory API path.")
        request = Request(
            self.url + path,
            data=json.dumps(body, allow_nan=False).encode(),
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer " + self._token,
            },
        )
        try:
            response = urlopen(request, timeout=self.timeout)
        except HTTPError as error:
            body = json.loads(error.read())
            raise SharedRequestError(error.code, body) from None
        with response:
            return json.loads(response.read())

    def add_event(self, **event):
        return self.call("/v1/events", **event)

    def wait_ready(self, event_id, timeout=30):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            receipt = self.call("/v1/events/status", eid=event_id)
            if receipt["status"] == "ready":
                return receipt
            if receipt["status"] in {"failed", "withdrawn", "redacted", "needs_review"}:
                raise SharedRequestError(
                    409,
                    dict(error="Event is not usable semantic memory", receipt=receipt),
                )
            time.sleep(0.05)
        raise TimeoutError("Event receipt was saved, but memory readiness timed out.")

    def recall(self, query, subject, predicate=None, scope=None):
        return self.call(
            "/v1/recall",
            query=query,
            subject=subject,
            predicate=predicate,
            scope=scope or {},
        )

    def handoff(self, work_ids):
        return self.call("/v1/handoff", work_ids=work_ids)

    def context(self, **request):
        return self.call("/v1/context", **request)

    def validate_context(self, context_token):
        return self.call("/v1/context/validate", context_token=context_token)

    def generate_current(self, request, generate, max_rebuilds=2):
        """Generate without locks, then check current memory before returning.

        `generate` must only produce a response; external side effects require
        their own conditional execution contract and must not be retried here.
        """
        if type(max_rebuilds) is not int or not 0 <= max_rebuilds <= 2:
            raise ValueError("Use zero to two rebuild attempts.")
        for _ in range(max_rebuilds+1):
            context = self.context(**request)
            if context["status"] != "ready":
                return dict(status=context["status"], context=context)
            response = generate(context)
            if self.validate_context(context["context_token"])["valid"]:
                return dict(status="ready", response=response, context=context)
        return dict(status="context_changed")
