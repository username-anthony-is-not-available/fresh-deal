# Smart Meal Planner & Deal Aggregator

AI-powered meal planning that saves you money by finding the best grocery deals.

## Features
- 7-day meal plans with breakfast, lunch, dinner
- Nutritional balance tracking
- Multi-store deal aggregation
- Smart shopping lists with cost optimization
- Quebec-focused (Walmart, Provigo, IGA, Metro, Maxi)

## Tech Stack
- Backend: Python FastAPI + SQLAlchemy
- Frontend: React + TailwindCSS + Vite
- AI: OpenRouter (Claude 3.5 Sonnet)
- Database: PostgreSQL (with SQLite fallback)

## Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+
- Docker & Docker Compose (for PostgreSQL)

### Option 1: Full Stack with Docker
```bash
# Start all services
docker-compose up -d

# Install backend dependencies
cd backend
pip install -r requirements.txt

# Run migrations
alembic upgrade head

# Start backend
uvicorn app.main:app --reload

# Install frontend dependencies
cd ../frontend
npm install

# Start frontend
npm run dev
```

### Option 2: SQLite (Local Development)
```bash
# Backend
cd backend
pip install -r requirements.txt
USE_SQLITE_LOCAL=True uvicorn app.main:app --reload

# Frontend
cd frontend
npm install
npm run dev
```

## Environment Variables

Create `backend/.env`:
```
OPENROUTER_API_KEY=your_key_here
DATABASE_URL=postgresql://user:password@localhost:5432/mealplanner
USE_SQLITE_LOCAL=False  # Set to True for SQLite
PROXY_POOL=http://user:pass@proxy1.example.com:8080,http://user:pass@proxy2.example.com:8080
```

## API Endpoints

The examples below use the backend origin `http://localhost:8000`. Replace it with your deployed backend URL as needed. The route paths include the prefixes mounted by the FastAPI app (`/api` and `/auth`). Most responses are JSON; download and upload routes call out their content types. Start the backend before trying the examples.

```bash
API=http://localhost:8000
AUTH='Authorization: Bearer YOUR_ACCESS_TOKEN'
```

Use `POST /auth/register` to create an account and `POST /auth/login/access-token` to obtain a bearer token. Login uses form fields (`username` is the account email), not a JSON body. Endpoints marked **Bearer required** need `-H "$AUTH"`; **Public** means that the handler does not declare bearer authentication. Authentication notes describe the current route dependencies, not a deployment security recommendation. `POST /api/onboard` is an alternate onboarding route; prefer `/auth/register` for new clients.

FastAPI's interactive reference is at `/docs` (ReDoc at `/redoc`). The OpenAPI JSON URL defaults to `/api/v1/openapi.json`; this is separate from the `/api` route prefix used by the application endpoints. The health check is `GET /health`, and the Prometheus metrics endpoint is `GET /metrics`.

### Authentication and accounts

- **POST `/auth/register`** — Create an account. JSON body: `email`, `password`, `postal_code`, `household_size`, `dietary_preferences`, and optional `allergies`. Public; returns the created user.
  ```bash
  curl -X POST "$API/auth/register" -H 'Content-Type: application/json' -d '{"email":"you@example.com","password":"YOUR_PASSWORD","postal_code":"H4T1V6","household_size":2,"dietary_preferences":["vegetarian"],"allergies":[]}'
  ```
- **POST `/auth/login/access-token`** — Exchange the account email and password for an access token; successful response includes `access_token` and `token_type: "bearer"`. Send form-encoded `username` and `password`. Public; limited to 10 requests per minute.
  ```bash
  curl -X POST "$API/auth/login/access-token" -H 'Content-Type: application/x-www-form-urlencoded' --data-urlencode 'username=you@example.com' --data-urlencode 'password=YOUR_PASSWORD'
  ```
- **POST `/api/onboard`** — Create a user from `email`, `password`, `postal_code`, `household_size`, `dietary_preferences`, and optional `allergies`; returns the created user object. Public. Prefer `/auth/register` for new signups.
  ```bash
  curl -X POST "$API/api/onboard" -H 'Content-Type: application/json' -d '{"email":"you@example.com","password":"YOUR_PASSWORD","postal_code":"H4T1V6","household_size":2,"dietary_preferences":["vegetarian"],"allergies":[]}'
  ```
- **GET `/api/users/{user_id}`** — Read a user's profile (`user_id` is the path parameter); returns `UserRead`, or 404 if the user is not found. Public.
  ```bash
  curl "$API/api/users/1"
  ```
