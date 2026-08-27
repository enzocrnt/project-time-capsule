import json
import webbrowser
import asyncio
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import organize

app = FastAPI(title="Project Time Capsule")

# Serve the static assets
STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

class ConfigUpdate(BaseModel):
    source_path: str
    target_path: str

@app.get("/", response_class=HTMLResponse)
async def serve_dashboard():
    index_path = STATIC_DIR / "index.html"
    return HTMLResponse(content=index_path.read_text(encoding="utf-8"))

@app.get("/api/config")
async def get_config():
    return organize.load_config()

@app.post("/api/config")
async def update_config(payload: ConfigUpdate):
    updated = organize.save_config(payload.source_path, payload.target_path)
    return {"status": "ok", "config": updated}

@app.get("/api/stream")
async def stream_ingestion(dry_run: bool = True, copy_mode: bool = False):
    config = organize.load_config()
    source = Path(config.get("source_path", ""))
    target = Path(config.get("target_path", ""))

    async def event_generator():
        for update in organize.process_media_stream(source, target, dry_run=dry_run, copy_mode=copy_mode):
            yield f"data: {json.dumps(update)}\n\n"
            await asyncio.sleep(0.01)  # Yield control to prevent event-loop choking

    return StreamingResponse(event_generator(), media_type="text/event-stream")

if __name__ == "__main__":
    import uvicorn
    # Open browser on startup
    webbrowser.open("http://localhost:8000")
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")