"""Dietary restriction-aware nutritional recommendations and compliance tracking (Issue #391)."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from app.models.all_models import DailyNutrition, MealPlan, UserNutritionGoal
from app.services.nutrition_helpers import extract_day_meals, extract_plan_days


DIETARY_PROFILES: Dict[str, Dict[str, Any]] = {
    "vegetarian": {
        "label": "Vegetarian",
        "excluded_ingredients": [
            "beef", "pork", "chicken", "turkey", "bacon", "ham", "steak", "sausage",
            "lamb", "veal", "salmon", "tuna", "shrimp", "cod", "fish", "anchovy",
        ],
        "macro_split": {"protein_pct": 22, "carbs_pct": 50, "fats_pct": 28},
        "min_fiber_g": 28.0,
        "micronutrients_to_watch": ["vitamin_b12", "iron", "zinc", "omega_3"],
    },
    "vegan": {
        "label": "Vegan",
        "excluded_ingredients": [
            "beef", "pork", "chicken", "turkey", "bacon", "ham", "steak", "sausage",
            "lamb", "salmon", "tuna", "shrimp", "fish", "milk", "cheese", "butter",
            "cream", "yogurt", "whey", "egg", "eggs", "honey",
        ],
        "macro_split": {"protein_pct": 20, "carbs_pct": 54, "fats_pct": 26},
        "min_fiber_g": 32.0,
        "micronutrients_to_watch": ["vitamin_b12", "iron", "calcium", "vitamin_d", "omega_3"],
    },
    "pescatarian": {
        "label": "Pescatarian",
        "excluded_ingredients": [
            "beef", "pork", "chicken", "turkey", "bacon", "ham", "steak", "sausage", "lamb", "veal",
        ],
        "macro_split": {"protein_pct": 26, "carbs_pct": 46, "fats_pct": 28},
        "min_fiber_g": 26.0,
        "micronutrients_to_watch": ["omega_3", "vitamin_d", "iron"],
    },
    "gluten-free": {
        "label": "Gluten-Free",
        "excluded_ingredients": [
            "wheat", "barley", "rye", "bread", "pasta", "spaghetti", "flour", "couscous",
            "soy sauce", "seitan", "crouton", "bagel",
        ],
        "macro_split": {"protein_pct": 25, "carbs_pct": 45, "fats_pct": 30},
        "min_fiber_g": 26.0,
        "micronutrients_to_watch": ["fiber", "folate", "iron", "vitamin_b6"],
    },
    "dairy-free": {
        "label": "Dairy-Free",
        "excluded_ingredients": [
            "milk", "cheese", "cheddar", "mozzarella", "parmesan", "butter", "cream",
            "yogurt", "whey", "casein", "ghee", "ricotta",
        ],
        "macro_split": {"protein_pct": 25, "carbs_pct": 45, "fats_pct": 30},
        "min_fiber_g": 25.0,
        "micronutrients_to_watch": ["calcium", "vitamin_d", "riboflavin"],
    },
    "keto": {
        "label": "Ketogenic",
        "excluded_ingredients": [
            "sugar", "bread", "pasta", "rice", "potato", "potatoes", "oat", "oats",
            "corn", "banana", "apple", "honey", "maple syrup",
        ],
        "macro_split": {"protein_pct": 25, "carbs_pct": 8, "fats_pct": 67},
        "max_carbs_g": 50.0,
        "min_fiber_g": 20.0,
        "micronutrients_to_watch": ["magnesium", "potassium", "sodium", "fiber"],
    },
    "low-carb": {
        "label": "Low-Carb",
        "excluded_ingredients": ["sugar", "white bread", "soda", "pastry", "candy"],
        "macro_split": {"protein_pct": 30, "carbs_pct": 25, "fats_pct": 45},
        "max_carbs_g": 130.0,
        "min_fiber_g": 25.0,
        "micronutrients_to_watch": ["fiber", "magnesium", "potassium"],
    },
    "paleo": {
        "label": "Paleo",
        "excluded_ingredients": [
            "bread", "pasta", "wheat", "rice", "oats", "corn", "soy", "tofu",
            "peanut", "peanuts", "beans", "lentils", "milk", "cheese", "sugar",
        ],
        "macro_split": {"protein_pct": 30, "carbs_pct": 30, "fats_pct": 40},
        "min_fiber_g": 26.0,
        "micronutrients_to_watch": ["calcium", "vitamin_d", "iodine"],
    },
    "halal": {
        "label": "Halal",
        "excluded_ingredients": [
            "pork", "bacon", "ham", "lard", "prosciutto", "pepperoni", "wine", "beer", "alcohol", "gelatin",
        ],
        "macro_split": {"protein_pct": 25, "carbs_pct": 45, "fats_pct": 30},
        "min_fiber_g": 25.0,
        "micronutrients_to_watch": ["iron", "vitamin_d"],
    },
    "kosher": {
        "label": "Kosher",
        "excluded_ingredients": [
            "pork", "bacon", "ham", "lard", "shrimp", "lobster", "crab", "clam",
            "oyster", "mussel", "scallop", "shellfish",
        ],
        "macro_split": {"protein_pct": 25, "carbs_pct": 45, "fats_pct": 30},
        "min_fiber_g": 25.0,
        "micronutrients_to_watch": ["vitamin_d", "calcium"],
    },
    "nut-free": {
        "label": "Nut-Free",
        "excluded_ingredients": [
            "peanut", "peanuts", "almond", "almonds", "walnut", "walnuts",
            "cashew", "cashews", "pecan", "pecans", "pistachio", "hazelnut", "macadamia",
        ],
        "macro_split": {"protein_pct": 25, "carbs_pct": 45, "fats_pct": 30},
        "min_fiber_g": 25.0,
        "micronutrients_to_watch": ["vitamin_e", "magnesium"],
    },
    "low-sodium": {
        "label": "Low-Sodium",
        "excluded_ingredients": ["soy sauce", "bacon", "deli meat", "bouillon", "pickles"],
        "macro_split": {"protein_pct": 25, "carbs_pct": 48, "fats_pct": 27},
        "max_sodium_mg": 1500.0,
        "min_fiber_g": 28.0,
        "micronutrients_to_watch": ["sodium", "potassium", "magnesium"],
    },
    "high-protein": {
        "label": "High-Protein",
        "excluded_ingredients": [],
        "macro_split": {"protein_pct": 35, "carbs_pct": 35, "fats_pct": 30},
        "min_protein_pct": 30.0,
        "min_fiber_g": 25.0,
        "micronutrients_to_watch": ["calcium", "hydration", "fiber"],
    },
    "mediterranean": {
        "label": "Mediterranean",
        "excluded_ingredients": ["processed meat", "hot dog", "soda"],
        "macro_split": {"protein_pct": 22, "carbs_pct": 45, "fats_pct": 33},
        "min_fiber_g": 30.0,
        "micronutrients_to_watch": ["omega_3", "polyphenols", "fiber"],
    },
}


class DietaryNutritionService:
    """Computes diet-tailored macro/micronutrient targets and evaluates restriction compliance."""

    @staticmethod
    def normalize_restriction(raw: str) -> str:
        return raw.strip().lower().replace("_", "-").replace(" ", "-")

    @classmethod
    def list_supported_profiles(cls) -> List[Dict[str, Any]]:
        return [
            {
                "key": key,
                "label": cfg["label"],
                "macro_split": cfg["macro_split"],
                "max_carbs_g": cfg.get("max_carbs_g"),
                "max_sodium_mg": cfg.get("max_sodium_mg"),
                "min_protein_pct": cfg.get("min_protein_pct"),
                "min_fiber_g": cfg.get("min_fiber_g", 25.0),
                "micronutrients_to_watch": cfg["micronutrients_to_watch"],
            }
            for key, cfg in DIETARY_PROFILES.items()
        ]

    @classmethod
    def compute_recommended_targets(
        cls,
        goal_type: str = "maintenance",
        restrictions: Optional[List[str]] = None,
        base_calories: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Compute daily calorie/macro/fiber/sodium targets tailored to goal and dietary restrictions."""
        normalized = [
            cls.normalize_restriction(r)
            for r in (restrictions or [])
            if isinstance(r, str) and r.strip()
        ]

        calories = float(base_calories) if base_calories else 2000.0
        if not base_calories:
            if goal_type == "weight_loss":
                calories = 1700.0
            elif goal_type == "muscle_gain":
                calories = 2400.0

        protein_pct = 25.0
        carbs_pct = 45.0
        fats_pct = 30.0
        if goal_type == "muscle_gain":
            protein_pct, carbs_pct, fats_pct = 30.0, 40.0, 30.0
        elif goal_type == "weight_loss":
            protein_pct, carbs_pct, fats_pct = 30.0, 40.0, 30.0

        max_carbs_g: Optional[float] = None
        max_sodium_mg: Optional[float] = None
        min_fiber_g = 25.0
        watch_micros: List[str] = []

        matched_profiles = [DIETARY_PROFILES[r] for r in normalized if r in DIETARY_PROFILES]
        if matched_profiles:
            protein_pct = max(p["macro_split"]["protein_pct"] for p in matched_profiles)
            if any(r in ("keto", "low-carb") for r in normalized):
                # Carb-restricted diets override carb percentage cleanly
                carb_caps = [p["max_carbs_g"] for p in matched_profiles if "max_carbs_g" in p]
                max_carbs_g = min(carb_caps) if carb_caps else 130.0
                carbs_pct = min((max_carbs_g * 4.0 / calories) * 100.0, 25.0)
                fats_pct = max(100.0 - protein_pct - carbs_pct, 20.0)
            else:
                carbs_pct = sum(p["macro_split"]["carbs_pct"] for p in matched_profiles) / len(matched_profiles)
                fats_pct = max(100.0 - protein_pct - carbs_pct, 20.0)

            for prof in matched_profiles:
                min_fiber_g = max(min_fiber_g, float(prof.get("min_fiber_g", 25.0)))
                if "max_sodium_mg" in prof:
                    sodium_cap = float(prof["max_sodium_mg"])
                    max_sodium_mg = sodium_cap if max_sodium_mg is None else min(max_sodium_mg, sodium_cap)
                for micro in prof["micronutrients_to_watch"]:
                    if micro not in watch_micros:
                        watch_micros.append(micro)

        target_protein = round((calories * (protein_pct / 100.0)) / 4.0, 1)
        target_carbs = round((calories * (carbs_pct / 100.0)) / 4.0, 1)
        if max_carbs_g is not None:
            target_carbs = min(target_carbs, max_carbs_g)
        target_fats = round((calories * (fats_pct / 100.0)) / 9.0, 1)

        return {
            "goal_type": goal_type,
            "target_calories": round(calories, 1),
            "target_protein": target_protein,
            "target_carbs": target_carbs,
            "target_fats": target_fats,
            "target_fiber": round(min_fiber_g, 1),
            "max_sodium_mg": max_sodium_mg,
            "restrictions_applied": [r for r in normalized if r in DIETARY_PROFILES],
            "micronutrients_to_watch": watch_micros,
        }

    @classmethod
    def check_plan_conflicts(
        cls,
        plan_data: Dict[str, Any],
        restrictions: Optional[List[str]] = None,
        allergies: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Detect meals whose ingredients conflict with user dietary restrictions or allergies."""
        normalized_restrictions = [
            cls.normalize_restriction(r)
            for r in (restrictions or [])
            if isinstance(r, str) and r.strip()
        ]
        normalized_allergies = [
            a.strip().lower()
            for a in (allergies or [])
            if isinstance(a, str) and a.strip()
        ]

        if not normalized_restrictions and not normalized_allergies:
            return []

        conflicts: List[Dict[str, Any]] = []
        for day_idx, day in enumerate(extract_plan_days(plan_data), start=1):
            for meal in extract_day_meals(day):
                meal_name = meal.get("recipe_name") or meal.get("name") or "Meal"
                raw_ingredients = meal.get("ingredients") or []
                ing_texts = []
                for ing in raw_ingredients:
                    if isinstance(ing, dict):
                        ing_texts.append(str(ing.get("item") or ing.get("name") or "").lower())
                    else:
                        ing_texts.append(str(ing).lower())
                combined_text = f"{meal_name.lower()} {' '.join(ing_texts)}"

                for restriction in normalized_restrictions:
                    prof = DIETARY_PROFILES.get(restriction)
                    if not prof:
                        continue
                    matched_bad = [
                        kw for kw in prof["excluded_ingredients"] if kw in combined_text
                    ]
                    if matched_bad:
                        conflicts.append(
                            {
                                "day": day_idx,
                                "meal": meal_name,
                                "type": "dietary_restriction",
                                "restriction": restriction,
                                "matched_terms": matched_bad,
                            }
                        )

                for allergy in normalized_allergies:
                    stem = allergy[:-1] if len(allergy) > 3 and allergy.endswith("s") else allergy
                    if allergy in combined_text or stem in combined_text:
                        conflicts.append(
                            {
                                "day": day_idx,
                                "meal": meal_name,
                                "type": "allergen",
                                "restriction": allergy,
                                "matched_terms": [allergy],
                            }
                        )

        return conflicts

    @classmethod
    def evaluate_compliance(
        cls,
        daily_records: List[DailyNutrition],
        restrictions: Optional[List[str]] = None,
        allergies: Optional[List[str]] = None,
        goal: Optional[UserNutritionGoal] = None,
        latest_plan: Optional[MealPlan] = None,
    ) -> Dict[str, Any]:
        """Evaluate macro adherence, restriction thresholds, and meal plan ingredient conflicts."""
        normalized = [
            cls.normalize_restriction(r)
            for r in (restrictions or [])
            if isinstance(r, str) and r.strip()
        ]
        goal_type = goal.goal_type if goal else "maintenance"
        recommended = cls.compute_recommended_targets(
            goal_type=goal_type,
            restrictions=normalized,
            base_calories=goal.target_calories if (goal and goal.target_calories) else None,
        )

        count = len(daily_records)
        averages = {
            "calories": 0.0,
            "protein": 0.0,
            "carbs": 0.0,
            "fats": 0.0,
            "fiber": 0.0,
            "sodium_mg": 0.0,
        }
        if count > 0:
            sodium_sum = 0.0
            for rec in daily_records:
                averages["calories"] += float(rec.calories or 0.0)
                averages["protein"] += float(rec.protein or 0.0)
                averages["carbs"] += float(rec.carbs or 0.0)
                averages["fats"] += float(rec.fats or 0.0)
                averages["fiber"] += float(rec.fiber or 0.0)
                if rec.micronutrients_json:
                    try:
                        micros = json.loads(rec.micronutrients_json)
                        sodium_sum += float(micros.get("sodium_mg") or micros.get("sodium") or 0.0)
                    except (json.JSONDecodeError, TypeError, ValueError):
                        pass
            averages["sodium_mg"] = sodium_sum
            for key in averages:
                averages[key] = round(averages[key] / count, 1)

        warnings: List[str] = []
        penalty = 0

        if count > 0:
            if "keto" in normalized and averages["carbs"] > 50.0:
                warnings.append(
                    f"Average daily carbs ({averages['carbs']}g) exceed ketogenic limit (50g)."
                )
                penalty += 25
            elif "low-carb" in normalized and averages["carbs"] > 130.0:
                warnings.append(
                    f"Average daily carbs ({averages['carbs']}g) exceed low-carb guideline (130g)."
                )
                penalty += 20

            if "high-protein" in normalized and averages["calories"] > 0:
                prot_pct = (averages["protein"] * 4.0 / averages["calories"]) * 100.0
                if prot_pct < 28.0:
                    warnings.append(
                        f"Protein contributes {round(prot_pct, 1)}% of calories; high-protein goal recommends >=30%."
                    )
                    penalty += 20

            if "low-sodium" in normalized and averages["sodium_mg"] > 1500.0:
                warnings.append(
                    f"Average daily sodium ({averages['sodium_mg']}mg) exceeds low-sodium limit (1500mg)."
                )
                penalty += 20

            min_fiber = recommended["target_fiber"]
            if averages["fiber"] > 0 and averages["fiber"] < min_fiber * 0.75:
                warnings.append(
                    f"Average daily fiber ({averages['fiber']}g) is below target ({min_fiber}g)."
                )
                penalty += 15

            if ("vegan" in normalized or "vegetarian" in normalized) and averages["protein"] < recommended["target_protein"] * 0.75:
                warnings.append(
                    f"Average plant-based protein ({averages['protein']}g) is below recommended {recommended['target_protein']}g."
                )
                penalty += 15

        conflicts: List[Dict[str, Any]] = []
        if latest_plan and latest_plan.content_json:
            try:
                plan_data = json.loads(latest_plan.content_json)
                conflicts = cls.check_plan_conflicts(plan_data, restrictions=normalized, allergies=allergies)
            except (json.JSONDecodeError, TypeError):
                conflicts = []

        if conflicts:
            penalty += min(len(conflicts) * 15, 45)
            warnings.append(
                f"Detected {len(conflicts)} potential dietary/allergen ingredient conflict(s) in your latest meal plan."
            )

        score = max(0, 100 - penalty)
        status = "compliant" if score >= 80 else ("attention" if score >= 50 else "non_compliant")

        return {
            "days_analyzed": count,
            "restrictions": normalized,
            "allergies": list(allergies or []),
            "averages": averages,
            "recommended_targets": recommended,
            "compliance_score": score,
            "status": status,
            "warnings": warnings,
            "conflicts": conflicts,
            "micronutrients_to_watch": recommended["micronutrients_to_watch"],
        }
