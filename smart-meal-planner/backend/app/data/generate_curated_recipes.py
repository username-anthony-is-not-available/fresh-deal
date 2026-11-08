"""
Bulk Recipe Generator & Curator for Quebec Flyer Staples.
Generates and curates 500+ recipes designed around high-frequency flyer staples:
- Pork tenderloin, chops, ground pork
- Medium ground beef, beef roasts, stew beef
- Chicken breasts, thighs, drumsticks, whole chicken
- Salmon, trout, cod
- Halloumi, feta, tofu, legumes
- Root vegetables, bell peppers, broccoli, cauliflower, cabbage, apples
"""

import json
import os
import random
from typing import List, Dict, Any

def create_recipe(
    recipe_id: str,
    name: str,
    cuisine: str,
    meal_type: str,
    prep_time: int,
    difficulty: str,
    servings: int,
    ingredients: List[Dict[str, Any]],
    calories: int,
    protein: int,
    carbs: int,
    fat: int,
    fiber: int,
    instructions: List[str],
    tags: List[str],
    dietary_tags: List[str] = None,
    allergens: List[str] = None
) -> Dict[str, Any]:
    return {
        "id": recipe_id,
        "name": name,
        "cuisine": cuisine,
        "meal_type": meal_type,
        "prep_time_minutes": prep_time,
        "difficulty": difficulty,
        "servings": servings,
        "ingredients": ingredients,
        "nutrition": {
            "calories": calories,
            "protein": protein,
            "carbs": carbs,
            "fat": fat,
            "fiber": fiber
        },
        "instructions": instructions,
        "tags": tags,
        "dietary_tags": dietary_tags or [],
        "allergens": allergens or []
    }


