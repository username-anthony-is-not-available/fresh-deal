#!/bin/bash
echo "🍽️  Smart Meal Planner Demo Setup"
echo "================================"

# Check if running for first time
if [ ! -f "backend/.env" ] && [ ! -f "smart-meal-planner/backend/.env" ]; then
    echo "⚠️  No .env file found. Creating template..."
    cat > smart-meal-planner/backend/.env << EOF
OPENROUTER_API_KEY=your_key_here
USE_SQLITE_LOCAL=True
USE_MOCK_AI=True
EOF
    echo "✅ Created backend/.env - please add your OpenRouter API key"
fi

BACKEND_DIR="backend"
if [ ! -d "$BACKEND_DIR" ] && [ -d "smart-meal-planner/backend" ]; then
    BACKEND_DIR="smart-meal-planner/backend"
fi

FRONTEND_DIR="frontend"
if [ ! -d "$FRONTEND_DIR" ] && [ -d "smart-meal-planner/frontend" ]; then
    FRONTEND_DIR="smart-meal-planner/frontend"
fi

# Start backend
echo "🚀 Starting backend..."
cd "$BACKEND_DIR" || exit 1
env USE_SQLITE_LOCAL=True uvicorn app.main:app --reload &
BACKEND_PID=$!

# Wait for backend
sleep 3

# Start frontend
echo "🎨 Starting frontend..."
cd "../../$FRONTEND_DIR" || cd "../$FRONTEND_DIR" || exit 1
npm run dev &
FRONTEND_PID=$!

echo ""
echo "✅ App is running!"
echo "   Frontend: http://localhost:5173"
echo "   Backend:  http://localhost:8000"
echo "   API Docs: http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop all services"

# Wait for interrupt
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null" EXIT
wait
