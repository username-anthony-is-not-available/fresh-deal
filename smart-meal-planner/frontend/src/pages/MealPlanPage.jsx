
import React, { useEffect, useState, useCallback } from 'react';
import { DndProvider } from 'react-dnd';
import { HTML5Backend } from 'react-dnd-html5-backend';
import DraggableMealCard from '../components/DraggableMealCard';
import MealSlot from '../components/MealSlot';
import DietaryFilters from '../components/DietaryFilters';
import { RefreshCw, Calendar as CalendarIcon, Lightbulb, PiggyBank, Search, X, Star, Send, Download, FileText } from 'lucide-react';
import clsx from 'clsx';
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
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedModel, setSelectedModel] = useState('standard');
  const [mealPlanFeedback, setMealPlanFeedback] = useState({ rating: 0, comment: '' });
  const [submittingFeedback, setSubmittingFeedback] = useState(false);
  const [exporting, setExporting] = useState(null); // 'ical' or 'pdf'

  const userId = localStorage.getItem('user_id') || 1;

  const modelOptions = [
    { id: 'standard', name: 'Standard (Llama 3.1)' },
    { id: 'chef', name: 'Culinary Expert (Claude 3.5)' },
    { id: 'creative', name: 'Creative Chef (Gemini 1.5)' },
    { id: 'budget', name: 'Budget Expert (Llama 70B)' },
  ];

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
      const data = await api.post(`/plans/generate?user_id=${userId}&model=${selectedModel}`);
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

        <div className="max-w-md mx-auto mb-8 space-y-6">
          <DietaryFilters selected={dietaryPreferences} onChange={handleDietaryChange} initialOpen={true} />

          <div className="space-y-2">
            <label className="text-sm font-medium text-gray-700">Recipe Generation Model</label>
            <select
              value={selectedModel}
              onChange={(e) => setSelectedModel(e.target.value)}
              className="w-full bg-white border border-gray-300 rounded-lg px-4 py-2.5 focus:ring-2 focus:ring-primary-500 focus:border-primary-500 outline-none transition-all"
            >
              {modelOptions.map(opt => (
                <option key={opt.id} value={opt.id}>{opt.name}</option>
              ))}
            </select>
          </div>
        </div>

        <button
          onClick={generatePlan}
          className="bg-primary-600 text-white px-8 py-4 rounded-xl font-bold hover:bg-primary-700 shadow-lg transition-all hover:scale-105 active:scale-95"
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

  const planDaysRaw = plan.meal_plan || plan.days || [];

  const filteredPlanDays = planDaysRaw.map(day => {
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

    const filteredMeals = meals.filter(meal => {
      if (!searchTerm) return true;
      const query = searchTerm.toLowerCase();
      const nameMatch = (meal.recipe_name || meal.name || '').toLowerCase().includes(query);
      const ingredientMatch = meal.ingredients?.some(ing => {
        const ingName = typeof ing === 'string' ? ing : (ing.item || '');
        return ingName.toLowerCase().includes(query);
      });
      return nameMatch || ingredientMatch;
    });

    return { ...day, meals: filteredMeals };
  }).filter(day => day.meals.length > 0);

  const planDays = filteredPlanDays;
  const startDate = planDaysRaw.length > 0 ? planDaysRaw[0].date : "Upcoming Week";
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

  const handleMealPlanFeedback = async () => {
    if (mealPlanFeedback.rating === 0) {
      showErrorToast('Please select a rating before submitting.');
      return;
    }
    setSubmittingFeedback(true);
    try {
      await api.post('/feedback', {
        meal_plan_id: plan.id,
        rating: mealPlanFeedback.rating,
        comment: mealPlanFeedback.comment
      });
      showSuccessToast('Thank you for your feedback on this meal plan!');
      setMealPlanFeedback({ rating: 0, comment: '' });
    } catch (error) {
      console.error("Failed to submit plan feedback", error);
      showErrorToast('Failed to submit feedback.');
    } finally {
      setSubmittingFeedback(false);
    }
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
        existing_meals: plan.meal_plan.flatMap(d => d.meals),
        model_type: selectedModel
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

  const handleExport = async (format) => {
    setExporting(format);
    try {
      const blobData = await api.get(`/plans/${userId}/export/${format}`, {
        responseType: 'blob',
      });

      const blob = new Blob([blobData], {
        type: format === 'ical' ? 'text/calendar' : 'application/pdf'
      });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `meal_plan_${userId}.${format === 'ical' ? 'ics' : 'pdf'}`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);

      showSuccessToast(`Meal plan exported as ${format.toUpperCase()}!`);
    } catch (err) {
      console.error(`Failed to export ${format}`, err);
      showErrorToast(`Failed to export meal plan. Please try again.`);
    } finally {
      setExporting(null);
    }
  };

  const quickFilters = ['Chicken', 'Beef', 'Pasta'];

  return (
    <DndProvider backend={HTML5Backend}>
      <div>
        <div className="flex flex-col sm:flex-row sm:items-center justify-between mb-6 gap-4">
          <div>
            <h1 className="text-2xl sm:text-3xl font-bold text-gray-900">Weekly Meal Plan</h1>
            <p className="text-gray-500 text-sm sm:text-base">{dateRange}</p>
          </div>
          <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3">
            <select
              value={selectedModel}
              onChange={(e) => setSelectedModel(e.target.value)}
              className="bg-white border border-gray-200 rounded-lg px-3 py-2 text-sm font-medium focus:ring-2 focus:ring-primary-500 focus:border-primary-500 outline-none transition-all"
            >
              {modelOptions.map(opt => (
                <option key={opt.id} value={opt.id}>{opt.name}</option>
              ))}
            </select>
            <div className="flex items-center gap-2">
              <button
                onClick={() => handleExport('ical')}
                disabled={exporting === 'ical'}
                className="flex items-center justify-center gap-2 text-gray-700 bg-white border border-gray-200 px-3 py-2 rounded-lg hover:bg-gray-50 font-medium disabled:opacity-50 shadow-sm transition-colors"
                title="Export to Calendar (iCal)"
              >
                <CalendarIcon className="w-4 h-4" />
                <span className="hidden md:inline">iCal</span>
              </button>
              <button
                onClick={() => handleExport('pdf')}
                disabled={exporting === 'pdf'}
                className="flex items-center justify-center gap-2 text-gray-700 bg-white border border-gray-200 px-3 py-2 rounded-lg hover:bg-gray-50 font-medium disabled:opacity-50 shadow-sm transition-colors"
                title="Export as PDF"
              >
                <FileText className="w-4 h-4" />
                <span className="hidden md:inline">PDF</span>
              </button>
              <button
                onClick={generatePlan}
                disabled={generating}
                className="flex items-center justify-center gap-2 text-primary-700 bg-primary-50 px-4 py-2.5 rounded-lg hover:bg-primary-100 font-semibold disabled:opacity-50 shadow-sm transition-colors"
              >
                <RefreshCw className={`w-4 h-4 ${generating ? 'animate-spin' : ''}`} />
                <span>{generating ? 'Generating...' : 'Regenerate Plan'}</span>
              </button>
            </div>
          </div>
        </div>

        {/* Interactive Filter Bar */}
        <div className="mb-8 space-y-4">
          <div className="relative group max-w-2xl">
            <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-gray-400 w-5 h-5 group-focus-within:text-primary-500 transition-colors" />
            <input
              type="text"
              placeholder="Search recipes or ingredients (e.g., 'chicken')..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full pl-12 pr-12 py-3 bg-white border border-gray-200 rounded-xl shadow-sm focus:ring-2 focus:ring-primary-500 focus:border-primary-500 outline-none transition-all"
            />
            {searchTerm && (
              <button
                onClick={() => setSearchTerm('')}
                className="absolute right-4 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 p-1"
              >
                <X className="w-4 h-4" />
              </button>
            )}
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <span className="text-sm font-medium text-gray-500 mr-2">Quick filters:</span>
            {quickFilters.map((ingredient) => (
              <button
                key={ingredient}
                onClick={() => setSearchTerm(searchTerm === ingredient ? '' : ingredient)}
                className={`px-4 py-1.5 rounded-full text-sm font-medium transition-all border ${
                  searchTerm.toLowerCase() === ingredient.toLowerCase()
                    ? 'bg-primary-600 text-white border-primary-600 shadow-md'
                    : 'bg-white text-gray-700 border-gray-200 hover:border-primary-300 hover:bg-primary-50'
                }`}
              >
                {ingredient}
              </button>
            ))}
          </div>
        </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-8">
        <div className="lg:col-span-3 space-y-8">
          <div className="lg:hidden">
            <div className="bg-green-600 rounded-xl p-6 text-white shadow-lg mb-6">
              <div className="flex justify-between items-center">
                <div>
                  <p className="text-green-100 text-xs uppercase font-bold tracking-wider mb-1">Estimated Savings</p>
                  <p className="text-4xl font-black">${plan.shopping_summary?.estimated_savings || "0.00"}</p>
                </div>
                <div className="bg-green-500 p-3 rounded-full shadow-inner">
                  <PiggyBank className="w-8 h-8 text-white" />
                </div>
              </div>
            </div>
          </div>

          {plan.nutritional_summary && (
            <div className="lg:hidden bg-primary-50 rounded-xl p-6 border border-primary-100 mb-6">
              <div className="flex justify-between items-center mb-4">
                <h4 className="font-bold text-primary-900 uppercase tracking-wider text-xs">Weekly Nutrition</h4>
                <span className="text-[10px] text-primary-400 italic">{plan.nutritional_summary.note}</span>
              </div>
              <div className="flex gap-8">
                <div>
                  <p className="text-2xl font-black text-primary-900">{plan.nutritional_summary.avg_daily_calories}</p>
                  <p className="text-[10px] text-primary-600 uppercase font-bold">Avg. Cals</p>
                </div>
                <div>
                  <p className="text-2xl font-black text-primary-900">{plan.nutritional_summary.avg_daily_protein}g</p>
                  <p className="text-[10px] text-primary-600 uppercase font-bold">Avg. Protein</p>
                </div>
              </div>
            </div>
          )}

          <DietaryFilters selected={dietaryPreferences} onChange={handleDietaryChange} />

          {searchTerm && planDays.length === 0 && (
            <div className="text-center py-12 bg-gray-50 rounded-xl border border-dashed border-gray-300">
              <Search className="w-12 h-12 text-gray-300 mx-auto mb-4" />
              <h3 className="text-lg font-medium text-gray-900">No matching meals found</h3>
              <p className="text-gray-500">Try a different ingredient or clear the search.</p>
              <button
                onClick={() => setSearchTerm('')}
                className="mt-4 text-primary-600 font-semibold hover:text-primary-700"
              >
                Clear search
              </button>
            </div>
          )}

          {planDays.map((day) => {
            const meals = day.meals;

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
                  );
                  })}
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

            <div className="hidden lg:block">
              <h3 className="font-semibold text-gray-900 mb-4">Estimated Savings</h3>
              <div className="bg-green-50 p-4 rounded-lg border border-green-100 mb-6">
                <div className="text-3xl font-bold text-green-700">
                  ${plan.shopping_summary?.estimated_savings || "0.00"}
                </div>
                <p className="text-xs text-green-600 mt-1">Saved compared to regular prices</p>
              </div>
            </div>

            {plan.nutritional_summary && (
              <div className="bg-primary-50 p-4 rounded-lg border border-primary-100 mb-6">
                <h4 className="font-semibold text-primary-900 mb-3 text-sm uppercase tracking-wide">Nutritional Summary</h4>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <p className="text-[10px] text-primary-600 uppercase font-bold">Avg. Calories</p>
                    <p className="text-xl font-black text-primary-900">{plan.nutritional_summary.avg_daily_calories} <span className="text-xs font-normal text-primary-500">kcal</span></p>
                  </div>
                  <div>
                    <p className="text-[10px] text-primary-600 uppercase font-bold">Avg. Protein</p>
                    <p className="text-xl font-black text-primary-900">{plan.nutritional_summary.avg_daily_protein}g</p>
                  </div>
                </div>
                <p className="text-[10px] text-primary-400 mt-3 italic">
                  {plan.nutritional_summary.note}
                </p>
              </div>
            )}

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

        {/* Meal Plan Feedback Section */}
        <div className="mt-12 bg-white rounded-xl shadow-sm border border-gray-200 p-8 max-w-3xl mx-auto">
          <div className="text-center mb-6">
            <h2 className="text-xl font-bold text-gray-900">How do you like this Meal Plan?</h2>
            <p className="text-gray-500">Your feedback helps us tailor future plans to your taste.</p>
          </div>

          <div className="flex flex-col items-center gap-6">
            <div className="flex items-center gap-2">
              {[1, 2, 3, 4, 5].map((star) => (
                <button
                  key={star}
                  onClick={() => setMealPlanFeedback({ ...mealPlanFeedback, rating: star })}
                  className="transition-transform hover:scale-110"
                >
                  <Star
                    size={40}
                    className={clsx(
                      "transition-colors",
                      (mealPlanFeedback.rating >= star) ? "text-yellow-400 fill-current" : "text-gray-200"
                    )}
                  />
                </button>
              ))}
            </div>

            <div className="w-full">
              <textarea
                placeholder="Any comments or suggestions for this plan? (e.g., 'Too many pasta dishes', 'Loved the variety!')"
                value={mealPlanFeedback.comment}
                onChange={(e) => setMealPlanFeedback({ ...mealPlanFeedback, comment: e.target.value })}
                className="w-full p-4 bg-gray-50 border border-gray-200 rounded-xl focus:ring-2 focus:ring-primary-500 focus:border-primary-500 outline-none transition-all h-32 resize-none"
              />
            </div>

            <button
              onClick={handleMealPlanFeedback}
              disabled={submittingFeedback || mealPlanFeedback.rating === 0}
              className="flex items-center gap-2 bg-primary-600 text-white px-8 py-3 rounded-xl font-bold hover:bg-primary-700 disabled:opacity-50 shadow-lg transition-all"
            >
              {submittingFeedback ? <RefreshCw className="w-5 h-5 animate-spin" /> : <Send className="w-5 h-5" />}
              <span>Submit Feedback</span>
            </button>
          </div>
        </div>
      </div>
    </div>
    </DndProvider>
  );
};

export default MealPlanPage;
