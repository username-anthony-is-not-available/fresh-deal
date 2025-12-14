from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from typing import List
from datetime import date

from app.models.all_models import User, UserNutritionGoal, DailyNutrition
from app.core.security import get_current_active_user
from app.core.db import get_session
from app.schemas import UserNutritionGoalCreate, UserNutritionGoalRead, DailyNutritionRead

router = APIRouter()

@router.post("/users/me/nutrition-goal", response_model=UserNutritionGoalRead)
def create_or_update_nutrition_goal(
    *,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_active_user),
    goal: UserNutritionGoalCreate
):
    """
    Create or update the nutrition goal for the current user.
    """
    goal_query = select(UserNutritionGoal).where(UserNutritionGoal.user_id == current_user.id)
    db_goal = session.exec(goal_query).first()

    if db_goal:
        goal_data = goal.model_dump(exclude_unset=True)
        for key, value in goal_data.items():
            setattr(db_goal, key, value)
        session.add(db_goal)
    else:
        db_goal = UserNutritionGoal.model_validate(goal, update={"user_id": current_user.id})
        session.add(db_goal)

    session.commit()
    session.refresh(db_goal)
    return db_goal

@router.get("/users/me/nutrition-goal", response_model=UserNutritionGoalRead)
def get_nutrition_goal(
    *,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_active_user)
):
    """
    Get the nutrition goal for the current user.
    """
    goal_query = select(UserNutritionGoal).where(UserNutritionGoal.user_id == current_user.id)
    goal = session.exec(goal_query).first()
    if not goal:
        raise HTTPException(status_code=404, detail="Nutrition goal not found")
    return goal

@router.get("/users/me/nutrition-summary", response_model=List[DailyNutritionRead])
def get_nutrition_summary(
    *,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_active_user),
    start_date: date,
    end_date: date
):
    """
    Get the daily nutrition summary for the current user over a date range.
    """
    summary_query = (
        select(DailyNutrition)
        .where(DailyNutrition.user_id == current_user.id)
        .where(DailyNutrition.date >= start_date)
        .where(DailyNutrition.date <= end_date)
        .order_by(DailyNutrition.date)
    )
    summary = session.exec(summary_query).all()
    return summary
