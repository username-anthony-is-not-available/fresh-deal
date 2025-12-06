# Codebase Analysis: Smart Meal Planner

## 1. Project Overview

*   **Project Type:** MVP / Proof of Concept (POC) for an AI-powered meal planner and grocery deal aggregator.
*   **Domain:** FoodTech / Personal Finance (Grocery savings). Targets the Quebec market (specific retailers: Walmart, Provigo, IGA, Metro, Maxi).
*   **Purpose:** To generate 7-day meal plans based on active grocery deals to minimize costs for users.
*   **Tech Stack:**
    *   **Backend:** Python 3.12, FastAPI, SQLModel (SQLAlchemy), Alembic, Pydantic, OpenAI (OpenRouter).
    *   **Frontend:** React 18, Vite, TailwindCSS, Lucide React, Recharts.
    *   **Infrastructure:** Docker Compose (PostgreSQL, Redis).
*   **Scale:** Small to Medium. "Walking Skeleton" stage.
    *   Backend: ~10 key files, clear separation of concerns.
    *   Frontend: ~15 components/pages.

## 2. Architecture & Structure

*   **Pattern:** Layered Architecture (Monolithic).
    *   **Frontend:** Single Page Application (SPA).
    *   **Backend:** REST API (FastAPI) -> Services/Agents -> Data Access (SQLModel).
*   **Directory Structure:**
    *   `smart-meal-planner/` is the true root.
    *   `backend/` (top-level) is a legacy artifact containing only configuration examples (Safe to delete).
    *   Organization is logical: `app/models`, `app/api`, `app/services`, `app/agents`.
*   **Data Flow:**
    1.  User requests plan -> API.
    2.  `MealPlannerAgent` (LLM) generates JSON.
    3.  `ShoppingListOptimizer` calculates costs against `Deal` table.
    4.  Data stored in PostgreSQL via SQLModel.
*   **Observations:**
    *   **Separation of Concerns:** well-maintained. "Agents" isolate LLM logic; "Services" isolate business logic (shopping math).
    *   **Mocking:** Strong patterns for mocking AI and Scraping (via environment variables and interfaces), crucial for MVP development.

## 3. Code Quality & Patterns

*   **Backend:**
    *   **Style:** Follows PEP 8 generally. Type hinting is used extensively (good).
    *   **Patterns:** Repository pattern is implicitly handled by SQLModel sessions. Service layer handles complex logic.
    *   **Error Handling:** Basic try/catch blocks in API endpoints, returning HTTP 500s. Could be more granular.
    *   **Testing:** `pytest` suite exists and **passes** (6 tests). Covers API flows and Shopping logic.
    *   **Concern:** Mixed use of `async` (FastAPI) and synchronous database calls. While `SQLModel` supports async, the code often uses synchronous `Session` dependency, which can block the main thread under load.

*   **Frontend:**
    *   **Style:** Modern React (Hooks). Clean component composition.
    *   **Readability:** High. Variable names are descriptive.
    *   **Linting:** **BROKEN.** `npm run lint` fails due to configuration errors in `eslint.config.js` (React Hooks plugin compatibility issue).
    *   **Testing:** Non-existent. No test scripts or files found for frontend.

## 4. Dependencies & Tech Stack

*   **Backend:**
    *   `fastapi==0.111.0`, `uvicorn==0.30.1` (Modern).
    *   `sqlmodel==0.0.19`, `alembic` (Standard).
    *   `openai` (for OpenRouter).
    *   `faker` (for mock data).
*   **Frontend:**
    *   `react==18.3.1`, `vite==6.0.5` (Very recent).
    *   `tailwindcss` (Standard for styling).
    *   `lucide-react` (Icons).
*   **Management:** `requirements.txt` (Python) and `package.json` (Node). Simple and effective for this scale.
*   **Security:** No obvious vulnerable dependencies found in a quick scan, but `sqlmodel` is still in beta (< 1.0).

## 5. Documentation

*   **READMEs:**
    *   Root `README.md` is slightly confusing as it references `cd backend` which leads to the empty top-level folder.
    *   `smart-meal-planner/README.md` is excellent: clear features, "Walking Skeleton" context, and accurate run instructions.
*   **API Documentation:** Auto-generated via FastAPI (`/docs`), which is sufficient.
*   **Comments:** Code is self-documenting with moderate commenting. Complex logic (like `ShoppingListOptimizer`) is adequately commented.

## 6. Security & Best Practices

*   **Secrets:** API Keys (`OPENROUTER_API_KEY`) and DB credentials are properly externalized to `.env` files. `env.example` files are provided.
*   **Input Validation:** Pydantic models (`UserCreate`, etc.) provide strong validation for API inputs.
*   **CORS:** `allow_origins=["*"]` is enabled. Acceptable for MVP/Dev, but **must** be restricted for production.
*   **SQL Injection:** Mitigated by use of ORM (SQLModel/SQLAlchemy).

## 7. Performance Considerations

*   **Database:**
    *   N+1 query potential in `list_deals` (`select(Deal, Product, Store)...`). It joins, but fetching logic should be monitored as data grows.
    *   Synchronous DB sessions in `async` endpoints will hurt throughput.
*   **Frontend:**
    *   Vite build is optimized.
    *   No obvious large bundles.
*   **AI:** LLM calls are slow by nature. The system processes them synchronously in the HTTP request (`generate_meal_plan`). This will likely time out or hang the browser for 30s+. **Recommendation:** Move to background tasks (Celery/RQ) or `BackgroundTasks` in FastAPI.

## 8. Maintainability

*   **Complexity:** Low. The codebase is approachable.
*   **Onboarding:** Easy, provided the developer ignores the confusing top-level `backend/` folder.
*   **Deployment:** Docker Compose is well-configured for a "production-lite" setup.
*   **Technical Debt:**
    *   The "Sync DB in Async Route" pattern.
    *   Broken Frontend Linting.
    *   Lack of Frontend Tests.

## 9. Strengths

*   **MVP Clarity:** The project perfectly scopes a "Walking Skeleton"—it connects all parts (UI -> API -> DB -> AI) without over-engineering any single part.
*   **Testing Culture:** Backend tests exist and pass from the start, which is rare for POCs.
*   **Modern Stack:** Using the latest tools (Vite, FastAPI, SQLModel) reduces legacy drag.

## 10. Priority Recommendations

1.  **Fix Frontend Linting (High Impact, Low Effort):**
    *   The `eslint.config.js` is misconfigured for the installed plugins. Fixing this ensures code quality doesn't degrade.
2.  **Delete Legacy Directory (Low Impact, Low Effort):**
    *   Remove the top-level `backend/` directory to prevent developer confusion.
3.  **Correct Async/Sync Database Usage (High Impact, Medium Effort):**
    *   Either switch `app/api/endpoints.py` to use `AsyncSession` with `await`, or remove `async def` from endpoints (making them standard threads) to prevent blocking the event loop.
4.  **Implement Background Tasks for AI (High Impact, Medium Effort):**
    *   Meal plan generation is slow. Move `planner.generate_plan(user)` to a background task and use polling or websockets to update the UI.
5.  **Add Frontend Tests (Medium Impact, High Effort):**
    *   Add basic unit tests (Vitest) or E2E tests (Playwright) to verify the UI flow, as currently there are none.
6.  **Tighten CORS Policy (Security):**
    *   Change `allow_origins=["*"]` to specific frontend URLs for non-development environments.
