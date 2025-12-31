
import React, { useEffect, useState, useCallback } from 'react';
import { DndProvider } from 'react-dnd';
import { HTML5Backend } from 'react-dnd-html5-backend';
import DraggableMealCard from '../components/DraggableMealCard';
import MealSlot from '../components/MealSlot';
import DietaryFilters from '../components/DietaryFilters';
import { RefreshCw, Calendar as CalendarIcon, Lightbulb, Save } from 'lucide-react';
import api from '../services/api';
import SkeletonLoader from '../components/SkeletonLoader';
import { showSuccessToast, showErrorToast } from '../utils/toast';

const MealPlanSkeleton = () => (
  <div>
    <div className="flex items-center justify-between mb-8">
      <div>
        <SkeletonLoader className="h-9 w-64 mb-2" />
        <SkeletonLoader className="h-5 w-48" />
      </div>
      <SkeletonLoader className="h-10 w-32" />
    </div>
    <div className="grid grid-cols-1 lg:grid-cols-4 gap-8">
      <div className="lg:col-span-3 space-y-8">
        {[...Array(3)].map((_, i) => (
          <div key={i} className="bg-white rounded-xl shadow-sm border border-gray-200">
            <div className="bg-gray-50 px-6 py-3 border-b border-gray-200">
              <SkeletonLoader className="h-6 w-1/3" />
            </div>
            <div className="p-6 grid grid-cols-1 md:grid-cols-3 gap-6">
              <SkeletonLoader className="h-64" />
              <SkeletonLoader className="h-64" />
              <SkeletonLoader className="h-64" />
            </div>
          </div>
        ))}
      </div>
      <div className="space-y-6">
        <SkeletonLoader className="h-32" />
        <SkeletonLoader className="h-24" />
        <SkeletonLoader className="h-48" />
      </div>
    </div>
  </div>
);

const MealPlanPage = () => {
  const [plan, setPlan] = useState(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [regeneratingMeal, setRegeneratingMeal] = useState(null); // e.g., { day: 1, type: 'Breakfast' }
  const [error, setError] = useState(null);
  const [dietaryPreferences, setDietaryPreferences] = useState([]);

  const userId = localStorage.getItem('user_id') || 1;

  const dietaryOptions = ["vegetarian", "vegan", "gluten-free", "keto", "paleo"];

  const handleDietaryChange = (e) => {
    const { value, checked } = e.target;
    setDietaryPreferences(prev =>
      checked ? [...prev, value] : prev.filter(pref => pref !== value)
    );
  };

  const fetchLatestPlan = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.get(`/plans/${userId}/latest`);
      // Normalize plan structure on fetch
      if (data && !data.meal_plan && data.days) {
        data.meal_plan = data.days.map(day => ({
          ...day,
          meals: [
            { ...(day.breakfast || {}), type: 'Breakfast' },
            { ...(day.lunch || {}), type: 'Lunch' },
            { ...(day.dinner || {}), type: 'Dinner' },
          ],
        }));
        delete data.days;
      }
      setPlan(data);
    } catch (e) {
      // A 404 is an expected outcome for users without a plan yet.
      // We don't treat it as a render-blocking error.
      if (e.response && e.response.status === 404) {
        setPlan(null); // Ensure plan is null to show the generation view
      } else {
        // For other errors (500, network issues), show an error message.
        setError('Failed to fetch a meal plan. Please try generating a new one.');
      }
    } finally {
      setLoading(false);
    }
  }, [userId]);

  useEffect(() => {
    fetchLatestPlan();
  }, [fetchLatestPlan]);

  useEffect(() => {
    const fetchUserSettings = async () => {
      if (!userId) return;
      try {
        const user = await api.get(`/users/${userId}`);
        if (user && user.dietary_preferences) {
          setDietaryPreferences(user.dietary_preferences);
        }
      } catch (err) {
        console.error("Failed to fetch user settings", err);
      }
    };
    fetchUserSettings();
  }, [userId]);

  const pollTaskStatus = useCallback(async (taskId) => {
    const intervalId = setInterval(async () => {
      try {
        const data = await api.get(`/tasks/${taskId}`);
        if (data.status === "SUCCESS") {
          clearInterval(intervalId);
          setPlan(data.result);
          showSuccessToast('Your new meal plan is ready!');
          setGenerating(false);
        } else if (data.status === "FAILURE" || data.status === "Failed") {
          clearInterval(intervalId);
          showErrorToast(`Plan generation failed: ${data.error}`);
          setGenerating(false);
        }
      } catch {
        clearInterval(intervalId);
        setGenerating(false);
      }
    }, 2000);
  }, []);

  const savePreferences = async () => {
    try {
      await api.patch(`/users/${userId}`, { dietary_preferences: dietaryPreferences });
      showSuccessToast('Dietary preferences saved!');
    } catch (error) {
      showErrorToast('Failed to save preferences.');
    }
  };

  const generatePlan = async () => {
    setGenerating(true);
    setError(null);
    try {
      // First, update the user's dietary preferences
      await savePreferences();

      // Then, trigger the meal plan generation
      const data = await api.post(`/plans/generate?user_id=${userId}`);
      if (data.task_id) {
        pollTaskStatus(data.task_id);
      } else {
        setPlan(data);
        showSuccessToast('Your new meal plan is ready!');
        setGenerating(false);
      }
    } catch (e) {
      setGenerating(false);
      // The interceptor will show the error toast.
    }
  };

  if (loading) return <MealPlanSkeleton />;
  if (error && !plan) return <div className="p-8 text-center text-red-600">{error}</div>;

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

        <div className="max-w-md mx-auto mb-8">
          <DietaryFilters selected={dietaryPreferences} onChange={handleDietaryChange} />
        </div>

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

  const planDays = plan.meal_plan || plan.days || [];
  const startDate = planDays.length > 0 ? planDays[0].date : "Upcoming Week";
  const endDate = planDays.length > 0 ? planDays[planDays.length - 1].date : "";
  const dateRange = startDate && endDate ? `${startDate} - ${endDate}` : "This Week";

  const handleDrop = (item, target) => {
    const { day: sourceInfo, type: sourceType } = item;
    const { day: targetInfo, type: targetType } = target;

    setPlan(currentPlan => {
      const planToUpdate = JSON.parse(JSON.stringify(currentPlan));

      if (!planToUpdate.meal_plan) return currentPlan;

      const sourceDayIndex = planToUpdate.meal_plan.findIndex(d => d.day === sourceInfo.day);
      const targetDayIndex = planToUpdate.meal_plan.findIndex(d => d.day === targetInfo.day);

      if (sourceDayIndex === -1 || targetDayIndex === -1) return currentPlan;

      const sourceMeals = planToUpdate.meal_plan[sourceDayIndex].meals;
      const targetMeals = planToUpdate.meal_plan[targetDayIndex].meals;

      // Find by type, which is guaranteed to be stable (Breakfast, Lunch, Dinner)
      const sourceMealIndex = sourceMeals.findIndex(m => m.type === sourceType);
      const targetMealIndex = targetMeals.findIndex(m => m.type === targetType);

      if (sourceMealIndex === -1 || targetMealIndex === -1) return currentPlan;

      // Simple swap of the meal objects in the array is sufficient
      const tempMeal = sourceMeals[sourceMealIndex];
      sourceMeals[sourceMealIndex] = targetMeals[targetMealIndex];
      targetMeals[targetMealIndex] = tempMeal;

      return planToUpdate;
    });
  };

  const handleRegenerateMeal = async (day, type) => {
    const mealIdentifier = { day: day.day, type };
    setRegeneratingMeal(mealIdentifier);

    try {
      const newMeal = await api.post(`/plans/regenerate-meal`, {
        user_id: parseInt(userId),
        day: day.day_name,
        type: type,
        dietary_preferences: dietaryPreferences,
        existing_meals: plan.meal_plan.flatMap(d => d.meals)
      });

      setPlan(currentPlan => {
        const newPlan = JSON.parse(JSON.stringify(currentPlan));
        const dayIndex = newPlan.meal_plan.findIndex(d => d.day === day.day);
        if (dayIndex === -1) return currentPlan;

        const mealIndex = newPlan.meal_plan[dayIndex].meals.findIndex(m => m.type === type);
        if (mealIndex === -1) return currentPlan;

        newPlan.meal_plan[dayIndex].meals[mealIndex] = { ...newPlan.meal_plan[dayIndex].meals[mealIndex], ...newMeal };
        return newPlan;
      });

      showSuccessToast(`${type} for ${day.day_name} has been regenerated!`);

    } catch (err) {
      showErrorToast(`Failed to regenerate meal. Please try again.`);
    } finally {
      setRegeneratingMeal(null);
    }
  };

  return (
    <DndProvider backend={HTML5Backend}>
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
          <DietaryFilters selected={dietaryPreferences} onChange={handleDietaryChange} />
          {planDays.map((day) => {
            let meals = [];
            if (day.meals && Array.isArray(day.meals)) {
              meals = day.meals;
            } else {
              meals = [
                { ...day.breakfast, type: 'Breakfast' },
                { ...day.lunch, type: 'Lunch' },
                { ...day.dinner, type: 'Dinner' }
              ].filter(m => m && (m.recipe_name || m.name));
            }

            return (
              <div key={day.day} className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
                <div className="bg-gray-50 px-6 py-3 border-b border-gray-200 flex justify-between items-center">
                  <h3 className="font-bold text-gray-900">
                    {day.day_name || `Day ${day.day}`} <span className="text-gray-400 font-normal text-sm ml-2">{day.display_date || day.date}</span>
                  </h3>
                </div>
                <div className="p-6 grid grid-cols-1 md:grid-cols-3 gap-6">
                  {meals.map((meal, idx) => {
                    const isRegenerating = regeneratingMeal && regeneratingMeal.day === day.day && regeneratingMeal.type === meal.type;
                    return (
                    <MealSlot key={idx} day={day} type={meal.type} onDrop={handleDrop}>
                      <DraggableMealCard
                        meal={{name: meal.recipe_name || meal.name, ...meal}}
                        day={day}
                        type={meal.type}
                        onRegenerate={() => handleRegenerateMeal(day, meal.type)}
                        isRegenerating={isRegenerating}
                        />
                      {meal.reason && (
                        <div className="mt-2 text-xs text-blue-600 bg-blue-50 p-2 rounded flex gap-2 items-start">
                          <Lightbulb className="w-3 h-3 mt-0.5 flex-shrink-0" />
                          <span>{meal.reason}</span>
                        </div>
                      )}
                    </MealSlot>
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
    </DndProvider>
  );
};

export default MealPlanPage;
