import os
import io
import json
import asyncio
import subprocess
import webbrowser
import tkinter as tk
from tkinter import filedialog
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import organize

try:
    from PIL import Image
    HAS_PILLOW = True
except ImportError:
    HAS_PILLOW = False

app = FastAPI(title="Project Time Capsule")

STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

active_sort_task = {"abort": False}

class ConfigUpdate(BaseModel):
    source_path: str
    target_path: str

class OpenFolderRequest(BaseModel):
    path: str

@app.get("/", response_class=HTMLResponse)
async def serve_dashboard():
    index_path = STATIC_DIR / "index.html"
    return HTMLResponse(content=index_path.read_text(encoding="utf-8"))

@app.get("/api/config")
async def get_config():
    return organize.load_config()

@app.post("/api/config")
async def update_config(payload: ConfigUpdate):
    src = str(Path(payload.source_path).resolve()) if payload.source_path.strip() else ""
    tgt = str(Path(payload.target_path).resolve()) if payload.target_path.strip() else ""
    updated = organize.save_config(src, tgt)
    return {"status": "ok", "config": updated}

@app.get("/api/browse")
async def browse_directory(initial_dir: str = ""):
    root = tk.Tk()
    root.withdraw()
    root.attributes('-topmost', True)
    selected = filedialog.askdirectory(initialdir=initial_dir or None)
    root.destroy()
    if selected:
        selected = str(Path(selected).resolve())
    return {"path": selected or None}

@app.get("/api/validate-path")
async def validate_path(path: str):
    if not path.strip():
        return {"exists": False, "file_count": 0}
    p = Path(path).resolve()
    exists = p.exists() and p.is_dir()
    count = 0
    if exists:
        try:
            count = len([f for f in p.rglob('*') if f.is_file() and not f.name.startswith('.')])
        except Exception:
            count = 0
    return {"exists": exists, "file_count": count}

@app.get("/api/incoming-files")
async def get_incoming_files(path: str, limit: int = 20):
    """Scans and returns incoming media captures with robust path resolution."""
    if not path.strip():
        return {"files": []}
    
    p = Path(path).resolve()
    if not p.exists() or not p.is_dir():
        return {"files": []}
    
    media_files = []
    try:
        for root, _, files in os.walk(p):
            for file in files:
                if file.startswith('.'):
                    continue
                ext = Path(file).suffix.lower()
                is_img = ext in organize.IMAGE_EXTENSIONS
                is_vid = ext in organize.VIDEO_EXTENSIONS
                
                if is_img or is_vid:
                    full_p = Path(root) / file
                    rel_p = str(full_p.relative_to(p)).replace("\\", "/")
                    size_mb = round(full_p.stat().st_size / (1024 * 1024), 2)
                    media_files.append({
                        "name": file,
                        "rel_path": rel_p,
                        "type": "video" if is_vid else "image",
                        "size_mb": size_mb
                    })
                if len(media_files) >= limit:
                    break
            if len(media_files) >= limit:
                break
    except Exception as e:
        print(f"Preview scan error: {e}")

    return {"files": media_files}

@app.get("/api/thumbnail")
async def get_thumbnail(path: str, file: str):
    """Generates JPEG thumbnail with RGB conversion to prevent alpha channel crashes."""
    p_root = Path(path).resolve()
    file_path = (p_root / file).resolve()

    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    
    if not HAS_PILLOW or file_path.suffix.lower() not in organize.IMAGE_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Cannot render thumbnail")

    try:
        with Image.open(file_path) as img:
            img = img.convert("RGB")
            img.thumbnail((160, 160))
            buffer = io.BytesIO()
            img.save(buffer, format="JPEG", quality=80)
            return Response(content=buffer.getvalue(), media_type="image/jpeg")
    except Exception as e:
        print(f"Thumbnail generation error: {e}")
        raise HTTPException(status_code=500, detail="Thumbnail render failed")

@app.post("/api/open-folder")
async def open_system_folder(payload: OpenFolderRequest):
    p = Path(payload.path).resolve()
    if not p.exists():
        raise HTTPException(status_code=400, detail="Folder does not exist")
    
    if os.name == 'nt':
        os.startfile(str(p))
    elif os.name == 'posix':
        subprocess.Popen(['xdg-open' if 'linux' in os.sys.platform else 'open', str(p)])
    return {"status": "ok"}

@app.post("/api/abort")
async def abort_sorting():
    active_sort_task["abort"] = True
    return {"status": "abort_requested"}

@app.get("/api/stream")
async def stream_sorting(dry_run: bool = True, copy_mode: bool = False):
    config = organize.load_config()
    source = Path(config.get("source_path", "")).resolve()
    target = Path(config.get("target_path", "")).resolve()
    active_sort_task["abort"] = False

    async def event_generator():
        for update in organize.process_media_stream(source, target, dry_run=dry_run, copy_mode=copy_mode):
            if active_sort_task["abort"]:
                yield f"data: {json.dumps({'type': 'aborted'})}\n\n"
                break
            yield f"data: {json.dumps(update)}\n\n"
            await asyncio.sleep(0.005)

    return StreamingResponse(event_generator(), media_type="text/event-stream")

if __name__ == "__main__":
    import uvicorn
    webbrowser.open("http://localhost:8000")
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")