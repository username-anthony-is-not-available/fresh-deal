
import React, { useEffect, useState } from 'react';
import MealCard from '../components/MealCard';
import NutritionSummary from '../components/NutritionSummary';
import { RefreshCw, Calendar as CalendarIcon, Lightbulb } from 'lucide-react';

const MealPlanPage = () => {
  const [plan, setPlan] = useState(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState(null);

  const userId = localStorage.getItem('user_id') || 1; // Default to 1 for dev

  useEffect(() => {
    const fetchLatestPlan = async () => {
      try {
        const res = await fetch(`http://localhost:8000/api/plans/${userId}/latest`);
        if (res.ok) {
          const data = await res.json();
          setPlan(data);
        } else {
           console.log("No existing plan or API error");
        }
      } catch (e) {
        console.log("Network error fetching plan", e);
        setError(e.message);
      } finally {
        setLoading(false);
      }
    };

    fetchLatestPlan();
  }, [userId]);

  const pollTaskStatus = async (taskId) => {
      const intervalId = setInterval(async () => {
          try {
              const res = await fetch(`http://localhost:8000/api/tasks/${taskId}`);
              if (res.ok) {
                  const data = await res.json();
                  if (data.status === "SUCCESS") {
                      clearInterval(intervalId);
                      setPlan(data.result);
                      setGenerating(false);
                  } else if (data.status === "FAILURE" || data.status === "Failed") {
                      clearInterval(intervalId);
                      setError("Plan generation failed: " + data.error);
                      setGenerating(false);
                  }
                  // If PENDING or STARTED, continue polling
              } else {
                   clearInterval(intervalId);
                   setError("Failed to check task status");
                   setGenerating(false);
              }
          } catch {
              clearInterval(intervalId);
              setError("Network error polling status");
              setGenerating(false);
          }
      }, 2000); // Poll every 2 seconds
  };

  const generatePlan = async () => {
    setGenerating(true);
    setError(null);
    try {
      const res = await fetch(`http://localhost:8000/api/plans/generate?user_id=${userId}`, {
        method: 'POST'
      });
      if (res.ok) {
        const data = await res.json();
        // The API now returns a task_id
        if (data.task_id) {
            pollTaskStatus(data.task_id);
        } else {
            // Fallback for sync response (should not happen with new API)
            setPlan(data);
            setGenerating(false);
        }
      } else {
         const txt = await res.text();
         console.error("Generate failed", txt);
         setError(`Generate failed: ${res.status}`);
         setGenerating(false);
      }
    } catch (e) {
      console.error("Failed to generate", e);
      setError(`Network error: ${e.message}`);
      setGenerating(false);
    }
  };

  if (loading) return <div className="p-8 text-center">Loading...</div>;
  if (error) return <div className="p-8 text-center text-red-600">Error: {error}</div>;

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
           <p className="text-gray-500 mt-2">Analyzing 60+ recipes and 100+ deals...</p>
           <p className="text-sm text-gray-400 mt-4">This might take up to 30 seconds.</p>
        </div>
     );
  }

  // Handle both structure formats (old "days", new "meal_plan")
  const planDays = plan.meal_plan || plan.days || [];

  // Extract dates for display
  const startDate = planDays.length > 0 ? planDays[0].date : "Upcoming Week";
  const endDate = planDays.length > 0 ? planDays[planDays.length - 1].date : "";
  const dateRange = startDate && endDate ? `${startDate} - ${endDate}` : "This Week";

  // Parse Nutrition Data
  // const nutritionSummary = plan.nutritional_summary || plan.shopping_summary || {};
  // const nutritionData = [
  //    { name: 'Protein', value: nutritionSummary.avg_daily_protein || 0, unit: 'g', color: '#3b82f6' },
  //    { name: 'Calories', value: nutritionSummary.avg_daily_calories || 0, unit: 'kcal', color: '#ef4444' },
  // ];

  return (
    <div>
      <div className="flex items-center justify-between mb-8">
         <div>
            <h1 className="text-3xl font-bold text-gray-900">Weekly Meal Plan</h1>
            <p className="text-gray-500">{dateRange}</p>
         </div>
         <button
           onClick={generatePlan}
           disabled={generating}
           className="flex items-center gap-2 text-primary-700 bg-primary-50 px-4 py-2 rounded-lg hover:bg-primary-100 font-medium disabled:opacity-50"
         >
            <RefreshCw className={`w-4 h-4 ${generating ? 'animate-spin' : ''}`} />
            {generating ? 'Generating...' : 'Regenerate'}
         </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-8">
         <div className="lg:col-span-3 space-y-8">
            {planDays.map((day) => {
               // Transform day object to list of meals if needed
               // The new structure has breakfast, lunch, dinner keys
               let meals = [];
               if (day.meals && Array.isArray(day.meals)) {
                  meals = day.meals;
               } else {
                  meals = [
                     { ...day.breakfast, type: 'Breakfast' },
                     { ...day.lunch, type: 'Lunch' },
                     { ...day.dinner, type: 'Dinner' }
                  ].filter(m => m && (m.recipe_name || m.name)); // Filter out empty meals if any
               }

               return (
                  <div key={day.day} className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
                     <div className="bg-gray-50 px-6 py-3 border-b border-gray-200 flex justify-between items-center">
                        <h3 className="font-bold text-gray-900">
                           {day.day_name || `Day ${day.day}`} <span className="text-gray-400 font-normal text-sm ml-2">{day.display_date || day.date}</span>
                        </h3>
                     </div>
                     <div className="p-6 grid grid-cols-1 md:grid-cols-3 gap-6">
                        {meals.map((meal, idx) => (
                           <div key={idx} className="flex flex-col h-full">
                              <MealCard type={meal.type} meal={{name: meal.recipe_name || meal.name, ...meal}} />
                              {meal.reason && (
                                 <div className="mt-2 text-xs text-blue-600 bg-blue-50 p-2 rounded flex gap-2 items-start">
                                    <Lightbulb className="w-3 h-3 mt-0.5 flex-shrink-0" />
                                    <span>{meal.reason}</span>
                                 </div>
                              )}
                           </div>
                        ))}
                     </div>
                  </div>
               );
            })}
         </div>

         <div className="space-y-6">
            <div className="sticky top-24">
               {plan.weekly_overview && (
                  <div className="bg-indigo-50 p-4 rounded-lg border border-indigo-100 mb-6">
                     <h4 className="font-semibold text-indigo-900 mb-2 text-sm uppercase tracking-wide">Weekly Focus</h4>
                     <p className="text-sm text-indigo-800 leading-relaxed">
                        {plan.weekly_overview}
                     </p>
                  </div>
               )}

               <h3 className="font-semibold text-gray-900 mb-4">Estimated Savings</h3>
               <div className="bg-green-50 p-4 rounded-lg border border-green-100 mb-6">
                  <div className="text-3xl font-bold text-green-700">
                     ${plan.shopping_summary?.estimated_savings || "0.00"}
                  </div>
                  <p className="text-xs text-green-600 mt-1">Saved compared to regular prices</p>
               </div>

               <div className="bg-gray-50 p-4 rounded-lg border border-gray-200">
                  <h4 className="font-semibold text-gray-800 mb-2 text-sm">Key Deals Used</h4>
                  <ul className="text-sm text-gray-600 space-y-1">
                     {plan.shopping_summary?.key_deals_used?.map((deal, i) => (
                        <li key={i} className="flex items-center gap-2">
                           <span className="w-1.5 h-1.5 bg-green-500 rounded-full"></span>
                           {deal}
                        </li>
                     )) || <li className="text-gray-400 italic">No deals listed</li>}
                  </ul>
               </div>
            </div>
         </div>
      </div>
    </div>
  );
};

export default MealPlanPage;
