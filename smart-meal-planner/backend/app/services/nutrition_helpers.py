"""Shared helpers for extracting and normalizing meal plan nutrition data."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional


NUTRIENT_KEYS = ("calories", "protein", "carbs", "fat", "fiber")


def _to_float(value: Any) -> float:
    """Safely convert numeric or string nutrient values to float, defaulting to 0.0."""
    if value is None or isinstance(value, bool):
        return 0.0
    try:
        parsed = float(value)
        return parsed if parsed >= 0 else 0.0
    except (TypeError, ValueError):
        return 0.0


def parse_nutrition_json(raw: Any) -> Dict[str, Any]:
    """Parse a JSON string or mapping into a nutrition dictionary."""
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str) and raw.strip():
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                return parsed
        except (json.JSONDecodeError, TypeError):
            return {}
    return {}


def normalize_nutrition(raw: Optional[Dict[str, Any]]) -> Dict[str, float]:
    """Normalize a meal/recipe nutrition dict, supporting 'fat'/'fats' and None values."""
    if not isinstance(raw, dict):
        return {key: 0.0 for key in NUTRIENT_KEYS}

    fat_val = raw.get("fat")
    if fat_val is None:
        fat_val = raw.get("fats")

    return {
        "calories": _to_float(raw.get("calories")),
        "protein": _to_float(raw.get("protein")),
        "carbs": _to_float(raw.get("carbs")),
        "fat": _to_float(fat_val),
        "fiber": _to_float(raw.get("fiber")),
    }


def extract_plan_days(plan_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract day objects from either 'meal_plan' or 'days' plan formats."""
    if not isinstance(plan_data, dict):
        return []

    meal_plan = plan_data.get("meal_plan")
    if (
        isinstance(meal_plan, list)
        and meal_plan
        and all(isinstance(day, dict) for day in meal_plan)
    ):
        return meal_plan

    days = plan_data.get("days")
    if (
        isinstance(days, list)
        and days
        and all(isinstance(day, dict) for day in days)
    ):
        return days

    return []


def extract_day_meals(day: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract all meal dictionaries from either list-based or keyed day structures."""
    if not isinstance(day, dict):
        return []

    extracted: List[Dict[str, Any]] = []
    meals_container = day.get("meals")
    if isinstance(meals_container, list):
        extracted.extend(m for m in meals_container if isinstance(m, dict))
        return extracted

    source = meals_container if isinstance(meals_container, dict) else day
    for meal_type in ("breakfast", "lunch", "dinner", "snack", "snacks"):
        entry = source.get(meal_type)
        if isinstance(entry, dict):
            extracted.append(entry)
        elif isinstance(entry, list):
            extracted.extend(m for m in entry if isinstance(m, dict))

    return extracted
