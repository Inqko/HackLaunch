import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import init_db
from app.routers import ai, analytics, auth, materials, projects, tasks

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(_: FastAPI):
    await init_db()
    yield


app = FastAPI(
    title="HackLaunch AI",
    description="Платформа быстрого запуска хакатон-проектов: задачи от ИИ, GitLab, аналитика.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)

for module in (auth, projects, tasks, ai, materials, analytics):
    app.include_router(module.router)


@app.get("/api/health", tags=["system"])
async def health():
    return {"status": "ok"}
