import React, { useState } from "react";
import StarRating from "./StarRating";
import FavoriteButton from "./FavoriteButton";
import api from "../services/api";
import clsx from "clsx";
import { Check, X, RefreshCw, MessageSquare, Send } from "lucide-react";

const MealCard = ({ type, meal, onRegenerate, isRegenerating }) => {
  const [rating, setRating] = useState(meal.user_rating || 0);
  const [isFavorited, setIsFavorited] = useState(meal.is_favorited || false);
  const [feedbackStatus, setFeedbackStatus] = useState(null); // 'made_it' or 'skipped'
  const [comment, setComment] = useState("");
  const [showComment, setShowComment] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleRate = async (newRating) => {
    setRating(newRating);
    try {
      await api.post("/feedback", {
        recipe_id: meal.recipe_id,
        rating: newRating,
        comment: comment || undefined
      });
    } catch (error) {
      console.error("Failed to submit rating/feedback", error);
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
      // Send both legacy feedback and new unified feedback if rating exists
      await api.post(`/recipes/${meal.recipe_id}/feedback`, { status });

      if (rating > 0) {
        await api.post("/feedback", {
          recipe_id: meal.recipe_id,
          rating: rating,
          comment: `Status: ${status}. ${comment}`.trim()
        });
      }
    } catch (error) {
      console.error("Failed to submit feedback:", error);
      setFeedbackStatus(originalStatus); // Revert on error
    }
  };

  const handleCommentSubmit = async () => {
    if (!comment.trim()) return;
    setIsSubmitting(true);
    try {
      await api.post("/feedback", {
        recipe_id: meal.recipe_id,
        rating: rating || 5, // Default to 5 if not rated but commented
        comment: comment
      });
      setShowComment(false);
    } catch (error) {
      console.error("Failed to submit comment", error);
    } finally {
      setIsSubmitting(false);
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
    <div className="relative bg-white rounded-lg border border-gray-200 p-4 hover:border-primary-300 transition-colors h-full flex flex-col group shadow-sm sm:shadow-none">
       <div className="absolute top-2 right-2 flex items-center gap-2 sm:gap-1 opacity-100 sm:opacity-0 sm:group-hover:opacity-100 transition-all">
        {onRegenerate && (
            <button
              onClick={onRegenerate}
              disabled={isRegenerating}
              className="p-2 sm:p-1.5 rounded-full bg-white/90 sm:bg-gray-100 text-gray-600 hover:bg-gray-200 disabled:opacity-50 shadow-md sm:shadow-none border border-gray-100 sm:border-none"
              title="Regenerate this meal"
            >
              <RefreshCw size={18} className={isRegenerating ? "animate-spin" : "sm:w-[14px] sm:h-[14px]"} />
            </button>
        )}
        <div className="bg-white/90 sm:bg-transparent p-1 sm:p-0 rounded-full shadow-md sm:shadow-none border border-gray-100 sm:border-none">
          <FavoriteButton
            isFavorited={isFavorited}
            onToggle={handleToggleFavorite}
          />
        </div>
       </div>
      <div className="flex justify-between items-start mb-2">
        <span className="text-xs font-semibold text-primary-600 bg-primary-50 px-2 py-0.5 rounded-full uppercase">
          {type}
        </span>
      </div>

      <h3 className="font-bold text-gray-900 mb-2 flex items-center gap-2 leading-tight">
        <span className="text-2xl sm:text-xl">{getEmoji(meal.recipe_name)}</span>
        <span className="text-base sm:text-sm">{meal.recipe_name}</span>
      </h3>

      {meal.nutrition && (
        <div className="flex gap-3 mb-3 text-[10px] uppercase font-bold tracking-wider text-gray-400">
          <div className="flex items-center gap-1">
            <span className="text-primary-600">{meal.nutrition.calories || 0}</span> kcal
          </div>
          <div className="flex items-center gap-1">
            <span className="text-primary-600">{meal.nutrition.protein || 0}g</span> protein
          </div>
        </div>
      )}

      <div className="text-sm text-gray-500 mb-4 flex-grow">
        <ul className="space-y-1">
          {meal.ingredients.slice(0, 3).map((ing, idx) => (
            <li key={idx} className="truncate flex items-center gap-2">
              <span className="w-1 h-1 bg-gray-300 rounded-full flex-shrink-0" />
              {typeof ing === "string"
                ? ing
                : `${ing.quantity || ""} ${ing.unit || ""} ${ing.item}`.trim()}
            </li>
          ))}
          {meal.ingredients.length > 3 && (
            <li className="list-none text-xs text-gray-400 pl-3 italic">
              + {meal.ingredients.length - 3} more ingredients
            </li>
          )}
        </ul>
      </div>

      <div className="mt-auto pt-3 border-t border-gray-100">
        {showComment && (
          <div className="mb-3 animate-in fade-in slide-in-from-bottom-2">
            <div className="relative">
              <textarea
                autoFocus
                value={comment}
                onChange={(e) => setComment(e.target.value)}
                placeholder="Add a comment..."
                className="w-full p-2 text-xs bg-gray-50 border border-gray-200 rounded-lg focus:ring-1 focus:ring-primary-500 outline-none resize-none h-16"
              />
              <button
                onClick={handleCommentSubmit}
                disabled={isSubmitting || !comment.trim()}
                className="absolute bottom-2 right-2 p-1 bg-primary-600 text-white rounded-md hover:bg-primary-700 disabled:opacity-50"
              >
                {isSubmitting ? <RefreshCw size={12} className="animate-spin" /> : <Send size={12} />}
              </button>
            </div>
          </div>
        )}
        <div className="flex justify-between items-center gap-2">
          <div className="flex items-center gap-1">
            <StarRating
              recipeId={meal.recipe_id}
              initialRating={rating}
              onRatingSubmit={handleRate}
            />
            <button
              onClick={() => setShowComment(!showComment)}
              className={clsx(
                "p-1 rounded-md transition-colors",
                showComment || comment ? "text-primary-600 bg-primary-50" : "text-gray-400 hover:bg-gray-100"
              )}
              title="Add a comment"
            >
              <MessageSquare size={16} />
            </button>
          </div>
          {feedbackStatus ? (
            <div className="text-sm text-gray-600 font-medium">
              Thanks for the feedback!
            </div>
          ) : (
            <div className="flex items-center gap-2">
              <button
                onClick={() => handleFeedback("made_it")}
                className="p-2.5 sm:p-1.5 rounded-full bg-green-50 text-green-700 hover:bg-green-100 border border-green-100 sm:border-none shadow-sm sm:shadow-none transition-colors"
                title="I made this"
              >
                <Check size={20} className="sm:w-4 sm:h-4" />
              </button>
              <button
                onClick={() => handleFeedback("skipped")}
                className="p-2.5 sm:p-1.5 rounded-full bg-red-50 text-red-700 hover:bg-red-100 border border-red-100 sm:border-none shadow-sm sm:shadow-none transition-colors"
                title="I skipped this"
              >
                <X size={20} className="sm:w-4 sm:h-4" />
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default MealCard;
