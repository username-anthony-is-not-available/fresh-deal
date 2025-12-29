import React from 'react';
import { useDrag } from 'react-dnd';
import MealCard from './MealCard';

const DraggableMealCard = ({ meal, day, type, onRegenerate, isRegenerating }) => {
  const [{ isDragging }, drag] = useDrag(() => ({
    type: 'meal',
    item: { meal, day, type },
    collect: (monitor) => ({
      isDragging: !!monitor.isDragging(),
    }),
  }));

  return (
    <div
      ref={drag}
      style={{
        opacity: isDragging ? 0.5 : 1,
        cursor: 'move',
      }}
    >
      <MealCard meal={meal} type={type} onRegenerate={onRegenerate} isRegenerating={isRegenerating} />
    </div>
  );
};

export default DraggableMealCard;
