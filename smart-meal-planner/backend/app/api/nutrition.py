from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select
from typing import List
from datetime import date, timedelta

from app.models.all_models import User, UserNutritionGoal, DailyNutrition, MealPlan
from app.core.security import get_current_active_user
from app.core.db import get_session
from app.schemas import (
    UserNutritionGoalCreate,
    UserNutritionGoalRead,
    DailyNutritionRead,
    DietaryProfileRead,
    DietaryComplianceRead,
    RecommendedNutritionRequest,
    RecommendedNutritionRead,
)
from app.services.dietary_nutrition_service import DietaryNutritionService

router = APIRouter()

@router.post("/users/me/nutrition-goal", response_model=UserNutritionGoalRead, summary="Create or update nutrition goal")
def create_or_update_nutrition_goal(
    *,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_active_user),
    goal: UserNutritionGoalCreate
):
    """
    Set or update the daily nutrition goals (calories, protein, etc.) for the logged-in user.
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

@router.get("/users/me/nutrition-goal", response_model=UserNutritionGoalRead, summary="Get nutrition goal")
def get_nutrition_goal(
    *,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_active_user)
):
    """
    Retrieve the current daily nutrition goals for the logged-in user.
    """
    goal_query = select(UserNutritionGoal).where(UserNutritionGoal.user_id == current_user.id)
    goal = session.exec(goal_query).first()
    if not goal:
        raise HTTPException(status_code=404, detail="Nutrition goal not found")
    return goal

@router.get("/users/me/nutrition-summary", response_model=List[DailyNutritionRead], summary="Get nutrition summary")
def get_nutrition_summary(
    *,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_active_user),
    start_date: date,
    end_date: date
):
    """
    Get a summary of daily nutritional intake for the logged-in user over a specified date range.
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


@router.get(
    "/nutrition/dietary-profiles",
    response_model=List[DietaryProfileRead],
    summary="List supported dietary restriction nutritional profiles",
)
def get_dietary_profiles():
    """Return supported dietary restrictions with macro splits and micronutrient watchlists."""
    return DietaryNutritionService.list_supported_profiles()


@router.post(
    "/users/me/nutrition-goal/recommended",
    response_model=RecommendedNutritionRead,
    summary="Compute dietary-restriction-adjusted nutrition targets",
)
def get_recommended_nutrition_goal(
    *,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_active_user),
    payload: RecommendedNutritionRequest,
):
    """
    Calculate recommended daily calorie, macro, fiber, and sodium targets based on
    goal type and active dietary restrictions, optionally persisting them as the user's goal.
    """
    restrictions = (
        payload.dietary_restrictions
        if payload.dietary_restrictions is not None
        else current_user.dietary_preferences
    )
    recommended = DietaryNutritionService.compute_recommended_targets(
        goal_type=payload.goal_type,
        restrictions=restrictions,
        base_calories=payload.base_calories,
    )

    if payload.apply_to_goal:
        db_goal = session.exec(
            select(UserNutritionGoal).where(UserNutritionGoal.user_id == current_user.id)
        ).first()
        fields = {
            "goal_type": recommended["goal_type"],
            "target_calories": recommended["target_calories"],
            "target_protein": recommended["target_protein"],
            "target_carbs": recommended["target_carbs"],
            "target_fats": recommended["target_fats"],
            "target_fiber": recommended["target_fiber"],
        }
        if db_goal:
            for k, v in fields.items():
                setattr(db_goal, k, v)
        else:
            db_goal = UserNutritionGoal(user_id=current_user.id, **fields)
        session.add(db_goal)
        session.commit()

    return recommended


@router.get(
    "/users/me/nutrition-compliance",
    response_model=DietaryComplianceRead,
    summary="Evaluate nutritional compliance against dietary restrictions",
)
def get_nutrition_compliance(
    *,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_active_user),
    days: int = Query(7, ge=1, le=90),
):
    """
    Evaluate recent daily nutrition intake and the latest meal plan against the user's
    dietary restrictions, allergies, and nutrition goals.
    """
    end_date = date.today()
    start_date = end_date - timedelta(days=days - 1)

    daily_records = session.exec(
        select(DailyNutrition)
        .where(DailyNutrition.user_id == current_user.id)
        .where(DailyNutrition.date >= start_date)
        .where(DailyNutrition.date <= end_date)
        .order_by(DailyNutrition.date)
    ).all()

    goal = session.exec(
        select(UserNutritionGoal).where(UserNutritionGoal.user_id == current_user.id)
    ).first()

    latest_plan = session.exec(
        select(MealPlan)
        .where(MealPlan.user_id == current_user.id)
        .order_by(MealPlan.created_at.desc())
    ).first()

    return DietaryNutritionService.evaluate_compliance(
        daily_records=daily_records,
        restrictions=current_user.dietary_preferences,
        allergies=current_user.allergies,
        goal=goal,
        latest_plan=latest_plan,
    )
