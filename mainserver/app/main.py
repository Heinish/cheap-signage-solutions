from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from . import config
from .db import init_db
from .routers import auth, devices, pairing, rooms, urls, ws

app = FastAPI(title="CSS Signage Mainserver")

app.include_router(auth.router)
app.include_router(devices.router)
app.include_router(rooms.router)
app.include_router(urls.router)
app.include_router(pairing.router)
app.include_router(ws.router)


@app.on_event("startup")
def on_startup():
    init_db()


@app.get("/api/health")
def health():
    return {"status": "healthy"}


FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"

if FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

    @app.get("/{full_path:path}")
    def spa_fallback(full_path: str):
        index = FRONTEND_DIST / "index.html"
        return FileResponse(index)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host=config.HOST, port=config.PORT, reload=False)
