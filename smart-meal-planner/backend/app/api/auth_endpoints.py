from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlmodel import Session, select
from jose import JWTError, jwt
from app.core.config import settings
from app.core.db import get_async_session
from app.core.security import create_access_token, get_password_hash, verify_password
from app.models.all_models import User
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.limiter import limiter
from typing import Optional

router = APIRouter()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/login/access-token")

class TokenData(BaseModel):
    id: Optional[str] = None

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    session: AsyncSession = Depends(get_async_session)
):
    credentials_exception = HTTPException(
        status_code=401,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id = payload.get("sub")
        if user_id is None:
            raise credentials_exception
        token_data = TokenData(id=user_id)
    except JWTError:
        raise credentials_exception
    user = await session.get(User, int(token_data.id))
    if user is None:
        raise credentials_exception
    return user

async def get_current_user_optional(
    token: Optional[str] = Depends(oauth2_scheme),
    session: AsyncSession = Depends(get_async_session)
) -> Optional[User]:
    if not token:
        return None
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id = payload.get("sub")
        if user_id is None:
            return None
        user = await session.get(User, int(user_id))
        return user
    except JWTError:
        return None


import json
from typing import List

class UserCreate(BaseModel):
    email: str
    password: str
    postal_code: str
    household_size: int
    dietary_preferences: List[str]
    allergies: List[str] = []


@router.post("/register", response_model=User, summary="Register a new user")
async def register(user_in: UserCreate, session: AsyncSession = Depends(get_async_session)):
    """
    Create a new user account.
    """
    result = await session.execute(select(User).where(User.email == user_in.email))
    if result.scalars().first():
        raise HTTPException(status_code=400, detail="Email already registered")
    hashed_password = get_password_hash(user_in.password)
    user = User(
        email=user_in.email,
        hashed_password=hashed_password,
        postal_code=user_in.postal_code,
        household_size=user_in.household_size,
        dietary_preferences_json=json.dumps(user_in.dietary_preferences),
        allergies_json=json.dumps(user_in.allergies),
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


@router.post("/login/access-token", summary="User login")
@limiter.limit("10/minute")
async def login(
    request: Request, session: AsyncSession = Depends(get_async_session), form_data: OAuth2PasswordRequestForm = Depends()
):
    """
    Authenticate a user and return a JWT access token.
    """
    result = await session.execute(select(User).where(User.email == form_data.username))
    user = result.scalars().first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=400, detail="Incorrect email or password"
        )
    access_token = create_access_token(subject=user.id)
    return {"access_token": access_token, "token_type": "bearer"}
