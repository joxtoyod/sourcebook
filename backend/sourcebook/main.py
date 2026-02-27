from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from sourcebook.config import settings
from sourcebook.database import (
    get_requirements, init_db, list_versions, restore_version, update_requirements,
)
from sourcebook.models import (
    DiagramRestoreOut, DiagramVersionListOut, DiagramVersionOut, RequirementsIn,
)
from sourcebook.ws_handler import handle_websocket


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(title="Sourcebook API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:4173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    await handle_websocket(websocket)


@app.get("/api/requirements")
async def get_requirements_route():
    text = await get_requirements()
    return {"requirements_text": text}


@app.put("/api/requirements")
async def put_requirements(body: RequirementsIn):
    text = body.requirements_text.strip()
    await update_requirements(text)
    return {"requirements_text": text}


@app.get("/api/versions", response_model=DiagramVersionListOut)
async def get_versions():
    rows = await list_versions()
    return DiagramVersionListOut(versions=[DiagramVersionOut(**r) for r in rows])


@app.post("/api/versions/{version_id}/restore", response_model=DiagramRestoreOut)
async def post_restore_version(version_id: str):
    result = await restore_version(version_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Version not found")
    nodes, edges, groups = result
    return DiagramRestoreOut(nodes=nodes, edges=edges, groups=groups)


@app.get("/api/project-root")
async def get_project_root():
    import shutil
    editor = "vscode" if shutil.which("code") else ("cursor" if shutil.which("cursor") else "vscode")
    return {"project_root": settings.project_root, "editor": editor}


@app.get("/api/file")
async def get_file(path: str):
    if not path:
        raise HTTPException(status_code=400, detail="path is required")
    # Strip optional :line suffix before reading
    file_part = path.split(":")[0] if ":" in path else path
    root = Path(settings.project_root).resolve()
    target = (root / file_part).resolve()
    # Security: prevent path traversal
    if not str(target).startswith(str(root)):
        raise HTTPException(status_code=400, detail="Invalid path")
    if not target.exists():
        raise HTTPException(status_code=404, detail="File not found")
    if not target.is_file():
        raise HTTPException(status_code=400, detail="Path is not a file")
    try:
        content = target.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"content": content}


# Serve the built SvelteKit frontend — must be mounted last so API routes take priority.
_static_dir = Path(__file__).parent / "static"
if _static_dir.exists():
    app.mount("/", StaticFiles(directory=_static_dir, html=True), name="frontend")
