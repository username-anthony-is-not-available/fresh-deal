
import json
from celery import shared_task
from app.celery_app import celery_app
from sqlmodel import Session, select
from app.core.db import engine
from app.models.all_models import User, MealPlan
from app.agents.planner_agent import MealPlannerAgent
from datetime import datetime, timedelta

@shared_task
def generate_meal_plan_task(user_id: int):
    # Tasks run in a separate process, so they need their own sync session
    with Session(engine) as session:
        try:
            user = session.get(User, user_id)
            if not user:
                return {"error": "User not found"}

            planner = MealPlannerAgent(session)
            plan_data = planner.generate_plan(user)

            # Extract start date from the first day of the plan
            start_date_str = plan_data.get("meal_plan", [])[0].get("date")
            if start_date_str:
                 start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
            else:
                 # Fallback if somehow missing
                 start_date = datetime.now().date()

            meal_plan = MealPlan(
                user_id=user.id,
                start_date=start_date,
                end_date=start_date + timedelta(days=6),
                content_json=json.dumps(plan_data)
            )
            session.add(meal_plan)
            session.commit()
            session.refresh(meal_plan)

            # Return just the ID or basic info, or the full plan
            # The result is stored in Redis
            return json.loads(meal_plan.content_json)

        except Exception as e:
            import traceback
            traceback.print_exc()
            return {"error": str(e)}