- **PATCH `/api/users/{user_id}`** — Update any supplied profile fields: `postal_code`, `household_size`, `dietary_preferences`, `allergies`, or `preferred_loyalty_programs`; returns `UserRead`, or 404 if not found. Public.
  ```bash
  curl -X PATCH "$API/api/users/1" -H 'Content-Type: application/json' -d '{"household_size":3,"dietary_preferences":["vegetarian"],"postal_code":"H4T1V6"}'
  ```
- **GET `/api/users/{user_id}/nutrition-summary`** — Return the meal-plan nutrition summary for a user (`totals` and `daily_averages`); 404 if no summary is available. Public.
  ```bash
  curl "$API/api/users/1/nutrition-summary"
  ```
- **GET `/api/users/me/favorites`** — List the authenticated user's favorite recipes. Bearer required.
  ```bash
  curl "$API/api/users/me/favorites" -H "$AUTH"
  ```

### Recipes and ratings

- **GET `/api/recipes`** — List recipes, with optional `search` (recipe or ingredient text), `cuisine`, and maximum `prep_time` in minutes; returns recipe objects including `average_rating`. Public.
  ```bash
  curl -G "$API/api/recipes" --data-urlencode 'search=tomato' --data-urlencode 'cuisine=Italian' --data-urlencode 'prep_time=30'
  ```
- **GET `/api/recipes/{recipe_id}`** — Get a recipe with scaled ingredients, substitutions, and average rating. Optional query `servings` overrides the target servings; otherwise the handler uses the signed-in user's household size or the recipe default. **Bearer required** by the current OAuth2 dependency, despite the handler's optional-user helper; returns 404 if the recipe is missing.
  ```bash
  curl "$API/api/recipes/1?servings=2" -H "$AUTH"
  ```
- **GET `/api/recipes/top-rated`** — List recipes ordered by average rating, highest first. Optional `limit` (default `10`). Public.
  ```bash
  curl "$API/api/recipes/top-rated?limit=5"
  ```
- **POST `/api/recipes/{recipe_id}/rate`** — Create or replace the signed-in user's rating for a recipe. JSON body: `{"rating":5}`; returns a success message. Bearer required.
  ```bash
  curl -X POST "$API/api/recipes/1/rate" -H "$AUTH" -H 'Content-Type: application/json' -d '{"rating":5}'
  ```
- **POST `/api/recipes/{recipe_id}/feedback`** — Record whether the signed-in user made a recipe and optional notes. JSON body: `{"status":"made_it","notes":"Cooking time was long."}`; returns a success message. Bearer required.
  ```bash
  curl -X POST "$API/api/recipes/1/feedback" -H "$AUTH" -H 'Content-Type: application/json' -d '{"status":"made_it","notes":"Cooking time was long."}'
  ```
- **GET `/api/recipes/{recipe_id}/average-rating`** — Return `{"average_rating": number}` (zero when no ratings exist). Public.
  ```bash
  curl "$API/api/recipes/1/average-rating"
  ```
- **GET `/api/recipes/{recipe_id}/my-rating`** — Return the signed-in user's rating as `{"rating": number}` or `{"rating": null}`. Bearer required.
  ```bash
  curl "$API/api/recipes/1/my-rating" -H "$AUTH"
  ```
- **POST `/api/recipes/{recipe_id}/favorite`** — Add a recipe to the signed-in user's favorites; returns a success message. Bearer required.
  ```bash
  curl -X POST "$API/api/recipes/1/favorite" -H "$AUTH"
  ```
- **DELETE `/api/recipes/{recipe_id}/favorite`** — Remove a recipe from the signed-in user's favorites; returns a success message or 404 if no favorite exists. Bearer required.
  ```bash
  curl -X DELETE "$API/api/recipes/1/favorite" -H "$AUTH"
  ```

### Meal plans, tasks, and shopping

- **POST `/api/plans/generate`** — Queue meal-plan generation for `user_id`; optional query `model` selects the model. Returns a `task_id` and `Processing` status. Public.
  ```bash
  curl -X POST "$API/api/plans/generate?user_id=1"
  ```
- **POST `/api/plans/regenerate-meal`** — Generate one replacement meal. JSON body requires `user_id`, `day`, `type`, `dietary_preferences`, and `existing_meals`; optional `model_type`. Returns the generated meal object. Public.
  ```bash
  curl -X POST "$API/api/plans/regenerate-meal" -H 'Content-Type: application/json' -d '{"user_id":1,"day":"Monday","type":"dinner","dietary_preferences":["vegetarian"],"existing_meals":[{"name":"Pasta"}],"model_type":"YOUR_MODEL"}'
  ```
