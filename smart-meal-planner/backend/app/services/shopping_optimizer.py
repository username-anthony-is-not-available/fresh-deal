
import json
import os
from typing import List, Dict, Any, Tuple
from sqlmodel import select, or_, col
from app.models.all_models import Product, Deal, Store, User, PantryItem
from app.services.ingredient_matching_service import ingredient_matching_service

class ShoppingListOptimizer:
    def __init__(self, session):
        self.session = session # Can be AsyncSession or Sync Session
        self.recipes = self._load_recipes()
        self.ingredient_matcher = ingredient_matching_service

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

    async def generate_shopping_list_async(self, user: User, plan_data: Dict[str, Any], strategy: str = "min_cost", preferred_stores: List[str] = None) -> Dict[str, Any]:
        """
        Async version of generate_shopping_list.
        """
        # 1. Consolidate Ingredients
        consolidated = self._consolidate_ingredients(plan_data, user.household_size)

        # 2. Subtract Pantry Items
        pantry_result = await self.session.execute(select(PantryItem).where(PantryItem.user_id == user.id))
        pantry_items = pantry_result.scalars().all()
        self._subtract_pantry(consolidated, pantry_items)

        # 3. Find Prices for Each Ingredient
        priced_items = []
        for key, qty_data in consolidated.items():
            # key is (name, unit)
            item_name = key[0]
            unit = key[1]
            best_options = await self._find_prices_for_ingredient_async(item_name, unit)
            priced_items.append({
                "ingredient": item_name,
                "quantity": qty_data["qty"],
                "unit": unit,
                "options": best_options
            })

        # 3. Optimize based on strategy
        optimization_result = self._optimize_routes(priced_items, strategy, preferred_stores)

        return optimization_result

    def generate_shopping_list(self, user: User, plan_data: Dict[str, Any], strategy: str = "min_cost", preferred_stores: List[str] = None) -> Dict[str, Any]:
        """
        Synchronous version (for tests or sync contexts).
        """
        # 1. Consolidate Ingredients
        consolidated = self._consolidate_ingredients(plan_data, user.household_size)

        # 2. Subtract Pantry Items
        pantry_items = self.session.exec(select(PantryItem).where(PantryItem.user_id == user.id)).all()
        self._subtract_pantry(consolidated, pantry_items)

        # 3. Find Prices for Each Ingredient
        priced_items = []
        for key, qty_data in consolidated.items():
            item_name = key[0]
            unit = key[1]
            best_options = self._find_prices_for_ingredient_sync(item_name, unit)
            priced_items.append({
                "ingredient": item_name,
                "quantity": qty_data["qty"],
                "unit": unit,
                "options": best_options
            })

        # 3. Optimize based on strategy
        return self._optimize_routes(priced_items, strategy, preferred_stores)

    def _subtract_pantry(self, consolidated: Dict, pantry_items: List[PantryItem]):
        """
        Subtracts quantities of items already in the pantry from the consolidated list
        using bilingual synonym and fuzzy ingredient matching plus unit conversions.
        """
        for p_item in pantry_items:
            p_name = (p_item.name or "").strip()
            qty = float(p_item.quantity or 0)
            unit = (p_item.unit or "each").strip()
            if not p_name or qty <= 0:
                continue

            matching_keys = [
                k for k in consolidated.keys()
                if self.ingredient_matcher.is_match(k[0], p_name)
            ]

            for k in matching_keys:
                existing_unit = k[1]
                converted_qty, _ = self.ingredient_matcher.convert_quantity(qty, unit, existing_unit, k[0])
                if converted_qty > 0:
                    current_needed = consolidated[k]["qty"]
                    if current_needed <= converted_qty:
                        consolidated[k]["qty"] = 0
                        qty -= self.ingredient_matcher.convert_quantity(current_needed, existing_unit, unit, k[0])[0]
                    else:
                        consolidated[k]["qty"] -= converted_qty
                        qty = 0
                if qty <= 0:
                    break

        # Remove items with zero or negative quantity
        keys_to_remove = [k for k, v in consolidated.items() if v["qty"] <= 0.001]
        for k in keys_to_remove:
            del consolidated[k]

    def _consolidate_ingredients(self, plan_data: Dict, household_size: int) -> Dict[Tuple[str, str], Dict]:
        """
        Returns: { ("Chicken Breast", "kg"): { "qty": 2.5, "unit": "kg" }, ... }
        Handles unit conversion where possible.
        """
        consolidated = {} # Key: (name, unit)

        scale = max(1, household_size / 4)

        # Handle both 'meal_plan' (new format) and 'days' (legacy/mock format)
        days = plan_data.get("meal_plan", plan_data.get("days", []))

        for day in days:
            # Check if day has 'meals' array (legacy) or structured breakfast/lunch/dinner (new)
            meals_to_process = []
            if "meals" in day and isinstance(day["meals"], list):
                meals_to_process = day["meals"]
            else:
                for meal_type in ["breakfast", "lunch", "dinner"]:
                    if meal_type in day:
                        # Normalize to look like the legacy structure for processing
                        m = day[meal_type]
                        # Ensure it has 'ingredients'
                        if m:
                            meals_to_process.append(m)

            for meal in meals_to_process:
                # If meal is fully enriched it has 'ingredients'
                ingredients = meal.get("ingredients", [])

                # If ingredients is missing, try to lookup by ID (legacy path)
                if not ingredients:
                    recipe_id = meal.get("id") or meal.get("recipe_id")
                    if recipe_id:
                        recipe = self.get_recipe_by_id(recipe_id)
                        if recipe:
                             ingredients = recipe["ingredients"]

                for ing in ingredients:
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

    async def _find_prices_for_ingredient_async(self, ingredient_name: str, required_unit: str) -> List[Dict]:
        """
        Async: Returns a list of price options using fuzzy matching.
        """
        normalized_name = self.ingredient_matcher.normalize(ingredient_name)
        if not normalized_name:
            return []

        # Broad DB filter: find products containing any word from the normalized name
        words = normalized_name.split()
        filters = [col(Product.name).ilike(f"%{w}%") for w in words if len(w) > 2]

        if not filters:
            # Fallback to exact-ish match if no long words
            stmt = select(Product).where(Product.name.ilike(f"%{normalized_name}%"))
        else:
            stmt = select(Product).where(or_(*filters))

        result = await self.session.execute(stmt)
        candidate_products = result.scalars().all()

        # Refine with fuzzy matching
        best_product = None
        best_score = 0

        for p in candidate_products:
            if self.ingredient_matcher.is_match(ingredient_name, p.name):
                # Calculate a score to pick the best if multiple match
                from thefuzz import fuzz
                score = fuzz.token_set_ratio(normalized_name, self.ingredient_matcher.normalize(p.name))
                if score > best_score:
                    best_score = score
                    best_product = p

        if not best_product:
            return []

        deals_result = await self.session.execute(select(Deal).where(Deal.product_id == best_product.id))
        deals = deals_result.scalars().all()

        stores_result = await self.session.execute(select(Store))
        stores = stores_result.scalars().all()
        store_map = {s.id: s for s in stores}

        return self._calculate_options(deals, store_map, best_product, required_unit)

    def _find_prices_for_ingredient_sync(self, ingredient_name: str, required_unit: str) -> List[Dict]:
        """
        Sync: Returns a list of price options using fuzzy matching.
        """
        normalized_name = self.ingredient_matcher.normalize(ingredient_name)
        if not normalized_name:
            return []

        words = normalized_name.split()
        filters = [col(Product.name).ilike(f"%{w}%") for w in words if len(w) > 2]

        if not filters:
            stmt = select(Product).where(Product.name.ilike(f"%{normalized_name}%"))
        else:
            stmt = select(Product).where(or_(*filters))

        candidate_products = self.session.exec(stmt).all()

        best_product = None
        best_score = 0

        for p in candidate_products:
            if self.ingredient_matcher.is_match(ingredient_name, p.name):
                from thefuzz import fuzz
                score = fuzz.token_set_ratio(normalized_name, self.ingredient_matcher.normalize(p.name))
                if score > best_score:
                    best_score = score
                    best_product = p

        if not best_product:
            return []

        deals = self.session.exec(select(Deal).where(Deal.product_id == best_product.id)).all()
        stores = self.session.exec(select(Store)).all()
        store_map = {s.id: s for s in stores}

        return self._calculate_options(deals, store_map, best_product, required_unit)

    def _calculate_options(self, deals, store_map, product, required_unit):
        options = []
        for deal in deals:
            store = store_map.get(deal.store_id)
            if store:
                price = deal.price
                conversion_factor = 1.0
                if product.unit_type == "kg" and required_unit == "lb":
                    conversion_factor = 0.453592
                elif product.unit_type == "lb" and required_unit == "kg":
                    conversion_factor = 2.20462

                final_price = price * conversion_factor

                options.append({
                    "store_id": store.id,
                    "store_name": store.name,
                    "chain": store.chain,
                    "price": final_price,
                    "discount_pct": deal.discount_pct,
                    "unit_type": required_unit,
                    "category": product.category
                })
        return options

    def _optimize_routes(
        self,
        priced_items: List[Dict],
        strategy: str,
        preferred_stores: List[str] = None,
        max_stores: int = None,
        travel_cost_per_stop: float = None,
    ) -> Dict[str, Any]:
        from app.core.config import settings
        import itertools

        if max_stores is None:
            max_stores = getattr(settings, "MAX_STORES_PER_TRIP", 2)
        if travel_cost_per_stop is None:
            travel_cost_per_stop = getattr(settings, "TRAVEL_COST_PER_STOP", 3.50)
        stores_usage = {}
        total_estimated_savings = 0.0
        total_cost_regular = 0.0
        unmatched_items = []

        # Single Store Calculation
        all_stores = set()
        for item in priced_items:
            for opt in item["options"]:
                all_stores.add(opt["store_name"])

        total_items_requested = len(priced_items)

        single_store_baskets = {
            s: {"total": 0.0, "regular_total": 0.0, "items_count": 0, "missing": []}
            for s in all_stores
        }

        # Calculate single store totals
        for item in priced_items:
            for store_name in single_store_baskets.keys():
                opt = next((o for o in item["options"] if o["store_name"] == store_name), None)
                if opt:
                    cost = opt["price"] * item["quantity"]

                    if opt.get("discount_pct") and opt["discount_pct"] > 0:
                        regular_price = opt["price"] / (1 - (opt["discount_pct"] / 100))
                    else:
                        regular_price = opt["price"]

                    regular_cost = regular_price * item["quantity"]

                    single_store_baskets[store_name]["total"] += cost
                    single_store_baskets[store_name]["regular_total"] += regular_cost
                    single_store_baskets[store_name]["items_count"] += 1
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
                if opt.get("discount_pct") and opt["discount_pct"] > 0:
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
                valid_store_names = [o["store_name"] for o in valid_options]
                best_store = None
                min_total = float('inf')

                for s_name in valid_store_names:
                    basket = single_store_baskets[s_name]

                    # Grouping & Priority Logic:
                    penalty = len(basket["missing"]) * 100

                    priority_bonus = 0
                    if preferred_stores and s_name in preferred_stores:
                        priority_bonus = 500

                    score = basket["total"] + penalty - priority_bonus

                    if score < min_total:
                        min_total = score
                        best_store = s_name

                if best_store:
                    selected_option = next((o for o in valid_options if o["store_name"] == best_store), None)

                if not selected_option:
                    valid_options.sort(key=lambda x: x["total_item_cost"])
                    selected_option = valid_options[0]

            else: # min_cost with store-hopping penalty & max_stores constraint
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
                "discount_pct": selected_option.get("discount_pct"),
                "category": selected_option.get("category", "Grocery")
            })

            stores_usage[s_name]["subtotal"] += selected_option["total_item_cost"]
            stores_usage[s_name]["savings"] += selected_option["regular_item_cost"] - selected_option["total_item_cost"]

            total_estimated_savings += selected_option["regular_item_cost"] - selected_option["total_item_cost"]
            total_cost_regular += selected_option["regular_item_cost"]

        # Store-Hopping Consolidation & Cap Enforcer
        # If min_cost chose more than max_stores, or if travel penalty exceeds savings, consolidate!
        if strategy == "min_cost" and len(stores_usage) > 1 and all_stores:
            # Check best single store option
            complete_single_stores = [
                (s_name, b) for s_name, b in single_store_baskets.items()
                if len(b["missing"]) == 0
            ]
            if not complete_single_stores:
                # Store with least missing
                min_missing = min(len(b["missing"]) for b in single_store_baskets.values())
                complete_single_stores = [
                    (s_name, b) for s_name, b in single_store_baskets.items()
                    if len(b["missing"]) == min_missing
                ]

            best_single_name, best_single_basket = min(
                complete_single_stores,
                key=lambda x: x[1]["total"]
            )

            current_basket_cost = sum(d["subtotal"] for d in stores_usage.values())
            num_stops = len(stores_usage)
            travel_penalty = (num_stops - 1) * travel_cost_per_stop

            # Condition 1: If 2+ stores save LESS than the travel cost compared to 1 store, consolidate to 1 store!
            # Only consolidate if the single store covers the items (missing count == 0 or equal)
            if len(best_single_basket["missing"]) == 0 and (current_basket_cost + travel_penalty) >= best_single_basket["total"]:
                # Consolidate into best_single_name
                stores_usage = {}
                total_estimated_savings = 0.0
                total_cost_regular = 0.0
                for item in priced_items:
                    opts = item["options"]
                    opt = next((o for o in opts if o["store_name"] == best_single_name), None)
                    if not opt and opts:
                        opts_sorted = sorted(opts, key=lambda x: x["price"])
                        opt = opts_sorted[0]
                    if opt:
                        cost = opt["price"] * item["quantity"]
                        reg_price = opt["price"] / (1 - (opt.get("discount_pct", 0) / 100)) if opt.get("discount_pct") else opt["price"]
                        reg_cost = reg_price * item["quantity"]

                        sn = opt["store_name"]
                        if sn not in stores_usage:
                            stores_usage[sn] = {
                                "store_id": opt["store_id"],
                                "chain": opt["chain"],
                                "items": [],
                                "subtotal": 0.0,
                                "savings": 0.0
                            }
                        stores_usage[sn]["items"].append({
                            "name": item["ingredient"],
                            "qty": item["quantity"],
                            "unit": item["unit"],
                            "price_per_unit": opt["price"],
                            "cost": round(cost, 2),
                            "discount_pct": opt.get("discount_pct"),
                            "category": opt.get("category", "Grocery")
                        })
                        stores_usage[sn]["subtotal"] += cost
                        stores_usage[sn]["savings"] += (reg_cost - cost)
                        total_estimated_savings += (reg_cost - cost)
                        total_cost_regular += reg_cost

            # Condition 2: If still > max_stores, enforce hard cap on top max_stores by spend
            elif len(stores_usage) > max_stores:
                top_stores = set(sorted(stores_usage.keys(), key=lambda s: stores_usage[s]["subtotal"], reverse=True)[:max_stores])
                # Re-assign items from non-top stores to the best available top store
                new_usage = {s: stores_usage[s] for s in top_stores}
                for s_name, data in list(stores_usage.items()):
                    if s_name not in top_stores:
                        for itm in data["items"]:
                            # Find best option among top_stores
                            p_item = next((p for p in priced_items if p["ingredient"] == itm["name"]), None)
                            assigned = False
                            if p_item:
                                top_opts = [o for o in p_item["options"] if o["store_name"] in top_stores]
                                if top_opts:
                                    top_opts.sort(key=lambda x: x["price"])
                                    chosen_opt = top_opts[0]
                                    cs = chosen_opt["store_name"]
                                    c_cost = chosen_opt["price"] * itm["qty"]
                                    new_usage[cs]["items"].append({
                                        **itm,
                                        "price_per_unit": chosen_opt["price"],
                                        "cost": round(c_cost, 2)
                                    })
                                    new_usage[cs]["subtotal"] += c_cost
                                    assigned = True
                            if not assigned:
                                # Keep in primary top store
                                p_top = list(top_stores)[0]
                                new_usage[p_top]["items"].append(itm)
                                new_usage[p_top]["subtotal"] += itm["cost"]
                stores_usage = new_usage

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
            savings = data["regular_total"] - data["total"]
            efficiency = (data["items_count"] / total_items_requested * 100) if total_items_requested > 0 else 0
            single_store_formatted.append({
                "name": s_name,
                "total": round(data["total"], 2),
                "items_count": data["items_count"],
                "savings": round(savings, 2),
                "trip_efficiency": round(efficiency, 1)
            })
        single_store_formatted.sort(key=lambda x: (len(single_store_baskets[x["name"]]["missing"]), x["total"]))

        # Create detailed comparison data
        detailed_comparison = []
        all_store_names = sorted(list(all_stores))
        for item in priced_items:
            ingredient_details = {
                "ingredient": item["ingredient"],
                "quantity": item["quantity"],
                "unit": item["unit"],
                "prices": {}
            }
            # Create a map of store_name -> price for the current item
            options_by_store = {opt["store_name"]: opt["price"] for opt in item["options"]}

            # Populate prices for all known stores, using None if not available
            for store_name in all_store_names:
                price = options_by_store.get(store_name)
                ingredient_details["prices"][store_name] = round(price * item["quantity"], 2) if price is not None else None

            detailed_comparison.append(ingredient_details)

        total_items_found = sum(len(s["items"]) for s in recommended_stores)
        overall_efficiency = (total_items_found / total_items_requested * 100) if total_items_requested > 0 else 0

        basket_total = round(sum(s["subtotal"] for s in recommended_stores), 2)
        extra_stops = max(0, len(recommended_stores) - 1)
        travel_penalty = round(extra_stops * travel_cost_per_stop, 2)
        net_cost_with_travel = round(basket_total + travel_penalty, 2)
        net_savings_with_travel = round(total_estimated_savings - travel_penalty, 2)

        return {
            "strategy": strategy,
            "recommended_stores": recommended_stores,
            "total_cost": basket_total,
            "travel_penalty_cost": travel_penalty,
            "net_cost_with_travel": net_cost_with_travel,
            "net_savings_with_travel": net_savings_with_travel,
            "max_stores_limit": max_stores,
            "travel_cost_per_stop": travel_cost_per_stop,
            "total_savings": round(total_estimated_savings, 2),
            "total_regular_cost": round(total_cost_regular, 2),
            "unmatched_items": [u["ingredient"] for u in unmatched_items],
            "single_store_comparison": single_store_formatted,
            "detailed_comparison": detailed_comparison,
            "all_stores": all_store_names,
            "total_items_count": total_items_requested,
            "trip_efficiency": round(overall_efficiency, 1)
        }