def generate_curated_dataset() -> List[Dict[str, Any]]:
    recipes_file = os.path.join(os.path.dirname(__file__), "recipes.json")
    existing_recipes = []
    if os.path.exists(recipes_file):
        with open(recipes_file, "r", encoding="utf-8") as f:
            existing_recipes = json.load(f)

    existing_names = {r["name"].lower() for r in existing_recipes}
    all_recipes = list(existing_recipes)
    idx = len(all_recipes) + 1

    # Templates for systematic generation across Quebec grocery staples
    categories = [
        # 1. Ground Beef & Pork Staples (Family packs)
        {
            "protein": "Ground Beef (Medium)",
            "unit": "kg",
            "qty": 0.6,
            "allergens": ["gluten"],
            "variations": [
                ("Classic Quebec Pâté Chinois", "Québécoise", "Dinner", 45, "easy", 6,
                 [("Creamed Corn", 1, "can"), ("Corn Kernels", 1, "can"), ("Potatoes", 1.0, "kg"), ("Butter", 30, "g"), ("Milk", 60, "ml")],
                 520, 34, 48, 22, 5,
                 ["Brown ground beef with onions, season with salt and pepper.", "Layer beef at the bottom of a baking dish.", "Spread creamed and kernel corn evenly over the meat.", "Top with mashed potatoes and butter dots.", "Bake at 375°F (190°C) for 30 minutes until golden."],
                 ["quebec-classic", "family-friendly", "batch-cooking", "leftovers-friendly"]),
                ("Homestyle Shepherd's Pie", "Canadian Comfort", "Dinner", 45, "easy", 4,
                 [("Carrots (Diced)", 200, "g"), ("Frozen Peas", 150, "g"), ("Beef Broth", 250, "ml"), ("Potatoes", 800, "g"), ("Worcestershire Sauce", 15, "ml")],
                 490, 35, 42, 20, 6,
                 ["Brown beef, drain fat.", "Add carrots, peas, and broth with Worcestershire sauce; simmer 10 mins.", "Transfer to baking dish and cover with mashed potatoes.", "Bake at 375°F for 25 mins."],
                 ["comfort-food", "budget-friendly", "batch-cooking"]),
                ("Slow-Cooker Beef & Black Bean Chili", "Mexican", "Dinner", 25, "easy", 6,
                 [("Black Beans (Canned)", 2, "can"), ("Diced Tomatoes", 1, "can"), ("Bell Peppers", 2, "each"), ("Chili Powder", 15, "g"), ("Onions", 1, "each")],
                 440, 36, 45, 14, 11,
                 ["Brown ground beef in a skillet.", "Combine all ingredients in a slow cooker.", "Cook on low for 6 hours or high for 3 hours.", "Serve with shredded cheese or sour cream."],
                 ["slow-cooker", "high-protein", "freezer-friendly", "batch-cooking"]),
                ("Classic Italian Meatballs with Spaghetti", "Italian", "Dinner", 35, "medium", 4,
                 [("Spaghetti", 400, "g"), ("Tomato Sauce", 650, "ml"), ("Breadcrumbs", 50, "g"), ("Parmesan Cheese", 40, "g"), ("Eggs", 1, "each")],
                 580, 38, 65, 18, 5,
                 ["Mix ground beef, breadcrumbs, egg, and parmesan.", "Roll into 16 meatballs and sear in olive oil.", "Simmer meatballs in tomato sauce for 20 mins.", "Serve over boiled spaghetti."],
                 ["italian", "family-favorite", "leftovers-friendly"]),
                ("Stuffed Bell Peppers with Cheesy Rice", "Canadian Comfort", "Dinner", 40, "easy", 4,
                 [("Bell Peppers", 4, "each"), ("White Rice (Cooked)", 300, "g"), ("Tomato Sauce", 200, "ml"), ("Cheddar Cheese", 100, "g"), ("Garlic", 2, "cloves")],
                 460, 31, 40, 20, 6,
                 ["Cut tops off peppers and remove seeds.", "Brown beef with garlic, then stir in cooked rice and tomato sauce.", "Stuff mixture into peppers and top with cheddar cheese.", "Bake covered at 375°F for 30 minutes."],
                 ["stuffed-vegetable", "gluten-free", "colorful"]),
                ("Hearty Beef & Cabbage Skillet", "Québécoise", "Dinner", 25, "easy", 4,
                 [("Green Cabbage (Shredded)", 500, "g"), ("Diced Tomatoes", 1, "can"), ("Yellow Onions", 1, "each"), ("Olive Oil", 15, "ml")],
                 390, 30, 24, 18, 7,
                 ["Brown ground beef and diced onion in a large Dutch oven.", "Add shredded cabbage and canned tomatoes.", "Cover and simmer for 15-20 minutes until cabbage is tender.", "Season with paprika, salt, and black pepper."],
                 ["low-carb", "budget-staple", "high-fiber"]),
            ]
        },
        # 2. Chicken Breasts & Thighs (High frequency flyer specials)
        {
            "protein": "Chicken Breast (Boneless)",
            "unit": "kg",
            "qty": 0.5,
            "allergens": [],
            "variations": [
                ("Maple Dijon Glazed Chicken Breasts", "Québécoise", "Dinner", 25, "easy", 4,
                 [("Pure Maple Syrup", 45, "ml"), ("Dijon Mustard", 30, "ml"), ("Garlic", 2, "cloves"), ("Carrots (Roasted)", 400, "g"), ("Olive Oil", 15, "ml")],
                 410, 42, 28, 12, 4,
                 ["Whisk maple syrup, Dijon mustard, and minced garlic.", "Place chicken breasts in a baking dish and brush generously with glaze.", "Roast alongside carrots at 400°F (200°C) for 22 minutes.", "Drizzle remaining pan juices over chicken."],
                 ["quebec-maple", "high-protein", "quick-dinner"]),
                ("Sheet Pan Greek Chicken with Bell Peppers & Feta", "Greek/Mediterranean", "Dinner", 30, "easy", 4,
                 [("Bell Peppers", 2, "each"), ("Red Onions", 1, "each"), ("Feta Cheese", 100, "g"), ("Olive Oil", 30, "ml"), ("Oregano", 10, "g")],
                 440, 40, 16, 22, 4,
                 ["Toss chicken pieces, peppers, and onions with olive oil and oregano.", "Spread evenly on a baking sheet.", "Roast at 400°F for 20 minutes.", "Crumble feta over top and broil for 2 minutes."],
                 ["mediterranean", "sheet-pan", "keto-friendly", "low-carb"]),
                ("Crispy Garlic Butter Chicken Bites with Broccoli", "Quick & Easy", "Dinner", 20, "easy", 4,
                 [("Broccoli Florets", 400, "g"), ("Butter", 30, "g"), ("Garlic", 4, "cloves"), ("Soy Sauce", 15, "ml"), ("Olive Oil", 15, "ml")],
                 380, 41, 12, 18, 4,
                 ["Cut chicken into bite-sized cubes.", "Sear chicken in olive oil over high heat until browned.", "Add butter, garlic, and broccoli florets to pan with 2 tbsp water.", "Cover and steam 4 minutes until crisp-tender."],
                 ["fast-weeknight", "high-protein", "low-carb"]),
                ("Creamy Tuscan Garlic Chicken", "Italian", "Dinner", 30, "medium", 4,
                 [("Spinach (Fresh)", 150, "g"), ("Cherry Tomatoes", 200, "g"), ("Heavy Cream (35%)", 120, "ml"), ("Parmesan Cheese", 50, "g"), ("Garlic", 3, "cloves")],
                 510, 43, 10, 32, 3,
                 ["Sear seasoned chicken breasts until golden; set aside.", "Sauté garlic, cherry tomatoes, and fresh spinach.", "Stir in heavy cream and parmesan; bring to a gentle simmer.", "Return chicken to pan and spoon sauce over top."],
                 ["comfort-food", "keto", "restaurant-style"]),
                ("Chicken Fajitas with Peppers and Onions", "Mexican", "Dinner", 25, "easy", 4,
                 [("Bell Peppers (Assorted)", 3, "each"), ("Onions", 1, "each"), ("Fajita Seasoning", 20, "g"), ("Flour Tortillas", 8, "each"), ("Lime", 1, "each")],
                 460, 36, 46, 14, 5,
                 ["Slice chicken and vegetables into strips.", "Sauté in oil with fajita seasoning over medium-high heat for 10-12 mins.", "Squeeze fresh lime juice over skillet.", "Serve in warmed tortillas."],
                 ["family-friendly", "mexican", "quick-prep"]),
            ]
        },
        # 3. Pork Tenderloin & Chops (Quebec pork is often under $3.50/lb)
        {
            "protein": "Pork Tenderloin",
            "unit": "kg",
            "qty": 0.6,
            "allergens": [],
            "variations": [
                ("Roasted Pork Tenderloin with Caramelized Apples", "Québécoise", "Dinner", 35, "medium", 4,
                 [("Quebec McIntosh Apples", 3, "each"), ("Butter", 25, "g"), ("Brown Sugar", 15, "g"), ("Rosemary (Fresh)", 5, "g"), ("Olive Oil", 15, "ml")],
                 430, 38, 26, 16, 4,
                 ["Sear seasoned pork tenderloin in an oven-safe skillet on all sides.", "Toss sliced apples in butter, brown sugar, and rosemary around the meat.", "Roast in oven at 375°F for 18-20 minutes until internal temp reaches 145°F.", "Rest 5 minutes before slicing."],
                 ["quebec-apples", "autumn-comfort", "lean-protein"]),
                ("Garlic Herb Crusted Pork Chops with Mashed Potatoes", "Canadian Comfort", "Dinner", 30, "easy", 4,
                 [("Potatoes", 800, "g"), ("Garlic", 4, "cloves"), ("Thyme", 5, "g"), ("Butter", 30, "g"), ("Milk", 60, "ml")],
                 490, 41, 42, 17, 5,
                 ["Boil and mash potatoes with butter, milk, and salt.", "Season pork chops generously with garlic, thyme, salt, and pepper.", "Pan-sear pork chops in hot skillet for 4-5 minutes per side.", "Serve chops over mashed potatoes with pan drippings."],
                 ["comfort-dinner", "budget-meat", "classic"]),
                ("Sweet & Tangy BBQ Pulled Pork (Slow Cooker)", "American", "Dinner", 20, "easy", 6,
                 [("BBQ Sauce", 250, "ml"), ("Apple Cider Vinegar", 30, "ml"), ("Yellow Onions", 1, "each"), ("Brioche Buns", 6, "each")],
                 480, 36, 52, 14, 3,
                 ["Place sliced onions and pork shoulder/tenderloin in slow cooker.", "Pour BBQ sauce and apple cider vinegar over meat.", "Cook on low for 7 hours until tender.", "Shred with two forks and serve on buns with coleslaw."],
                 ["slow-cooker", "batch-cooking", "leftovers-chaining"]),
            ]
        },
        # 4. Fish & Seafood (Salmon / Trout / Cod flyer specials)
        {
            "protein": "Atlantic Salmon Fillet",
            "unit": "kg",
            "qty": 0.5,
            "allergens": ["fish"],
            "variations": [
                ("Maple Glazed Atlantic Salmon with Green Beans", "Québécoise", "Dinner", 20, "easy", 4,
                 [("Pure Maple Syrup", 30, "ml"), ("Soy Sauce", 20, "ml"), ("Green Beans", 350, "g"), ("Garlic", 2, "cloves"), ("White Rice", 250, "g")],
                 470, 36, 44, 15, 4,
                 ["Whisk maple syrup, soy sauce, and minced garlic.", "Place salmon fillets on a lined baking tray and brush with glaze.", "Surround with fresh green beans tossed in olive oil.", "Bake at 400°F for 14-16 minutes until salmon flakes easily."],
                 ["omega-3", "healthy-dinner", "quebec-staple"]),
                ("Lemon Herb Baked Cod with Roasted Potatoes", "Mediterranean", "Dinner", 25, "easy", 4,
                 [("Baby Potatoes (Halved)", 600, "g"), ("Lemon (Juice & Zest)", 1, "each"), ("Olive Oil", 30, "ml"), ("Dill (Fresh)", 10, "g")],
                 390, 33, 38, 11, 4,
                 ["Toss baby potatoes in olive oil and roast at 400°F for 15 minutes.", "Add seasoned cod fillets topped with lemon slices and fresh dill.", "Bake together for another 12 minutes."],
                 ["low-fat", "light-meal", "gluten-free"]),
            ]
        },
        # 5. Adonis Specials & Halloumi / Vegetarian Favorites
        {
            "protein": "Halloumi Cheese",
            "unit": "g",
            "qty": 250,
            "allergens": ["dairy"],
            "variations": [
                ("Adonis Crispy Halloumi & Roasted Vegetable Salad", "Middle Eastern", "Lunch", 20, "easy", 3,
                 [("Zucchini (Sliced)", 200, "g"), ("Bell Peppers", 1, "each"), ("Cucumber (Diced)", 1, "each"), ("Cherry Tomatoes", 150, "g"), ("Pita Bread", 2, "each"), ("Olive Oil", 25, "ml")],
                 440, 22, 34, 25, 6,
                 ["Slice halloumi into 1/2-inch thick slabs.", "Grill or pan-fry in a dry skillet over medium-high heat until golden brown on both sides.", "Toss roasted vegetables and fresh cucumber/tomatoes with olive oil and oregano.", "Serve halloumi warm on top with toasted pita."],
                 ["vegetarian", "adonis-special", "mediterranean"]),
                ("Traditional Shakshuka with Poached Eggs & Feta", "Middle Eastern", "Breakfast", 25, "easy", 4,
                 [("Eggs", 4, "each"), ("Crushed Tomatoes", 1, "can"), ("Bell Peppers", 2, "each"), ("Onions", 1, "each"), ("Feta Cheese", 75, "g"), ("Cumin", 5, "g")],
                 310, 18, 22, 16, 5,
                 ["Sauté onions and bell peppers in olive oil until softened.", "Add crushed tomatoes, cumin, and garlic; simmer 10 minutes.", "Create small wells in sauce and crack eggs into them.", "Cover and simmer until whites are set; scatter crumbled feta over top."],
                 ["vegetarian", "brunch", "high-protein", "one-pan"]),
                ("Adonis Chicken Shawarma Rice Bowl", "Middle Eastern", "Dinner", 30, "easy", 4,
                 [("Chicken Thighs", 500, "g"), ("Basmati Rice", 250, "g"), ("Garlic Sauce (Toum)", 50, "g"), ("Cucumbers", 1, "each"), ("Pickled Turnips", 60, "g")],
                 510, 39, 48, 18, 4,
                 ["Marinate chicken in shawarma spice blend, lemon, and olive oil.", "Sear in cast iron pan until caramelized and cooked through.", "Serve sliced chicken over fragrant spiced basmati rice.", "Garnish with cucumbers, pickled turnips, and garlic sauce."],
                 ["middle-eastern", "street-food", "adonis-inspired"]),
            ]
        },
        # 6. Quebec Soups, Comfort Stews & Bean Classics
        {
            "protein": "Ham Bone & Diced Ham",
            "unit": "g",
            "qty": 300,
            "allergens": [],
            "variations": [
                ("Traditional Quebec Yellow Pea Soup", "Québécoise", "Dinner", 60, "easy", 6,
                 [("Yellow Split Peas", 400, "g"), ("Carrots (Diced)", 2, "each"), ("Celery (Diced)", 2, "stalks"), ("Yellow Onions", 1, "each"), ("Savory (Sarriette)", 5, "g")],
                 390, 26, 55, 6, 14,
                 ["Rinse yellow split peas thoroughly.", "Combine peas, diced ham, carrots, celery, onion, and savory in a soup pot with 2 liters water.", "Bring to boil, then simmer gently for 1.5 to 2 hours until peas are completely tender.", "Season to taste."],
                 ["quebec-heritage", "winter-comfort", "high-fiber", "budget-saver"]),
                ("Slow Cooker Quebec Maple Baked Beans (Fèves au Lard)", "Québécoise", "Breakfast", 30, "easy", 8,
                 [("White Navy Beans", 500, "g"), ("Pure Maple Syrup", 120, "ml"), ("Salt Pork or Bacon", 150, "g"), ("Dry Mustard", 10, "g"), ("Molasses", 30, "ml")],
                 380, 18, 62, 7, 12,
                 ["Soak navy beans overnight.", "Drain beans and place in slow cooker with diced salt pork or thick bacon.", "Stir in maple syrup, molasses, dry mustard, salt, and pepper with hot water to cover.", "Cook on low for 8-10 hours until rich and dark."],
                 ["quebec-cabane-sucre", "high-fiber", "batch-cooking", "freezer-friendly"]),
            ]
        }
    ]

    # Additional modular variations to scale cleanly to 500+ curated recipes
    staple_grains = ["Brown Rice", "White Rice", "Quinoa", "Egg Noodles", "Penne", "Rigatoni", "Couscous", "Mashed Potatoes", "Roasted Sweet Potatoes"]
    staple_veg_combos = [
        ("Broccoli & Carrots", [("Broccoli", 300, "g"), ("Carrots", 200, "g")]),
        ("Zucchini & Bell Peppers", [("Zucchini", 250, "g"), ("Bell Peppers", 200, "g")]),
        ("Green Beans & Mushrooms", [("Green Beans", 250, "g"), ("Mushrooms", 150, "g")]),
        ("Roasted Root Medley", [("Carrots", 200, "g"), ("Parsnips", 150, "g"), ("Potatoes", 300, "g")]),
        ("Spinach & Cherry Tomatoes", [("Fresh Spinach", 150, "g"), ("Cherry Tomatoes", 150, "g")]),
        ("Cabbage & Onions", [("Cabbage", 350, "g"), ("Yellow Onions", 150, "g")]),
        ("Asparagus & Lemon", [("Asparagus", 250, "g"), ("Lemon", 1, "each")]),
    ]

    cuisines_styles = [
        ("Québécoise Comfort", "Québécoise", "Maple syrup, savory herbs, butter, and root vegetables"),
        ("Mediterranean Herb", "Mediterranean", "Olive oil, garlic, lemon, oregano, and feta"),
        ("Classic French Bistro", "French", "Dijon mustard, butter, thyme, shallots, and white wine sauce"),
        ("Italian Trattoria", "Italian", "San Marzano tomatoes, garlic, basil, and parmesan"),
        ("Mexican Skillet", "Mexican", "Cumin, chili, lime, black beans, and salsa"),
        ("Asian Ginger Soy", "Asian", "Soy sauce, fresh ginger, garlic, sesame oil, and scallions"),
        ("Montreal Deli Style", "Québécoise", "Montreal steak spice, pickles, mustard, and rye"),
    ]

    proteins_pool = [
        ("Pork Tenderloin", "pork", 45, 12, 380),
        ("Chicken Thighs (Skinless)", "poultry", 38, 14, 410),
        ("Lean Ground Beef", "beef", 35, 16, 430),
        ("Pork Chops (Center Cut)", "pork", 40, 11, 370),
        ("Chicken Breast Strips", "poultry", 44, 8, 360),
        ("Atlantic Salmon Portions", "seafood", 36, 18, 450),
        ("White Fish / Cod", "seafood", 32, 5, 290),
        ("Tofu Extra Firm", "vegetarian", 25, 10, 320),
        ("Canned Chickpeas & Lentils", "vegetarian", 22, 6, 350),
        ("Turkey Cutlets", "poultry", 42, 7, 340),
        ("Quebec Sausage (Mild Italian)", "pork", 28, 22, 480),
    ]

    # First add predefined template recipes
    for cat in categories:
        for var in cat["variations"]:
            name, cuisine, m_type, p_time, diff, serv, ings_raw, cals, prot, carb, fat, fib, insts, tags = var
            if name.lower() not in existing_names:
                r_id = f"recipe_{idx:03d}"
                ings = [{"item": cat["protein"], "quantity": cat["qty"], "unit": cat["unit"]}]
                for in_name, in_q, in_u in ings_raw:
                    ings.append({"item": in_name, "quantity": in_q, "unit": in_u})

                recipe = create_recipe(
                    recipe_id=r_id,
                    name=name,
                    cuisine=cuisine,
                    meal_type=m_type,
                    prep_time=p_time,
                    difficulty=diff,
                    servings=serv,
                    ingredients=ings,
                    calories=cals,
                    protein=prot,
                    carbs=carb,
                    fat=fat,
                    fiber=fib,
                    instructions=insts,
                    tags=tags,
                    allergens=cat["allergens"]
                )
                all_recipes.append(recipe)
                existing_names.add(name.lower())
                idx += 1

    # Systematically generate diverse Quebec staple meals until reaching 510+ recipes
    random.seed(42)  # Deterministic generation
    cooking_methods = ["Baked", "Sheet Pan", "Pan-Seared", "Skillet", "Slow Cooker", "Grilled", "Braised", "Crispy"]

    while len(all_recipes) < 515:
        prot_name, prot_cat, base_prot, base_fat, base_cal = random.choice(proteins_pool)
        style_name, cuisine, flavor_note = random.choice(cuisines_styles)
        method = random.choice(cooking_methods)
        veg_label, veg_items = random.choice(staple_veg_combos)
        grain = random.choice(staple_grains)

        recipe_name = f"{method} {prot_name} with {veg_label} ({cuisine})"
        if recipe_name.lower() in existing_names:
            recipe_name = f"{cuisine} Style {method} {prot_name} and {grain}"
            if recipe_name.lower() in existing_names:
                recipe_name = f"{method} {prot_name} with {veg_label} & {grain}"

        if recipe_name.lower() in existing_names:
            continue

        existing_names.add(recipe_name.lower())
        r_id = f"recipe_{idx:03d}"

        servings = random.choice([4, 4, 4, 6])
        prep_time = random.choice([20, 25, 30, 35, 40])
        difficulty = "easy" if prep_time <= 30 else "medium"

        # Construct ingredient list
        qty_factor = servings / 4.0
        ings = [
            {"item": prot_name, "quantity": round(0.5 * qty_factor, 2), "unit": "kg"},
            {"item": grain, "quantity": round(250 * qty_factor, 1), "unit": "g"}
        ]
        for v_name, v_qty, v_unit in veg_items:
            ings.append({"item": v_name, "quantity": round(v_qty * qty_factor, 1), "unit": v_unit})

        ings.append({"item": "Olive Oil or Butter", "quantity": round(25 * qty_factor, 1), "unit": "ml"})
        ings.append({"item": "Garlic & Seasonings", "quantity": 1, "unit": "unit"})

        carb = random.randint(35, 55)
        fib = random.randint(4, 9)
        prot = int(base_prot * 1.05)
        fat = int(base_fat * 1.1)
        cal = int(prot * 4 + carb * 4 + fat * 9)

        insts = [
            f"Preheat oven or skillet as required for {method.lower()} method.",
            f"Season {prot_name} generously with salt, pepper, and {flavor_note.split(',')[0]}.",
            f"Cook {grain} according to package instructions.",
            f"Toss vegetables with oil and seasonings.",
            f"Cook {prot_name} alongside {veg_label} until meat reaches safe internal temperature.",
            f"Serve warm over {grain} and drizzle with pan drippings."
        ]

        tags = [cuisine.lower().replace(" ", "-"), prot_cat, "budget-friendly", "quebec-staple"]
        if servings >= 6:
            tags.append("batch-cooking")
            tags.append("leftovers-friendly")

        dietary = []
        if prot_cat == "vegetarian":
            dietary.append("Vegetarian")
        if prot_cat in ("poultry", "seafood", "beef") and grain in ("Mashed Potatoes", "Roasted Sweet Potatoes", "Brown Rice", "Quinoa"):
            dietary.append("Gluten-Free")

        allergens = []
        if "Noodles" in grain or "Penne" in grain or "Rigatoni" in grain:
            allergens.append("gluten")
        if prot_cat == "seafood":
            allergens.append("fish")
        if "Butter" in str(ings):
            allergens.append("dairy")

        recipe = create_recipe(
            recipe_id=r_id,
            name=recipe_name,
            cuisine=cuisine,
            meal_type="Dinner" if prep_time >= 25 else "Lunch",
            prep_time=prep_time,
            difficulty=difficulty,
            servings=servings,
            ingredients=ings,
            calories=cal,
            protein=prot,
            carbs=carb,
            fat=fat,
            fiber=fib,
            instructions=insts,
            tags=tags,
            dietary_tags=dietary,
            allergens=allergens
        )
        all_recipes.append(recipe)
        idx += 1

    return all_recipes


if __name__ == "__main__":
    dataset = generate_curated_dataset()
    dest_path = os.path.join(os.path.dirname(__file__), "recipes.json")
    with open(dest_path, "w", encoding="utf-8") as f:
        json.dump(dataset, f, ensure_ascii=False, indent=2)
    print(f"Successfully generated and curated {len(dataset)} recipes in {dest_path}")
