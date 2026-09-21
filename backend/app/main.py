from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .routers import dashboards, studies, weeks

BASE_DIR = Path(__file__).resolve().parent.parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"

app = FastAPI(title="Jeeny Insights Hub API")

app.include_router(weeks.router)
app.include_router(studies.router)
app.include_router(dashboards.router)

app.mount("/static", StaticFiles(directory=FRONTEND_DIR / "static"), name="static")

PAGES = {
    "/": "index.html",
    "/studies": "studies.html",
    "/dashboards": "dashboards.html",
}


def _serve_page(filename: str):
    return FileResponse(FRONTEND_DIR / filename)


for route_path, page_file in PAGES.items():
    app.get(route_path, include_in_schema=False)(
        lambda page_file=page_file: _serve_page(page_file)
    )
