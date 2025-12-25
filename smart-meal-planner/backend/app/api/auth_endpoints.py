from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import Session, select
from app.core.db import get_async_session
from app.core.security import create_access_token, get_password_hash, verify_password
from app.models.all_models import User
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.limiter import limiter

router = APIRouter()


import json
from typing import List

class UserCreate(BaseModel):
    email: str
    password: str
    postal_code: str
    household_size: int
    dietary_preferences: List[str]


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
