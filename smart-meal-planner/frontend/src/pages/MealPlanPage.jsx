import React, { useEffect, useState } from 'react';
import MealCard from '../components/MealCard';
import NutritionSummary from '../components/NutritionSummary';
import { RefreshCw, Calendar as CalendarIcon } from 'lucide-react';

const MealPlanPage = () => {
  const [plan, setPlan] = useState(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);

  const userId = localStorage.getItem('user_id') || 1; // Default to 1 for dev

  useEffect(() => {
    fetchLatestPlan();
  }, []);

  const fetchLatestPlan = async () => {
    try {
      const res = await fetch(`http://localhost:8000/api/plans/${userId}/latest`);
      if (res.ok) {
        const data = await res.json();
        setPlan(data);
      }
    } catch (e) {
      console.log("No existing plan found");
    } finally {
      setLoading(false);
    }
  };

  const generatePlan = async () => {
    setGenerating(true);
    try {
      const res = await fetch(`http://localhost:8000/api/plans/generate?user_id=${userId}`, {
        method: 'POST'
      });
      if (res.ok) {
        const data = await res.json();
        setPlan(data);
      }
    } catch (e) {
      console.error("Failed to generate", e);
    } finally {
      setGenerating(false);
    }
  };

  if (loading) return <div className="p-8 text-center">Loading...</div>;

  if (!plan && !generating) {
    return (
      <div className="text-center py-20 bg-white rounded-xl border border-dashed border-gray-300">
         <div className="mx-auto w-16 h-16 bg-primary-100 rounded-full flex items-center justify-center mb-4">
            <CalendarIcon className="w-8 h-8 text-primary-600" />
         </div>
         <h2 className="text-2xl font-bold text-gray-900 mb-2">No Meal Plan Yet</h2>
         <p className="text-gray-500 mb-8 max-w-md mx-auto">
            Generate your first 7-day meal plan based on this week's best grocery deals.
         </p>
         <button
           onClick={generatePlan}
           className="bg-primary-600 text-white px-6 py-3 rounded-lg font-medium hover:bg-primary-700 shadow-lg transition-all hover:scale-105"
         >
           Generate My Plan
         </button>
      </div>
    );
  }

  if (generating) {
     return (
        <div className="text-center py-32">
           <div className="animate-spin rounded-full h-16 w-16 border-4 border-primary-200 border-t-primary-600 mx-auto mb-6"></div>
           <h2 className="text-xl font-bold text-gray-900">AI is crafting your menu...</h2>
           <p className="text-gray-500 mt-2">Analyzing 150+ deals and optimizing for nutrition.</p>
        </div>
     );
  }

  // Mock Nutrition Data (Will come from API later)
  const nutritionData = [
     { name: 'Protein', value: 125, unit: 'g', color: '#3b82f6' },
     { name: 'Carbs', value: 250, unit: 'g', color: '#22c55e' },
     { name: 'Fats', value: 70, unit: 'g', color: '#eab308' },
  ];

  return (
    <div>
      <div className="flex items-center justify-between mb-8">
         <div>
            <h1 className="text-3xl font-bold text-gray-900">Weekly Meal Plan</h1>
            <p className="text-gray-500">Dec 9 - Dec 15, 2025</p>
         </div>
         <button
           onClick={generatePlan}
           className="flex items-center gap-2 text-primary-700 bg-primary-50 px-4 py-2 rounded-lg hover:bg-primary-100 font-medium"
         >
            <RefreshCw className="w-4 h-4" />
            Regenerate
         </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-8">
         <div className="lg:col-span-3 space-y-8">
            {plan.days.map((day) => (
               <div key={day.day} className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
                  <div className="bg-gray-50 px-6 py-3 border-b border-gray-200 flex justify-between items-center">
                     <h3 className="font-bold text-gray-900">Day {day.day}</h3>
                     <span className="text-xs font-medium text-gray-500 uppercase tracking-wider">
                        ~2100 kcal
                     </span>
                  </div>
                  <div className="p-6 grid grid-cols-1 md:grid-cols-3 gap-6">
                     {day.meals.map((meal, idx) => (
                        <MealCard key={idx} type={meal.type} meal={meal} />
                     ))}
                  </div>
               </div>
            ))}
         </div>

         <div className="space-y-6">
            <div className="sticky top-24">
               <h3 className="font-semibold text-gray-900 mb-4">Weekly Nutrition Avg.</h3>
               <NutritionSummary data={nutritionData} />

               <div className="mt-8 bg-blue-50 p-4 rounded-lg border border-blue-100">
                  <h4 className="font-semibold text-blue-800 mb-2 text-sm">Chef's Note</h4>
                  <p className="text-sm text-blue-700">
                     {plan.shopping_list_summary}
                  </p>
               </div>
            </div>
         </div>
      </div>
    </div>
  );
};

export default MealPlanPage;
