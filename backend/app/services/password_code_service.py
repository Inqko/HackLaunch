import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import PasswordCode, User
from app.security import hash_password, verify_password
from app.services.email_service import send_email

PURPOSE_CHANGE = "CHANGE"
PURPOSE_RESET = "RESET"

MAX_ATTEMPTS = 5


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


async def issue_code(db: AsyncSession, user_id: int, purpose: str) -> str:
    """Создаёт новый код и инвалидирует предыдущие активные коды этого назначения."""
    await db.execute(
        update(PasswordCode)
        .where(
            PasswordCode.user_id == user_id,
            PasswordCode.purpose == purpose,
            PasswordCode.consumed.is_(False),
        )
        .values(consumed=True)
    )

    code = f"{secrets.randbelow(1_000_000):06d}"
    db.add(
        PasswordCode(
            user_id=user_id,
            purpose=purpose,
            code_hash=hash_password(code),
            expires_at=datetime.now(timezone.utc)
            + timedelta(minutes=settings.password_code_ttl_minutes),
        )
    )
    await db.commit()
    return code


async def consume_code(
    db: AsyncSession, user_id: int, purpose: str, code: str
) -> bool:
    """Проверяет и одноразово погашает код. Неверные попытки ограничены."""
    record = await db.scalar(
        select(PasswordCode)
        .where(
            PasswordCode.user_id == user_id,
            PasswordCode.purpose == purpose,
            PasswordCode.consumed.is_(False),
        )
        .order_by(PasswordCode.created_at.desc())
        .limit(1)
    )
    if record is None:
        return False

    if _aware(record.expires_at) < datetime.now(timezone.utc):
        record.consumed = True
        await db.commit()
        return False

    if record.attempts >= MAX_ATTEMPTS:
        record.consumed = True
        await db.commit()
        return False

    try:
        valid = verify_password(code, record.code_hash)
    except ValueError:
        valid = False

    if not valid:
        record.attempts += 1
        await db.commit()
        return False

    record.consumed = True
    await db.commit()
    return True


async def send_code_email(user: User, code: str, purpose: str) -> bool:
    if purpose == PURPOSE_RESET:
        subject = "HackLaunch AI — сброс пароля"
        action = "сброса пароля"
    else:
        subject = "HackLaunch AI — смена пароля"
        action = "смены пароля"

    text = (
        f"Здравствуйте, {user.name}!\n\n"
        f"Код для {action}: {code}\n\n"
        f"Код действует {settings.password_code_ttl_minutes} минут. "
        "Если вы не запрашивали смену пароля, просто проигнорируйте это письмо."
    )
    return await send_email(user.email, subject, text)
