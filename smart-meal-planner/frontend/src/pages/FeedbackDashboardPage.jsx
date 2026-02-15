import React, { useEffect, useState } from 'react';
import api from '../services/api';
import { Star, MessageSquare, Filter, Calendar, BookOpen } from 'lucide-react';
import clsx from 'clsx';

const FeedbackDashboardPage = () => {
  const [feedback, setFeedback] = useState([]);
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('all'); // 'all', 'recipe', 'meal_plan'

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        const [feedbackData, summaryData] = await Promise.all([
          api.get('/feedback'),
          api.get('/feedback/summary')
        ]);
        setFeedback(feedbackData);
        setSummary(summaryData);
      } catch (error) {
        console.error("Failed to fetch feedback data", error);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  const filteredFeedback = feedback.filter(item => {
    if (filter === 'all') return true;
    if (filter === 'recipe') return item.recipe_id !== null;
    if (filter === 'meal_plan') return item.meal_plan_id !== null;
    return true;
  });

  if (loading) return <div className="p-8 text-center">Loading dashboard...</div>;

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-bold text-gray-900">Feedback Dashboard</h1>
        <p className="text-gray-500">Track your ratings and comments to improve AI recommendations.</p>
      </div>

      {summary && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-200">
            <p className="text-sm font-medium text-gray-500 uppercase tracking-wider">Total Feedback</p>
            <p className="text-3xl font-bold text-gray-900 mt-1">{summary.total_feedback_count}</p>
          </div>
          <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-200">
            <p className="text-sm font-medium text-gray-500 uppercase tracking-wider">Avg Recipe Rating</p>
            <div className="flex items-center mt-1">
              <p className="text-3xl font-bold text-gray-900 mr-2">{(summary.average_recipe_rating || 0).toFixed(1)}</p>
              <Star className="text-yellow-400 fill-current w-6 h-6" />
            </div>
          </div>
          <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-200">
            <p className="text-sm font-medium text-gray-500 uppercase tracking-wider">Avg Meal Plan Rating</p>
            <div className="flex items-center mt-1">
              <p className="text-3xl font-bold text-gray-900 mr-2">{(summary.average_meal_plan_rating || 0).toFixed(1)}</p>
              <Star className="text-yellow-400 fill-current w-6 h-6" />
            </div>
          </div>
        </div>
      )}

      <div className="flex items-center gap-4 border-b border-gray-200 pb-4">
        <button
          onClick={() => setFilter('all')}
          className={clsx(
            "px-4 py-2 text-sm font-medium rounded-lg transition-colors",
            filter === 'all' ? "bg-primary-100 text-primary-700" : "text-gray-500 hover:bg-gray-100"
          )}
        >
          All Feedback
        </button>
        <button
          onClick={() => setFilter('recipe')}
          className={clsx(
            "px-4 py-2 text-sm font-medium rounded-lg transition-colors",
            filter === 'recipe' ? "bg-primary-100 text-primary-700" : "text-gray-500 hover:bg-gray-100"
          )}
        >
          Recipes
        </button>
        <button
          onClick={() => setFilter('meal_plan')}
          className={clsx(
            "px-4 py-2 text-sm font-medium rounded-lg transition-colors",
            filter === 'meal_plan' ? "bg-primary-100 text-primary-700" : "text-gray-500 hover:bg-gray-100"
          )}
        >
          Meal Plans
        </button>
      </div>

      <div className="space-y-4">
        {filteredFeedback.length === 0 ? (
          <div className="bg-white p-12 text-center rounded-xl border border-dashed border-gray-300">
            <MessageSquare className="w-12 h-12 text-gray-300 mx-auto mb-4" />
            <p className="text-gray-500">No feedback found for this category.</p>
          </div>
        ) : (
          filteredFeedback.map((item) => (
            <div key={item.id} className="bg-white p-6 rounded-xl shadow-sm border border-gray-200">
              <div className="flex justify-between items-start mb-4">
                <div className="flex items-center gap-3">
                  <div className={clsx(
                    "p-2 rounded-lg",
                    item.recipe_id ? "bg-blue-50 text-blue-600" : "bg-purple-50 text-purple-600"
                  )}>
                    {item.recipe_id ? <BookOpen size={20} /> : <Calendar size={20} />}
                  </div>
                  <div>
                    <h3 className="font-bold text-gray-900">
                      {item.recipe_id ? `Recipe Feedback` : `Meal Plan Feedback`}
                    </h3>
                    <p className="text-xs text-gray-400">
                      {new Date(item.created_at).toLocaleDateString()}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-1">
                  {[...Array(5)].map((_, i) => (
                    <Star
                      key={i}
                      size={16}
                      className={clsx(
                        i < item.rating ? "text-yellow-400 fill-current" : "text-gray-200"
                      )}
                    />
                  ))}
                </div>
              </div>
              {item.comment && (
                <div className="bg-gray-50 p-4 rounded-lg text-gray-700 italic">
                  "{item.comment}"
                </div>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  );
};

export default FeedbackDashboardPage;
