#!/bin/bash
echo "🍽️  Smart Meal Planner Demo Setup"
echo "================================"

# Check if running for first time
if [ ! -f "backend/.env" ]; then
    echo "⚠️  No .env file found. Creating template..."
    cat > backend/.env << EOF
OPENROUTER_API_KEY=your_key_here
USE_SQLITE_LOCAL=True
EOF
    echo "✅ Created backend/.env - please add your OpenRouter API key"
    exit 1
fi

# Start backend
echo "🚀 Starting backend..."
cd backend
USE_SQLITE_LOCAL=True uvicorn app.main:app --reload &
BACKEND_PID=$!

# Wait for backend
sleep 3

# Start frontend
echo "🎨 Starting frontend..."
cd ../frontend
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
trap "kill $BACKEND_PID $FRONTEND_PID" EXIT
wait
