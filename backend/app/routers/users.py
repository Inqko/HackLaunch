import re
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.deps import get_current_user
from app.models import User
from app.schemas import UserOut

router = APIRouter(prefix="/api/users", tags=["users"])

AVATAR_URL_PREFIX = "/api/users/avatars/"
SAFE_NAME = re.compile(r"[A-Za-z0-9_-]+\.(jpg|png|webp|gif)")
MEDIA_TYPES = {".jpg": "image/jpeg", ".png": "image/png", ".webp": "image/webp", ".gif": "image/gif"}


def _uploads_root() -> Path:
    root = Path(settings.upload_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def _sniff_extension(head: bytes) -> str | None:
    """Тип определяем по сигнатуре файла, а не по Content-Type от клиента."""
    if head.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return ".webp"
    if head[:6] in (b"GIF87a", b"GIF89a"):
        return ".gif"
    return None


def _stored_file(avatar_url: str | None) -> Path | None:
    if not avatar_url:
        return None
    # В БД лежит URL; берём только basename, чтобы не выйти за пределы uploads
    name = Path(avatar_url).name
    if not SAFE_NAME.fullmatch(name):
        return None
    return _uploads_root() / name


@router.post("/me/avatar", response_model=UserOut)
async def upload_avatar(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    limit = settings.avatar_max_mb * 1024 * 1024
    data = await file.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, f"Файл больше {settings.avatar_max_mb} МБ")
    ext = _sniff_extension(data[:16])
    if ext is None:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Поддерживаются только JPEG, PNG, WebP и GIF")

    name = f"{user.id}-{uuid.uuid4().hex}{ext}"
    dest = _uploads_root() / name
    dest.write_bytes(data)

    old = _stored_file(user.avatar_url)
    user.avatar_url = AVATAR_URL_PREFIX + name
    try:
        await db.commit()
    except Exception:
        dest.unlink(missing_ok=True)
        raise
    # Старый файл удаляем только после того, как новый успешно сохранён
    if old is not None:
        old.unlink(missing_ok=True)
    await db.refresh(user)
    return user


@router.delete("/me/avatar", response_model=UserOut)
async def delete_avatar(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    old = _stored_file(user.avatar_url)
    user.avatar_url = None
    await db.commit()
    if old is not None:
        old.unlink(missing_ok=True)
    await db.refresh(user)
    return user


@router.get("/avatars/{filename}", include_in_schema=False)
async def serve_avatar(filename: str):
    if not SAFE_NAME.fullmatch(filename):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Не найдено")
    path = _uploads_root() / filename
    if not path.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Не найдено")
    # Имя уникально для каждой загрузки, поэтому файл можно кэшировать навсегда
    return FileResponse(
        path,
        media_type=MEDIA_TYPES[path.suffix],
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )
