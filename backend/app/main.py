import asyncio
import contextlib
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import init_db
from app.routers import ai, analytics, auth, gitlab, materials, projects, review, tasks, users
from app.services.review_service import review_poller

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(_: FastAPI):
    await init_db()
    # Фоновый опрос веток задач: новый push -> ИИ-ревью
    poller = asyncio.create_task(review_poller())
    yield
    poller.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await poller


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

for module in (auth, projects, tasks, review, ai, materials, analytics, gitlab, users):
    app.include_router(module.router)


@app.get("/api/health", tags=["system"])
async def health():
    return {"status": "ok"}
