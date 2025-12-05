# Smart Meal Planner & Deal Aggregator

A "Walking Skeleton" Proof of Concept (POC) for an AI-powered meal planner that optimizes for grocery deals.

## Features (POC)
- **Mock Scraper**: Generates realistic deal data for Walmart, Provigo, and IGA (Quebec).
- **Meal Planner**: AI-driven generation of 3-day meal plans based on dietary preferences.
- **Deal Optimization**: Prioritizes ingredients currently on sale.
- **Tech Stack**: FastAPI, React, PostgreSQL, Redis, Docker.

## Running with Docker (Recommended)
1. Ensure you have Docker and Docker Compose installed.
2. Create a `.env` file in the root directory (see `.env.example`).
3. Run:
   ```bash
   docker compose up --build
   ```
4. Access the app at `http://localhost:5173`.

## Running Locally (Development)
If Docker is not available, you can run the services individually.

### Backend
1. Navigate to `backend/`.
2. Install dependencies: `pip install -r requirements.txt`.
3. Run with SQLite fallback:
   ```bash
   uvicorn app.main:app --reload
   ```

### Frontend
1. Navigate to `frontend/`.
2. Install dependencies: `npm install`.
3. Run:
   ```bash
   npm run dev
   ```
