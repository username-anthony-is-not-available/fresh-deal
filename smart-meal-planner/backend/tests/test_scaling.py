
import pytest
from app.services.recipe_service import RecipeService

def test_scale_ingredients_double():
    ingredients = [
        {"item": "Chicken", "quantity": 0.5, "unit": "kg"},
        {"item": "Broccoli", "quantity": 1, "unit": "each"}
    ]
    base_servings = 2
    target_servings = 4

    scaled = RecipeService.scale_ingredients(ingredients, base_servings, target_servings)

    assert scaled[0]["quantity"] == 1.0
    assert scaled[1]["quantity"] == 2.0
    assert scaled[0]["item"] == "Chicken"

def test_scale_ingredients_half():
    ingredients = [
        {"item": "Chicken", "quantity": 0.5, "unit": "kg"},
        {"item": "Eggs", "quantity": 4, "unit": "each"}
    ]
    base_servings = 4
    target_servings = 2

    scaled = RecipeService.scale_ingredients(ingredients, base_servings, target_servings)

    assert scaled[0]["quantity"] == 0.25
    assert scaled[1]["quantity"] == 2.0

def test_scale_ingredients_no_change():
    ingredients = [{"item": "Salt", "quantity": 1, "unit": "tsp"}]
    scaled = RecipeService.scale_ingredients(ingredients, 4, 4)
    assert scaled == ingredients

def test_scale_ingredients_zero_servings():
    ingredients = [{"item": "Salt", "quantity": 1, "unit": "tsp"}]
    # Should return original if base_servings is 0 to avoid division by zero
    scaled = RecipeService.scale_ingredients(ingredients, 0, 4)
    assert scaled == ingredients

def test_scale_ingredients_non_numeric_quantity():
    ingredients = [{"item": "Salt", "quantity": "a pinch", "unit": ""}]
    scaled = RecipeService.scale_ingredients(ingredients, 2, 4)
    assert scaled[0]["quantity"] == "a pinch"
