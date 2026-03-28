import React, { useState } from 'react';
import { Star } from 'lucide-react';
import { cn } from '../lib/utils';
import api from '../services/api';
import { toast } from 'react-hot-toast';

const StarRating = ({ recipeId, initialRating = 0, onRatingSubmit }) => {
  const [rating, setRating] = useState(initialRating);
  const [hoverRating, setHoverRating] = useState(0);

  const handleRating = async (newRating) => {
    setRating(newRating);
    try {
      await api.post(`/recipes/${recipeId}/rate`, { rating: newRating });
      toast.success('Rating submitted!');
      if (onRatingSubmit) {
        onRatingSubmit(newRating);
      }
    } catch (error) {
      toast.error('Failed to submit rating.');
      console.error('Rating submission error:', error);
      // Revert to the initial rating on failure
      setRating(initialRating);
    }
  };

  return (
    <div className="flex items-center">
      {[1, 2, 3, 4, 5].map((star) => (
        <Star
          key={star}
          className={cn(
            'h-6 w-6 cursor-pointer',
            (hoverRating || rating) >= star ? 'text-yellow-400 fill-yellow-400' : 'text-gray-300 dark:text-gray-600'
          )}
          onMouseEnter={() => setHoverRating(star)}
          onMouseLeave={() => setHoverRating(0)}
          onClick={() => handleRating(star)}
        />
      ))}
    </div>
  );
};

export default StarRating;