- **GET `/api/tasks/{task_id}`** — Poll a background task. The response contains its `task_id` and status; completed results include `result`, while failures include `error`. Public.
  ```bash
  curl "$API/api/tasks/YOUR_TASK_ID"
  ```
- **POST `/api/tasks/{task_id}/stop`** — Request revocation of a background task; returns a stopped status and message. Public.
  ```bash
  curl -X POST "$API/api/tasks/YOUR_TASK_ID/stop"
  ```
- **GET `/api/plans/{user_id}/latest`** — Return the user's latest non-empty meal plan JSON, with its plan `id` added; 404 if no plan is available. Public.
  ```bash
  curl "$API/api/plans/1/latest"
  ```
- **GET `/api/shopping/optimize`** — Build an optimized shopping list from the user's latest plan. Required query `user_id`; optional `strategy` (default `min_cost`) and repeatable `preferred_stores`. Returns the optimizer's shopping-list result. Public.
  ```bash
  curl "$API/api/shopping/optimize?user_id=1&strategy=min_cost&preferred_stores=metro&preferred_stores=iga"
  ```

### Deals and scraping

- **GET `/api/deals`** — List deal, product, and store details. Optional `sort_by` is `category`, `effective_discount`, `discount_pct`, or `distance`; `postal_code` adds a 5 km proximity filter when distance can be calculated. Public.
  ```bash
  curl "$API/api/deals?sort_by=discount_pct&postal_code=H4T1V6"
  ```
- **POST `/api/data/seed`** — Seed the database with mock deal data; returns a message with the inserted count. Public; intended as a development tool.
  ```bash
  curl -X POST "$API/api/data/seed"
  ```
- **POST `/api/admin/scrape`** — Queue scraping for the requested stores. JSON body: `stores` (required), optional `postal_code` (default `H4T1V6`) and `limit_per_store` (default `50`). Returns a task ID, status, stores, and postal code. Bearer required.
  ```bash
  curl -X POST "$API/api/admin/scrape" -H "$AUTH" -H 'Content-Type: application/json' -d '{"stores":["metro","walmart"],"postal_code":"H4T1V6","limit_per_store":50}'
  ```
- **POST `/api/admin/scrape/flipp`** — Queue the same scrape request through the dedicated Flipp endpoint. Accepts the same JSON body and returns the scrape task details. Bearer required.
  ```bash
  curl -X POST "$API/api/admin/scrape/flipp" -H "$AUTH" -H 'Content-Type: application/json' -d '{"stores":["metro"],"postal_code":"H4T1V6","limit_per_store":50}'
  ```
- **POST `/api/admin/scrape/{store_name}`** — Queue scraping for one store. Path `store_name`; optional query `postal_code` (default `H4T1V6`) and `limit` (default `50`). Bearer required.
  ```bash
  curl -X POST "$API/api/admin/scrape/metro?postal_code=H4T1V6&limit=50" -H "$AUTH"
  ```
- **GET `/api/admin/scrapers`** — List available scraper configuration and supported stores. Bearer required.
  ```bash
  curl "$API/api/admin/scrapers" -H "$AUTH"
  ```
- **GET `/api/admin/status/scrapers`** — Return store IDs, names, chains, last-scraped timestamps, and stale flags. Bearer required.
  ```bash
  curl "$API/api/admin/status/scrapers" -H "$AUTH"
  ```
- **GET `/api/admin/scrapers/health`** — Return scraper health metrics. Optional query `days` (default `7`). Bearer required.
  ```bash
  curl "$API/api/admin/scrapers/health?days=14" -H "$AUTH"
  ```
- **GET `/api/admin/scrapers/health/summary`** — Return a high-level health summary for the scraping system. Bearer required.
  ```bash
  curl "$API/api/admin/scrapers/health/summary" -H "$AUTH"
  ```
- **GET `/api/admin/scrapers/logs`** — List recent scraper logs; optional query filters `store_name`, `status`, `limit` (default `50`), and `offset` (default `0`). Returns log records. Bearer required.
  ```bash
  curl "$API/api/admin/scrapers/logs?store_name=metro&status=success&limit=20&offset=0" -H "$AUTH"
  ```
- **GET `/api/admin/scrapers/logs/{log_id}/screenshot`** — Download a log screenshot as PNG; `log_id` is the path parameter. Returns 404/403 when the file is absent or outside the permitted scraper directory. Bearer required.
  ```bash
  curl "$API/api/admin/scrapers/logs/42/screenshot" -H "$AUTH" -o screenshot.png
  ```
