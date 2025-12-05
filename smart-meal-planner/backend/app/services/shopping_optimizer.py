
import json
import os
from typing import List, Dict, Any, Tuple
from sqlmodel import Session, select
from app.models.all_models import Product, Deal, Store, MealPlan, User

class ShoppingListOptimizer:
    def __init__(self, session: Session):
        self.session = session
        self.recipes = self._load_recipes()

    def _load_recipes(self) -> List[Dict]:
        try:
            base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            file_path = os.path.join(base_path, "data", "recipes.json")
            with open(file_path, "r") as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading recipes: {e}")
            return []

    def get_recipe_by_id(self, recipe_id: str) -> Dict:
        return next((r for r in self.recipes if r["id"] == recipe_id), None)

    def generate_shopping_list(self, user: User, plan_data: Dict[str, Any], strategy: str = "min_cost") -> Dict[str, Any]:
        """
        Generates an optimized shopping list based on the meal plan.
        strategies: 'min_cost', 'convenience' (fewer stores), 'balanced'
        """

        # 1. Consolidate Ingredients
        consolidated = self._consolidate_ingredients(plan_data, user.household_size)

        # 2. Find Prices for Each Ingredient
        priced_items = []
        for key, qty_data in consolidated.items():
            # key is (name, unit)
            item_name = key[0]
            unit = key[1]
            best_options = self._find_prices_for_ingredient(item_name, unit)
            priced_items.append({
                "ingredient": item_name,
                "quantity": qty_data["qty"],
                "unit": unit,
                "options": best_options
            })

        # 3. Optimize based on strategy
        optimization_result = self._optimize_routes(priced_items, strategy)

        return optimization_result

    def _consolidate_ingredients(self, plan_data: Dict, household_size: int) -> Dict[Tuple[str, str], Dict]:
        """
        Returns: { ("Chicken Breast", "kg"): { "qty": 2.5, "unit": "kg" }, ... }
        Handles unit conversion where possible.
        """
        consolidated = {} # Key: (name, unit)

        scale = max(1, household_size / 4)

        for day in plan_data.get("days", []):
            for meal in day.get("meals", []):
                recipe_id = meal.get("id")
                if recipe_id:
                    recipe = self.get_recipe_by_id(recipe_id)
                    if recipe:
                        for ing in recipe["ingredients"]:
                            name = ing["item"]
                            qty = ing["quantity"] * scale
                            unit = ing["unit"]

                            # Normalization helpers
                            # Convert everything to lowercase for matching
                            # But keep original casing for display? Let's assume schema matches.

                            # Try to merge with existing entry if units are compatible
                            merged = False

                            # Check existing keys for this item name
                            existing_keys = [k for k in consolidated.keys() if k[0] == name]

                            for k in existing_keys:
                                existing_unit = k[1]
                                if existing_unit == unit:
                                    consolidated[k]["qty"] += qty
                                    merged = True
                                    break

                                # Simple conversions
                                if existing_unit == "kg" and unit == "lb":
                                    consolidated[k]["qty"] += qty * 0.453592
                                    merged = True
                                    break
                                elif existing_unit == "lb" and unit == "kg":
                                    consolidated[k]["qty"] += qty * 2.20462
                                    merged = True
                                    break
                                elif existing_unit == "L" and unit == "ml":
                                    consolidated[k]["qty"] += qty / 1000.0
                                    merged = True
                                    break

                            if not merged:
                                consolidated[(name, unit)] = {"qty": qty, "unit": unit}

        # Round quantities
        for k, v in consolidated.items():
            v["qty"] = round(v["qty"], 2)

        return consolidated

    def _find_prices_for_ingredient(self, ingredient_name: str, required_unit: str) -> List[Dict]:
        """
        Returns a list of price options. Handles unit conversion vs store pricing.
        """
        product = self.session.exec(select(Product).where(Product.name == ingredient_name)).first()

        options = []
        if not product:
            return []

        deals = self.session.exec(select(Deal).where(Deal.product_id == product.id)).all()
        stores = self.session.exec(select(Store)).all()
        store_map = {s.id: s for s in stores}

        for deal in deals:
            store = store_map.get(deal.store_id)
            if store:
                # Price is per product.unit_type
                # We need to convert price to required_unit
                price = deal.price

                # Conversion logic
                # if product.unit_type == "kg" and required_unit == "lb":
                #     price = price * 0.453592 (Price per lb is less than price per kg)

                conversion_factor = 1.0
                if product.unit_type == "kg" and required_unit == "lb":
                    conversion_factor = 0.453592
                elif product.unit_type == "lb" and required_unit == "kg":
                    conversion_factor = 2.20462

                # If units are totally different (e.g. "each" vs "kg"), we can't easily convert without more data.
                # For MVP, assume 1:1 if unknown, or rely on data seeding being consistent.

                final_price = price * conversion_factor

                options.append({
                    "store_id": store.id,
                    "store_name": store.name,
                    "chain": store.chain,
                    "price": final_price, # Price per REQUIRED unit
                    "discount_pct": deal.discount_pct,
                    "unit_type": required_unit
                })

        return options

    def _optimize_routes(self, priced_items: List[Dict], strategy: str) -> Dict[str, Any]:
        stores_usage = {}
        total_estimated_savings = 0.0
        total_cost_regular = 0.0
        unmatched_items = []

        # Single Store Calculation
        # We need to know the cost of the ENTIRE list at each store.
        all_stores = set()
        for item in priced_items:
            for opt in item["options"]:
                all_stores.add(opt["store_name"])

        single_store_baskets = {s: {"total": 0.0, "missing": []} for s in all_stores}

        # Calculate single store totals
        for item in priced_items:
            for store_name in single_store_baskets.keys():
                # Find option for this store
                opt = next((o for o in item["options"] if o["store_name"] == store_name), None)
                if opt:
                    cost = opt["price"] * item["quantity"]
                    single_store_baskets[store_name]["total"] += cost
                else:
                    single_store_baskets[store_name]["missing"].append(item["ingredient"])

        # Strategy Logic
        for item in priced_items:
            options = item["options"]
            if not options:
                unmatched_items.append(item)
                continue

            valid_options = []
            for opt in options:
                cost = opt["price"] * item["quantity"]
                if opt["discount_pct"] > 0:
                     reg_price = opt["price"] / (1 - (opt["discount_pct"]/100))
                     reg_cost = reg_price * item["quantity"]
                else:
                     reg_cost = cost

                valid_options.append({
                    **opt,
                    "total_item_cost": round(cost, 2),
                    "regular_item_cost": round(reg_cost, 2)
                })

            if not valid_options:
                unmatched_items.append(item)
                continue

            # Selection
            selected_option = None
            if strategy == "convenience":
                # Pick the store that has the lowest TOTAL basket cost (single store)
                # But filter for stores that actually have THIS item.

                # Find valid stores that have this item
                valid_store_names = [o["store_name"] for o in valid_options]

                # Sort single_store_baskets by total cost, picking the best one that contains this item
                # This approximates "Shop at the best single store"
                best_store = None
                min_total = float('inf')

                for s_name in valid_store_names:
                    # Penalize missing items in the total score to avoid picking a cheap store that has nothing
                    basket = single_store_baskets[s_name]
                    penalty = len(basket["missing"]) * 100 # Heavy penalty for missing items
                    score = basket["total"] + penalty

                    if score < min_total:
                        min_total = score
                        best_store = s_name

                if best_store:
                    selected_option = next(o for o in valid_options if o["store_name"] == best_store)
                else:
                    # Fallback
                    valid_options.sort(key=lambda x: x["total_item_cost"])
                    selected_option = valid_options[0]

            else: # min_cost
                valid_options.sort(key=lambda x: x["total_item_cost"])
                selected_option = valid_options[0]

            # Aggregation
            s_name = selected_option["store_name"]
            if s_name not in stores_usage:
                stores_usage[s_name] = {
                    "store_id": selected_option["store_id"],
                    "chain": selected_option["chain"],
                    "items": [],
                    "subtotal": 0.0,
                    "savings": 0.0
                }

            stores_usage[s_name]["items"].append({
                "name": item["ingredient"],
                "qty": item["quantity"],
                "unit": item["unit"],
                "price_per_unit": selected_option["price"],
                "cost": selected_option["total_item_cost"],
                "discount_pct": selected_option["discount_pct"]
            })

            stores_usage[s_name]["subtotal"] += selected_option["total_item_cost"]
            stores_usage[s_name]["savings"] += selected_option["regular_item_cost"] - selected_option["total_item_cost"]

            total_estimated_savings += selected_option["regular_item_cost"] - selected_option["total_item_cost"]
            total_cost_regular += selected_option["regular_item_cost"]

        recommended_stores = []
        for s_name, data in stores_usage.items():
            data["subtotal"] = round(data["subtotal"], 2)
            data["savings"] = round(data["savings"], 2)
            data["store"] = s_name
            recommended_stores.append(data)

        recommended_stores.sort(key=lambda x: x["subtotal"], reverse=True)

        # Format single store comparison for frontend
        single_store_formatted = []
        for s_name, data in single_store_baskets.items():
            single_store_formatted.append({
                "store": s_name,
                "total": round(data["total"], 2),
                "missing_count": len(data["missing"])
            })
        single_store_formatted.sort(key=lambda x: (x["missing_count"], x["total"]))

        return {
            "strategy": strategy,
            "recommended_stores": recommended_stores,
            "total_cost": round(sum(s["subtotal"] for s in recommended_stores), 2),
            "total_savings": round(total_estimated_savings, 2),
            "total_regular_cost": round(total_cost_regular, 2),
            "unmatched_items": [u["ingredient"] for u in unmatched_items],
            "single_store_comparison": single_store_formatted
        }
