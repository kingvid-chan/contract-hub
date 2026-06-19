"""FastAPI application entry point.

Mounts the React SPA under /projects/contract-hub/ and API routes under
/projects/contract-hub/api/.  Handles SPA fallback so client-side routing
works on page reload.
"""

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse

from backend.config import BASE_PATH, API_PREFIX, CORS_ORIGINS, UPLOAD_DIR, HOST, PORT
from backend.database import init_db
from backend.middleware import CacheControlMiddleware
from backend.routers import users, contracts, attachments

# ── Application ──────────────────────────────────────

app = FastAPI(
    title="Contract Hub",
    version="0.0.3",
    docs_url=f"{API_PREFIX}/docs",
    openapi_url=f"{API_PREFIX}/openapi.json",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Cache control (must be first in middleware stack to set response headers)
app.add_middleware(CacheControlMiddleware)


# ── Health check ──────────────────────────────────────

@app.get(f"{BASE_PATH}/healthz")
def healthz():
    return {"status": "ok", "version": "0.0.3"}


# ── API routers ───────────────────────────────────────

app.include_router(users.router, prefix=API_PREFIX)
app.include_router(contracts.router, prefix=API_PREFIX)
app.include_router(attachments.router, prefix=API_PREFIX)


# ── Static files & SPA fallback ───────────────────────

DIST_DIR = Path(__file__).resolve().parent.parent / "frontend" / "dist"


@app.get(f"{BASE_PATH}/{{full_path:path}}")
async def serve_spa(full_path: str = ""):
    """Serve React SPA — return index.html for non-API routes."""
    if full_path.startswith("api/"):
        # Should be handled by API routers; if it reaches here it's a 404
        from fastapi.responses import JSONResponse
        return JSONResponse({"detail": "Not found"}, status_code=404)

    # Try to serve the requested static file
    file_path = DIST_DIR / full_path
    if file_path.is_file() and not full_path.endswith(".html"):
        return FileResponse(file_path)

    # SPA fallback — serve index.html for all other paths
    index_path = DIST_DIR / "index.html"
    if index_path.is_file():
        return HTMLResponse(
            content=index_path.read_text(encoding="utf-8"),
            headers={"Cache-Control": "no-cache"},
        )

    return HTMLResponse(
        content="<html><body><h1>Frontend not built</h1><p>Run <code>cd frontend && npm run build</code></p></body></html>",
        status_code=503,
    )


# ── Startup ──────────────────────────────────────────

@app.on_event("startup")
def on_startup():
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    init_db()


# ── Direct run ───────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=HOST, port=PORT)
