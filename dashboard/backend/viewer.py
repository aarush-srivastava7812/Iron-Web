"""Viewer access, separate from the server-only publication grant."""
import hashlib
import hmac
import ipaddress
import os
import time

from fastapi.responses import JSONResponse

COOKIE = "ironweb_viewer"
TTL = 8 * 60 * 60


def local_request(request):
    try:
        peer = ipaddress.ip_address(request.client.host).is_loopback
    except (ValueError, AttributeError):
        peer = False
    return bool(peer and request.url.hostname in {"localhost", "127.0.0.1", "::1"}
                and not any(k in request.headers for k in ("forwarded", "x-forwarded-for", "x-forwarded-host")))


def configuration(request):
    secret = os.getenv("DASHBOARD_VIEWER_TOKEN", "")
    if secret and len(secret) < 32:
        return secret, "Configure DASHBOARD_VIEWER_TOKEN with at least 32 characters."
    if not secret and not local_request(request):
        return secret, "Remote dashboard access requires DASHBOARD_VIEWER_TOKEN."
    return secret, None


def signature(secret, issued):
    return hmac.new(secret.encode(), ("ironweb-viewer:" + issued).encode(), hashlib.sha256).hexdigest()


def equal(first, second):
    return hmac.compare_digest(first.encode(), second.encode())


def authorized(request, secret):
    bearer = request.headers.get("authorization", "")
    if bearer.startswith("Bearer ") and equal(bearer[7:], secret):
        return True
    cookie = request.cookies.get(COOKIE, "")
    issued, sep, proof = cookie.partition(".")
    if not sep or not issued.isdigit():
        return False
    return 0 <= time.time() - int(issued) < TTL and equal(proof, signature(secret, issued))


def gate(request):
    secret, error = configuration(request)
    if error:
        return JSONResponse({"detail": error}, status_code=503)
    if secret and not authorized(request, secret):
        return JSONResponse({"detail": "Viewer sign-in required."}, status_code=401)
    return None


async def sign_in(request):
    secret, error = configuration(request)
    if error:
        return JSONResponse({"detail": error}, status_code=503)
    allowed = {x.strip() for x in os.getenv("DASHBOARD_CORS_ORIGINS", "http://127.0.0.1:5174,http://localhost:5174").split(",")}
    allowed.add(str(request.base_url).rstrip("/"))
    if request.headers.get("origin") not in allowed:
        return JSONResponse({"detail": "Open sign-in from the configured dashboard origin."}, status_code=403)
    body = b""
    async for chunk in request.stream():
        body += chunk
        if len(body) > 2048:
            return JSONResponse({"detail": "Invalid viewer credential."}, status_code=400)
    import json
    try:
        supplied = json.loads(body).get("secret", "")
    except (ValueError, AttributeError):
        supplied = None
    if not isinstance(supplied, str) or (secret and not equal(supplied, secret)):
        return JSONResponse({"detail": "Invalid viewer credential."}, status_code=401)
    if not secret:
        return JSONResponse({"status": "local"})
    if request.url.scheme != "https" and not local_request(request):
        return JSONResponse({"detail": "Viewer sessions require HTTPS outside loopback."}, status_code=400)
    issued = str(int(time.time()))
    response = JSONResponse({"status": "signed_in"})
    secure = request.url.scheme == "https"
    response.set_cookie(COOKIE, issued + "." + signature(secret, issued), httponly=True,
                        secure=secure, samesite="none" if secure else "lax", max_age=TTL, path="/")
    return response
