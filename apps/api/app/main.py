from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles

from app.api.routes import router
from app.core.config import get_settings
from app.core.db import engine, init_db
from app.models import cv_upload as _cv_upload  # noqa: F401 — register table
from app.models import job as _job  # noqa: F401 — register table
from app.models import resource_feedback as _resource_feedback  # noqa: F401
from app.services.jobs import seed_sample_jobs
from app.services.seo import (
    build_robots_txt,
    build_role_page_html,
    build_roles_index_html,
    build_sitemap_xml,
    title_from_slug,
)
from sqlmodel import Session

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


@asynccontextmanager
async def lifespan(_: FastAPI):
    try:
        init_db()
        with Session(engine) as session:
            seed_sample_jobs(session)
    except Exception as exc:
        # Allow API to boot even if DB is temporarily unavailable
        print(f"[lernyra] DB init warning: {exc}")
    yield


settings = get_settings()

app = FastAPI(
    title="Lernyra API",
    description="Job + learning insights aggregator",
    version="0.1.0",
    lifespan=lifespan,
)

_cors_origins = settings.cors_origins or ["*"]
# Browsers reject Allow-Origin: * together with credentials.
_cors_credentials = _cors_origins != ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=_cors_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")


@app.get("/api")
def api_root() -> dict:
    return {"name": "lernyra-api", "docs": "/docs"}


@app.get("/robots.txt", response_class=PlainTextResponse)
def robots_txt() -> str:
    return build_robots_txt(settings.site_url)


@app.get("/sitemap.xml")
def sitemap_xml() -> Response:
    return Response(
        content=build_sitemap_xml(settings.site_url),
        media_type="application/xml",
        headers={"Cache-Control": "public, max-age=3600"},
    )


@app.get("/roles", response_class=HTMLResponse)
def roles_index() -> Response:
    return Response(
        content=build_roles_index_html(settings.site_url),
        media_type="text/html; charset=utf-8",
        headers={"Cache-Control": "public, max-age=3600"},
    )


@app.get("/roles/{slug}", response_class=HTMLResponse)
def role_seo_page(slug: str) -> str:
    title = title_from_slug(slug)
    if not title:
        raise HTTPException(status_code=404, detail="Role not found")
    return build_role_page_html(settings.site_url, title)


# Exact bytes of the file downloaded from Search Console. No trailing newline.
_GOOGLE_VERIFY_NAME = "googlef3c3eb3feaeda967.html"
_GOOGLE_VERIFY_BODY = b"google-site-verification: googlef3c3eb3feaeda967.html"


@app.api_route(f"/{_GOOGLE_VERIFY_NAME}", methods=["GET", "HEAD"])
def google_site_verification_file() -> Response:
    return Response(
        content=_GOOGLE_VERIFY_BODY,
        media_type="text/html",
        headers={"Cache-Control": "public, max-age=300"},
    )


@app.api_route("/google{code}.html", methods=["GET", "HEAD"])
def google_site_verification_missing(code: str) -> Response:
    # Search Console also requests a filename that was never uploaded.
    # A 200 for that probe means it cannot tell the real file exists.
    raise HTTPException(status_code=404, detail="Not found")


def _spa_html(noindex: bool = False) -> Response:
    # Always revalidate HTML so deploys pick up new hashed JS/CSS immediately.
    index = STATIC_DIR / "index.html"
    headers = {
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Pragma": "no-cache",
    }
    token = (settings.google_site_verification or "").strip()
    if not token and not noindex:
        return FileResponse(index, headers=headers)

    html = index.read_text(encoding="utf-8")
    if token and 'name="google-site-verification"' not in html:
        meta = f'<meta name="google-site-verification" content="{token}" />'
        html = html.replace("</head>", f"    {meta}\n  </head>", 1)
    if noindex:
        # The shell is the homepage. Private routes must say noindex before JS runs.
        html = html.replace(
            'content="index,follow,max-image-preview:large,max-snippet:-1"',
            'content="noindex, nofollow"',
            1,
        )
    return Response(content=html, media_type="text/html; charset=utf-8", headers=headers)


if STATIC_DIR.is_dir():
    assets_dir = STATIC_DIR / "assets"
    if assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

    @app.get("/")
    def spa_index() -> FileResponse:
        return _spa_html()

    @app.api_route("/{full_path:path}", methods=["GET", "HEAD"])
    def spa_fallback(full_path: str) -> Response:
        candidate = (STATIC_DIR / full_path).resolve()
        if candidate.is_file() and str(candidate).startswith(str(STATIC_DIR.resolve())):
            # Fingerprinted /assets/* can be cached; other static files stay short-lived.
            headers = {}
            if "/assets/" in str(candidate) or candidate.parent == assets_dir:
                headers["Cache-Control"] = "public, max-age=31536000, immutable"
            return FileResponse(candidate, headers=headers)
        # Unknown URLs must be real 404s. A 200 for a missing page makes
        # Search Console treat the verification file as missing too.
        if full_path.strip("/") == "learning-list":
            return _spa_html(noindex=True)
        raise HTTPException(status_code=404, detail="Not found")
else:

    @app.get("/")
    def root() -> dict:
        return {"name": "lernyra-api", "docs": "/docs", "hint": "UI not bundled"}
