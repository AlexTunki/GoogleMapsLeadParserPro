import json
import os
import threading
import queue
import asyncio
import webbrowser
import time
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import uvicorn

from engine import ParserEngine

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

ui_queue = queue.Queue()
engine = ParserEngine(lambda msg: ui_queue.put(msg))
engine_thread = None

@app.get("/", response_class=HTMLResponse)
def index():
    with open("static/index.html", "r", encoding="utf-8") as f:
        return f.read()

@app.get("/api/data")
def get_data():
    try:
        with open("data/cities.json", "r", encoding="utf-8") as f:
            cities = [c["name"] for c in json.load(f)]
    except:
        cities = []
    try:
        with open("data/niches.json", "r", encoding="utf-8") as f:
            niches = json.load(f)
    except:
        niches = []
    return {"cities": cities, "niches": niches}

@app.get("/api/projects")
def get_projects():
    if os.path.exists("projects.json"):
        try:
            with open("projects.json", "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return []
    return []

@app.post("/api/projects")
async def save_projects(request: Request):
    data = await request.json()
    with open("projects.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    return {"status": "ok"}

@app.get("/api/settings")
def get_settings():
    if os.path.exists("settings.json"):
        try:
            with open("settings.json", "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    return {
        "quota": 100,
        "radius": 20.0,
        "step": 6.0,
        "filters_enabled": False,
        "min_rev": 0,
        "max_rev": 50,
        "freshness": "Any"
    }

@app.post("/api/settings")
async def save_settings(request: Request):
    data = await request.json()
    with open("settings.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    return {"status": "ok"}

def run_async_engine(tasks):
    asyncio.run(engine.start(tasks))
    ui_queue.put({"type": "LOG", "text": "PARSING STOPPED", "color": "white"})

@app.post("/api/start")
def start_engine():
    global engine_thread
    if not engine.is_running:
        tasks = get_projects()
        engine_thread = threading.Thread(target=run_async_engine, args=(tasks,), daemon=True)
        engine_thread.start()
        return {"status": "started"}
    return {"status": "already_running"}

@app.post("/api/stop")
def stop_engine():
    engine.is_running = False
    engine.manual_stop = True
    ui_queue.put({"type": "LOG", "text": "Stopping at user request...", "color": "red"})
    return {"status": "stopped"}

@app.post("/api/pause")
def toggle_pause():
    engine.is_paused = not engine.is_paused
    return {"paused": engine.is_paused}

@app.post("/api/skip/{skip_type}")
def skip(skip_type: str):
    engine.skip_request = skip_type.upper()
    ui_queue.put({"type": "LOG", "text": f"⚡ SKIP REQUESTED ({skip_type.upper()})...", "color": "#FF4500"})
    return {"status": "skipped"}

async def log_generator():
    while True:
        try:
            msg = ui_queue.get_nowait()
            yield f"data: {json.dumps(msg)}\n\n"
            ui_queue.task_done()
        except queue.Empty:
            await asyncio.sleep(0.1)

@app.get("/api/stream")
async def stream():
    return StreamingResponse(log_generator(), media_type="text/event-stream")

if __name__ == "__main__":
    def open_browser():
        time.sleep(1.5)
        webbrowser.open("http://127.0.0.1:8000")
    threading.Thread(target=open_browser, daemon=True).start()
    uvicorn.run("app:app", host="127.0.0.1", port=8000, log_level="error")