# Smart Meal Planner & Deal Aggregator

A "Walking Skeleton" Proof of Concept (POC) for an AI-powered meal planner that optimizes for grocery deals.

## Features (POC)
- **Mock Scraper**: Generates realistic deal data for Walmart, Provigo, IGA, Metro, and Maxi (Quebec).
- **Meal Planner**: AI-driven generation of **7-day meal plans** (21 meals) based on dietary preferences (Vegetarian/Vegan supported).
- **Deal Optimization**: Prioritizes ingredients currently on sale.
- **Shopping List**: Automatically consolidates items and highlights AI-recommended store choices.
- **Tech Stack**: FastAPI, React, PostgreSQL (or SQLite local), TailwindCSS.

## Running Locally (Quick Start)

The easiest way to run the MVP is using the local SQLite mode.

### 1. Backend Setup
Navigate to the backend directory:
```bash
cd backend
```

Install Python dependencies:
```bash
pip install -r requirements.txt
```

Run the server with SQLite fallback enabled:
```bash
USE_SQLITE_LOCAL=True uvicorn app.main:app --reload
```
*The API will be available at `http://localhost:8000`*

### 2. Frontend Setup
Open a new terminal and navigate to the frontend directory:
```bash
cd frontend
```

Install Node.js dependencies:
```bash
npm install
```

Start the development server:
```bash
npm run dev
```
*Access the application at `http://localhost:5173`*

## Running with Docker (Production-like)
1. Ensure you have Docker and Docker Compose installed.
2. Create a `.env` file in the root directory (see `.env.example`).
3. Run:
   ```bash
   docker compose up --build
   ```
4. Access the app at `http://localhost:5173`.

## MVP Walkthrough
1. **Onboarding**: Enter your postal code (e.g., H4T 1V6) and select dietary preferences (e.g., Vegetarian).
2. **Seed Data**: If no deals appear, click "Seed Mock Data" on the Deals page.
3. **Meal Plan**: Click "Generate My Plan" to get a full 7-day schedule with breakfast, lunch, and dinner.
4. **Shopping List**: View your consolidated list and estimated savings.
