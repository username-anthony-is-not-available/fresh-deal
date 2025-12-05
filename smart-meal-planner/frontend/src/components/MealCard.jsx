import React from 'react';
import { Clock, Users } from 'lucide-react';

const MealCard = ({ type, meal }) => {
  // Simple heuristic for image placeholder based on meal name
  const getEmoji = (name) => {
    if (name.toLowerCase().includes('salad')) return '🥗';
    if (name.toLowerCase().includes('pasta')) return '🍝';
    if (name.toLowerCase().includes('chicken')) return '🍗';
    if (name.toLowerCase().includes('beef')) return '🥩';
    if (name.toLowerCase().includes('egg')) return '🍳';
    if (name.toLowerCase().includes('toast')) return '🍞';
    return '🍽️';
  };

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4 hover:border-primary-300 transition-colors h-full">
      <div className="flex items-center gap-2 mb-2">
        <span className="text-xs font-semibold text-primary-600 bg-primary-50 px-2 py-0.5 rounded-full uppercase">
          {type}
        </span>
      </div>

      <h3 className="font-medium text-gray-900 mb-2 flex items-center gap-2">
        <span className="text-xl">{getEmoji(meal.name)}</span>
        {meal.name}
      </h3>

      <div className="text-sm text-gray-500 mb-3">
        <ul className="list-disc list-inside">
          {meal.ingredients.slice(0, 3).map((ing, idx) => (
             <li key={idx} className="truncate">{ing}</li>
          ))}
          {meal.ingredients.length > 3 && (
            <li className="list-none text-xs text-gray-400 pl-4">+ {meal.ingredients.length - 3} more</li>
          )}
        </ul>
      </div>

      {/* Mock Nutrition Badges */}
      <div className="flex gap-2 text-xs text-gray-500 mt-auto pt-2 border-t border-gray-100">
         <span title="Calories">🔥 ~500 kcal</span>
         <span title="Protein">💪 30g</span>
      </div>
    </div>
  );
};

export default MealCard;
