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
```

## API Endpoints
- `POST /meal-plan/generate` - Generate meal plan
- `GET /deals` - Get current deals
- `GET /stores` - List stores near postal code

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
