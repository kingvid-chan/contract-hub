"""FastAPI middleware — cache control headers, CORS."""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class CacheControlMiddleware(BaseHTTPMiddleware):
    """Set appropriate Cache-Control headers based on response content type.

    - HTML files: Cache-Control: no-cache (force revalidation every time)
    - Static assets (JS/CSS/images): Cache-Control: public, max-age=31536000
    - API responses: no-store (don't cache API data)
    """

    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)

        path = request.url.path
        content_type = response.headers.get("content-type", "")

        # Check path-based rules first (file extension takes priority)
        if any(
            path.endswith(ext) for ext in (".js", ".css", ".png", ".jpg", ".jpeg", ".svg", ".ico", ".woff", ".woff2")
        ):
            # Static assets — long cache with version token invalidation
            response.headers["Cache-Control"] = "public, max-age=31536000"
        elif path.endswith(".html") or (
            "text/html" in content_type and not path.startswith("/projects/contract-hub/api/")
        ):
            # HTML documents — no-cache so browser always revalidates
            response.headers["Cache-Control"] = "no-cache"
        elif path.startswith("/projects/contract-hub/api/"):
            # API responses — no caching
            response.headers["Cache-Control"] = "no-store"

        return response
