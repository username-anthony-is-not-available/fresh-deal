import React, { useState } from "react";
import StarRating from "./StarRating";
import FavoriteButton from "./FavoriteButton";
import api from "../services/api";
import { Check, X } from "lucide-react";

const MealCard = ({ type, meal }) => {
  const [rating, setRating] = useState(meal.user_rating || 0);
  const [isFavorited, setIsFavorited] = useState(meal.is_favorited || false);
  const [feedbackStatus, setFeedbackStatus] = useState(null); // 'made_it' or 'skipped'

  const handleRate = async (newRating) => {
    setRating(newRating);
    try {
      await api.post(`/recipes/${meal.recipe_id}/rate`, { rating: newRating });
    } catch (error) {
      console.error("Failed to rate recipe:", error);
      // Revert rating on error
      setRating(rating);
    }
  };

  const handleToggleFavorite = async () => {
    const newIsFavorited = !isFavorited;
    setIsFavorited(newIsFavorited);
    try {
      if (newIsFavorited) {
        await api.post(`/recipes/${meal.recipe_id}/favorite`);
      } else {
        await api.delete(`/recipes/${meal.recipe_id}/favorite`);
      }
    } catch (error) {
      console.error("Failed to toggle favorite:", error);
      // Revert favorite status on error
      setIsFavorited(!newIsFavorited);
    }
  };

  const handleFeedback = async (status) => {
    const originalStatus = feedbackStatus;
    setFeedbackStatus(status);
    try {
      await api.post(`/recipes/${meal.recipe_id}/feedback`, { status });
    } catch (error) {
      console.error("Failed to submit feedback:", error);
      setFeedbackStatus(originalStatus); // Revert on error
    }
  };

  const getEmoji = (name) => {
    if (name.toLowerCase().includes("salad")) return "🥗";
    if (name.toLowerCase().includes("pasta")) return "🍝";
    if (name.toLowerCase().includes("chicken")) return "🍗";
    if (name.toLowerCase().includes("beef")) return "🥩";
    if (name.toLowerCase().includes("egg")) return "🍳";
    if (name.toLowerCase().includes("toast")) return "🍞";
    return "🍽️";
  };

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4 hover:border-primary-300 transition-colors h-full flex flex-col">
      <div className="flex justify-between items-start mb-2">
        <span className="text-xs font-semibold text-primary-600 bg-primary-50 px-2 py-0.5 rounded-full uppercase">
          {type}
        </span>
        <FavoriteButton
          isFavorited={isFavorited}
          onToggle={handleToggleFavorite}
        />
      </div>

      <h3 className="font-medium text-gray-900 mb-2 flex items-center gap-2">
        <span className="text-xl">{getEmoji(meal.recipe_name)}</span>
        {meal.recipe_name}
      </h3>

      <div className="text-sm text-gray-500 mb-3">
        <ul className="list-disc list-inside">
          {meal.ingredients.slice(0, 3).map((ing, idx) => (
            <li key={idx} className="truncate">
              {typeof ing === "string" ? ing : ing.item}
            </li>
          ))}
          {meal.ingredients.length > 3 && (
            <li className="list-none text-xs text-gray-400 pl-4">
              + {meal.ingredients.length - 3} more
            </li>
          )}
        </ul>
      </div>

      <div className="mt-auto pt-2 border-t border-gray-100">
        <div className="flex justify-between items-center">
          <StarRating rating={rating} onRate={handleRate} />
          {feedbackStatus ? (
            <div className="text-sm text-gray-600 font-medium">
              Thanks for the feedback!
            </div>
          ) : (
            <div className="flex items-center gap-2">
              <button
                onClick={() => handleFeedback("made_it")}
                className="p-1.5 rounded-full bg-green-100 text-green-700 hover:bg-green-200"
                title="I made this"
              >
                <Check size={16} />
              </button>
              <button
                onClick={() => handleFeedback("skipped")}
                className="p-1.5 rounded-full bg-red-100 text-red-700 hover:bg-red-200"
                title="I skipped this"
              >
                <X size={16} />
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default MealCard;
