from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.all_models import User
from app.schemas import UserUpdate
from typing import Optional

class UserService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_user(self, user_id: int) -> Optional[User]:
        result = await self.session.get(User, user_id)
        return result

    async def update_user(self, user_id: int, user_update: UserUpdate) -> Optional[User]:
        user = await self.get_user(user_id)
        if not user:
            return None

        update_data = user_update.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(user, key, value)

        self.session.add(user)
        await self.session.commit()
        await self.session.refresh(user)
        return user