- **GET `/api/admin/scrapers/logs/{log_id}/html`** — Download the saved HTML snapshot for a log as HTML; `log_id` is the path parameter. Returns 404/403 when the file is absent or outside the permitted scraper directory. Bearer required.
  ```bash
  curl "$API/api/admin/scrapers/logs/42/html" -H "$AUTH" -o snapshot.html
  ```
- **POST `/api/admin/scrapers/{store_name}/reset`** — Reset the selected store's scraper circuit breaker. Bearer required.
  ```bash
  curl -X POST "$API/api/admin/scrapers/metro/reset" -H "$AUTH"
  ```
- **POST `/api/innovative-meal-suggestions`** — Generate innovative meal suggestions for the authenticated user. Required query `user_id` must match the token's user; optional `num_suggestions` defaults to `3`. Returns an `InnovativeMealPlan`; 403 if the IDs do not match. Bearer required.
  ```bash
  curl -X POST "$API/api/innovative-meal-suggestions?user_id=1&num_suggestions=3" -H "$AUTH"
  ```

### Deal exports and quality

- **GET `/api/deals/export`** — Export deals as JSON (default), CSV, Markdown, or plain text. Optional query parameters: `format`, `store`, `category`, `min_discount`, and `limit`. CSV, Markdown, and text responses are downloadable files; JSON returns an array. Public.
  ```bash
  curl -G "$API/api/deals/export" --data-urlencode 'format=csv' --data-urlencode 'store=Metro' --data-urlencode 'category=Dairy' --data-urlencode 'min_discount=20' --data-urlencode 'limit=10'
  ```
- **GET `/api/deals/best`** — Return the highest-scoring deals; scoring considers discount and loyalty value. Optional `limit` (default `20`), `store`, and `category`; the endpoint applies a 5% minimum discount. Public.
  ```bash
  curl -G "$API/api/deals/best" --data-urlencode 'limit=5' --data-urlencode 'store=IGA' --data-urlencode 'category=Meat'
  ```
- **GET `/api/deals/summary`** — Return deal counts and savings/discount summaries grouped by store and category, including top categories. Public.
  ```bash
  curl "$API/api/deals/summary"
  ```
- **GET `/api/deals/quality`** — Filter and score deals by quality. Optional `min_quality` (`excellent`, `good`, `average`, `poor`, or `noise`; default `average`), `store`, `category`, and `limit` (default `50`). Response includes filter counts and scored deals. Public.
  ```bash
  curl -G "$API/api/deals/quality" --data-urlencode 'min_quality=good' --data-urlencode 'store=Metro' --data-urlencode 'category=Produce' --data-urlencode 'limit=25'
  ```
- **GET `/api/deals/quality/summary`** — Return quality distribution, recommendations, and a generation timestamp for current deals. Public.
  ```bash
  curl "$API/api/deals/quality/summary"
  ```

### Pantry and feedback

- **GET `/api/pantry/{user_id}`** — List pantry items for a user; returns a list of pantry item objects. Public.
  ```bash
  curl "$API/api/pantry/1"
  ```
- **POST `/api/pantry/{user_id}/add`** — Add or update pantry items. JSON body: `{"items":[{"name":"tomatoes","quantity":4,"unit":"each"}]}`; returns the updated pantry list. Public.
  ```bash
  curl -X POST "$API/api/pantry/1/add" -H 'Content-Type: application/json' -d '{"items":[{"name":"tomatoes","quantity":4,"unit":"each"},{"name":"rice","quantity":1,"unit":"kg"}]}'
  ```
- **DELETE `/api/pantry/{user_id}/{item_id}`** — Delete one pantry item; returns a message or 404 if the item does not belong to that user. Public.
  ```bash
  curl -X DELETE "$API/api/pantry/1/7"
  ```
- **POST `/api/pantry/{user_id}/consume-latest-plan`** — Consume pantry ingredients used by the user's latest meal plan; response is the pantry service's result. Public.
  ```bash
  curl -X POST "$API/api/pantry/1/consume-latest-plan"
  ```
- **POST `/api/feedback`** — Create feedback for the authenticated user. JSON body may include `recipe_id` or `meal_plan_id`, and requires `rating`; `comment` is optional. Returns a feedback record. Bearer required.
  ```bash
  curl -X POST "$API/api/feedback" -H "$AUTH" -H 'Content-Type: application/json' -d '{"recipe_id":1,"rating":5,"comment":"Delicious and easy."}'
  ```
