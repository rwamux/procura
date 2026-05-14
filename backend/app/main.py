from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from app.api import auth, procurements, workflows
from app.config import settings
from app.logging_config import setup_logging
from app.workflows.checkpointer import close_checkpointer, init_checkpointer


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging(debug=settings.DEBUG)
    await init_checkpointer()
    upload_path = Path(settings.UPLOAD_DIR)
    upload_path.mkdir(parents=True, exist_ok=True)
    yield
    await close_checkpointer()


app = FastAPI(
    title="Procura API",
    version="1.0.0",
    description="AI-assisted procurement workflow platform",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.APP_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api")
app.include_router(procurements.router, prefix="/api")
app.include_router(workflows.router, prefix="/api")

upload_path = Path(settings.UPLOAD_DIR)
if upload_path.exists():
    app.mount("/files", StaticFiles(directory=str(upload_path)), name="files")


@app.get("/health")
async def health():
    return {"status": "ok"}
