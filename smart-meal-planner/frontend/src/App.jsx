import React, { useState } from 'react';
import axios from 'axios';

// Simple Service (can be moved to separate file)
const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';

function App() {
  const [step, setStep] = useState(1);
  const [user, setUser] = useState(null);
  const [plan, setPlan] = useState(null);
  const [loading, setLoading] = useState(false);
  const [formData, setFormData] = useState({
    postal_code: 'H4T 1V6',
    household_size: 2,
    dietary_preferences: 'None'
  });

  const handleOnboard = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      // 1. Onboard
      const userRes = await axios.post(`${API_URL}/onboard`, formData);
      setUser(userRes.data);

      // 2. Seed Data (Dev only)
      await axios.post(`${API_URL}/data/seed`);

      // 3. Generate Plan
      const planRes = await axios.post(`${API_URL}/plans/generate?user_id=${userRes.data.id}`);
      setPlan(planRes.data);
      setStep(2);
    } catch (err) {
      console.error(err);
      alert("Error generating plan. Check console.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 p-8">
      <div className="max-w-4xl mx-auto">
        <header className="mb-8 text-center">
          <h1 className="text-4xl font-bold text-green-700">Smart Meal Planner</h1>
          <p className="text-gray-600">Save money on groceries with AI-optimized meal plans.</p>
        </header>

        {step === 1 && (
          <div className="bg-white p-6 rounded-lg shadow-md max-w-md mx-auto">
            <h2 className="text-2xl font-semibold mb-4">Get Started</h2>
            <form onSubmit={handleOnboard} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700">Postal Code (QC)</label>
                <input
                  type="text"
                  value={formData.postal_code}
                  onChange={(e) => setFormData({...formData, postal_code: e.target.value})}
                  className="mt-1 block w-full rounded-md border-gray-300 shadow-sm p-2 border"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700">Household Size</label>
                <input
                  type="number"
                  value={formData.household_size}
                  onChange={(e) => setFormData({...formData, household_size: parseInt(e.target.value)})}
                  className="mt-1 block w-full rounded-md border-gray-300 shadow-sm p-2 border"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700">Dietary Preferences</label>
                <input
                  type="text"
                  value={formData.dietary_preferences}
                  onChange={(e) => setFormData({...formData, dietary_preferences: e.target.value})}
                  className="mt-1 block w-full rounded-md border-gray-300 shadow-sm p-2 border"
                  placeholder="e.g. Vegetarian, No Peanuts"
                />
              </div>
              <button
                type="submit"
                disabled={loading}
                className="w-full bg-green-600 text-white py-2 px-4 rounded-md hover:bg-green-700 disabled:opacity-50"
              >
                {loading ? 'Generating Plan...' : 'Generate Meal Plan'}
              </button>
            </form>
          </div>
        )}

        {step === 2 && plan && (
          <div className="space-y-6">
            <div className="bg-white p-6 rounded-lg shadow-md">
              <h2 className="text-2xl font-semibold mb-4">Your 3-Day Plan</h2>
              <div className="grid md:grid-cols-3 gap-4">
                {plan.days.map((day) => (
                  <div key={day.day} className="border p-4 rounded-md">
                    <h3 className="font-bold text-lg mb-2 text-green-800">Day {day.day}</h3>
                    {day.meals.map((meal, idx) => (
                      <div key={idx} className="mb-3">
                        <span className="text-xs font-semibold uppercase text-gray-500">{meal.type}</span>
                        <p className="font-medium">{meal.name}</p>
                        <p className="text-xs text-gray-600">{meal.ingredients.join(', ')}</p>
                      </div>
                    ))}
                  </div>
                ))}
              </div>
            </div>

            <div className="bg-white p-6 rounded-lg shadow-md border-l-4 border-yellow-400">
              <h2 className="text-xl font-semibold mb-2">Shopping Summary</h2>
              <p className="text-gray-700 whitespace-pre-line">{plan.shopping_list_summary}</p>
            </div>

            <button
              onClick={() => setStep(1)}
              className="text-green-600 hover:underline"
            >
              Start Over
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

export default App;