- **GET `/api/feedback`** — List the authenticated user's feedback, newest first; optional filters `recipe_id` and `meal_plan_id`. Bearer required.
  ```bash
  curl "$API/api/feedback?recipe_id=1" -H "$AUTH"
  ```
- **GET `/api/feedback/summary`** — Return the authenticated user's average recipe rating, average meal-plan rating, and feedback count. Bearer required.
  ```bash
  curl "$API/api/feedback/summary" -H "$AUTH"
  ```

### Nutrition

- **POST `/api/users/me/nutrition-goal`** — Create or update the authenticated user's daily nutrition goals. JSON fields: optional `goal_type` (default `maintenance`), `target_calories`, `target_protein`, `target_carbs`, `target_fats`, and `target_fiber`. Bearer required.
  ```bash
  curl -X POST "$API/api/users/me/nutrition-goal" -H "$AUTH" -H 'Content-Type: application/json' -d '{"goal_type":"weight_loss","target_calories":2000,"target_protein":150,"target_carbs":200,"target_fats":60,"target_fiber":30}'
  ```
- **GET `/api/users/me/nutrition-goal`** — Retrieve the authenticated user's current nutrition goal; 404 if none exists. Bearer required.
  ```bash
  curl "$API/api/users/me/nutrition-goal" -H "$AUTH"
  ```
- **GET `/api/users/me/nutrition-summary`** — Return daily nutrition records over required inclusive ISO-date query parameters `start_date` and `end_date`. Bearer required.
  ```bash
  curl "$API/api/users/me/nutrition-summary?start_date=2026-10-01&end_date=2026-10-31" -H "$AUTH"
  ```

### Plan exports and flyers

- **GET `/api/plans/{user_id}/export/ical`** — Download the authenticated user's latest meal plan as an iCalendar `.ics` file. The path `user_id` must match the token owner; returns 403 for another user and 404 if no plan is available. Bearer required.
  ```bash
  curl -L "$API/api/plans/1/export/ical" -H "$AUTH" -o meal_plan_1.ics
  ```
- **GET `/api/plans/{user_id}/export/pdf`** — Download the authenticated user's latest meal plan as a PDF. The path `user_id` must match the token owner; returns 403 for another user and 404 if no plan is available. Bearer required.
  ```bash
  curl -L "$API/api/plans/1/export/pdf" -H "$AUTH" -o meal_plan_1.pdf
  ```
- **GET `/api/flyer/formats`** — List supported flyer formats, the single-upload size limit, tips, and example stores. Public.
  ```bash
  curl "$API/api/flyer/formats"
  ```
- **POST `/api/flyer/upload`** — Upload one JPG, JPEG, PNG, GIF, WebP, or PDF flyer (maximum 20 MB; PDF processing uses the first page) and return extracted deal fields. Multipart fields: required `file`, optional `store` hint. Public; requires the configured vision API for extraction.
  ```bash
  curl -X POST "$API/api/flyer/upload" -F 'file=@weekly-flyer.png;type=image/png' -F 'store=Metro'
  ```
- **POST `/api/flyer/upload/batch`** — Upload multiple flyer pages using repeated `files` parts and an optional `store` hint; deals are combined and deduplicated by product name and price. Use image files; this route does not perform the single-upload endpoint's PDF conversion. Public.
  ```bash
  curl -X POST "$API/api/flyer/upload/batch" -F 'files=@page-1.jpg;type=image/jpeg' -F 'files=@page-2.jpg;type=image/jpeg' -F 'store=IGA'
  ```

### Operational routes

- **GET `/health`** — Return `{"status":"ok"}` when the application is running. Public.
  ```bash
  curl "$API/health"
  ```
- **GET `/metrics`** — Expose Prometheus metrics via the FastAPI instrumentator. Public unless protected by deployment configuration.
  ```bash
  curl "$API/metrics"
  ```

All endpoint examples are based on the currently mounted handlers. For dynamically generated response schemas, use the running app's OpenAPI reference at `/docs` or `/api/v1/openapi.json`.

## Project Status
✅ Phase 1 MVP Complete (Walking Skeleton)
- Mock deal aggregation (100+ products)
- 7-day meal planning with AI
- Nutritional balancing
- Shopping list optimization
- Full-stack UI

🚧 Coming Next (Phase 2)
- Real Playwright scrapers
- Recipe ratings & feedback
- Advanced nutrition tracking
- Mobile app

## Architecture
[Diagram showing Frontend -> API -> Agents -> Database]

## Testing
```bash
cd backend
pytest tests/
```

## License
MIT
