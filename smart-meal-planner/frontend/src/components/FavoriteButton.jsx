import React, { useState } from 'react';
import { Heart } from 'lucide-react';
import { cn } from '../lib/utils';

const FavoriteButton = ({ isFavorited, onToggle }) => {
  const [localIsFavorited, setLocalIsFavorited] = useState(isFavorited);

  const handleToggle = () => {
    setLocalIsFavorited(!localIsFavorited);
    if (onToggle) {
      onToggle(!localIsFavorited);
    }
  };

  return (
    <button onClick={handleToggle} className="text-gray-400 hover:text-red-500">
      <Heart
        className={cn(
          'h-6 w-6',
          localIsFavorited && 'text-red-500 fill-red-500'
        )}
      />
    </button>
  );
};

export default FavoriteButton;
