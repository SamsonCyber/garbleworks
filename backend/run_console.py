"""Standalone launcher for the Garbleworks Ops Console.

Runs just the console router on its own port so you can see the UI without
mounting it into app.py. For production, prefer:  app.include_router(console_router)

    python run_console.py           # -> http://127.0.0.1:8799/console
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import uvicorn
from fastapi import FastAPI
from fastapi.responses import RedirectResponse

from console import router as console_router

app = FastAPI(title="Garbleworks Ops Console")
app.include_router(console_router)


@app.get("/")
def _root():
    return RedirectResponse("/console")


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8799, log_level="info")
