from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user
from app.models import User
from app.schemas import LoginIn, PasswordChangeIn, RegisterIn, TokenOut, UserOut, UserUpdate
from app.security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/api", tags=["auth"])


def _token_for(user: User) -> TokenOut:
    return TokenOut(access_token=create_access_token(user.id), user=UserOut.model_validate(user))


@router.post("/auth/register", response_model=TokenOut, status_code=status.HTTP_201_CREATED)
async def register(data: RegisterIn, db: AsyncSession = Depends(get_db)):
    email = data.email.lower()
    if await db.scalar(select(User).where(User.email == email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Пользователь с таким email уже существует")
    user = User(
        email=email,
        name=data.name,
        password_hash=hash_password(data.password),
        gitlab_username=data.gitlab_username or None,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return _token_for(user)


@router.post("/auth/login", response_model=TokenOut)
async def login(data: LoginIn, db: AsyncSession = Depends(get_db)):
    user = await db.scalar(select(User).where(User.email == data.email.lower()))
    if user is None or not verify_password(data.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Неверный email или пароль")
    return _token_for(user)


@router.get("/users/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)):
    return user


@router.patch("/users/me", response_model=UserOut)
async def update_me(
    data: UserUpdate, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(user, field, value or None if field == "gitlab_username" else value)
    await db.commit()
    await db.refresh(user)
    return user


@router.post("/users/me/password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    data: PasswordChangeIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not verify_password(data.current_password, user.password_hash):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Текущий пароль указан неверно")
    if data.new_password == data.current_password:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Новый пароль должен отличаться от текущего"
        )
    user.password_hash = hash_password(data.new_password)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
