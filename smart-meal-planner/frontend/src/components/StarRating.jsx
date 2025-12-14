import React from 'react';
import { Star } from 'lucide-react';
import { cn } from '../lib/utils'; // Assuming a utility for classnames exists

const StarRating = ({ rating = 0, onRate, readOnly = false }) => {
  const stars = Array(5).fill(0);

  return (
    <div className="flex items-center gap-1">
      {stars.map((_, i) => {
        const ratingValue = i + 1;
        return (
          <Star
            key={i}
            className={cn(
              'h-5 w-5',
              ratingValue <= rating ? 'text-yellow-400 fill-yellow-400' : 'text-gray-300',
              !readOnly && 'cursor-pointer hover:text-yellow-500'
            )}
            onClick={() => !readOnly && onRate && onRate(ratingValue)}
          />
        );
      })}
    </div>
  );
};

export default StarRating;
