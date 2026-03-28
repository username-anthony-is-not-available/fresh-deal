
import pytest
from datetime import date
from sqlmodel import Session, select
from app.agents.nutrition_agent import NutritionAgent
from app.models.all_models import DailyNutrition, User
from app.core.db import engine
from sqlmodel import SQLModel

@pytest.mark.asyncio
async def test_persist_daily_nutrition_from_plan():
    # Ensure tables exist for local testing
    SQLModel.metadata.create_all(engine)

    # Use a real session (assuming SQLite for tests as per memory)
    with Session(engine) as session:
        # 1. Setup mock user
        user = User(email="test_nutrition@example.com", hashed_password="pw", postal_code="H4T1V6", household_size=2)
        session.add(user)
        session.commit()
        session.refresh(user)

        agent = NutritionAgent(session=session)

        # 2. Mock plan data
        plan_data = {
            "meal_plan": [
                {
                    "date": "2025-01-01",
                    "daily_summary": {
                        "calories": 2000,
                        "protein": 150,
                        "carbs": 200,
                        "fat": 60
                    }
                },
                {
                    "date": "2025-01-02",
                    "daily_summary": {
                        "calories": 2100,
                        "protein": 160,
                        "carbs": 210,
                        "fat": 65
                    }
                }
            ]
        }

        # 3. Call persistence method
        await agent.persist_daily_nutrition_from_plan(user.id, plan_data)
        session.commit()

        # 4. Verify records in DB
        statement = select(DailyNutrition).where(DailyNutrition.user_id == user.id).order_by(DailyNutrition.date)
        results = session.exec(statement).all()

        assert len(results) == 2
        assert results[0].date == date(2025, 1, 1)
        assert results[0].calories == 2000
        assert results[0].protein == 150
        assert results[0].fats == 60

        assert results[1].date == date(2025, 1, 2)
        assert results[1].calories == 2100

        # 5. Test update existing record
        updated_plan_data = {
            "meal_plan": [
                {
                    "date": "2025-01-01",
                    "daily_summary": {
                        "calories": 2500,
                        "protein": 180,
                        "carbs": 250,
                        "fat": 80
                    }
                }
            ]
        }

        await agent.persist_daily_nutrition_from_plan(user.id, updated_plan_data)
        session.commit()

        # Verify update
        session.expire_all()
        updated_result = session.exec(select(DailyNutrition).where(DailyNutrition.user_id == user.id, DailyNutrition.date == date(2025, 1, 1))).first()
        assert updated_result.calories == 2500
        assert updated_result.protein == 180

        # Cleanup
        session.delete(user)
        for r in results:
            session.delete(r)
        session.commit()
