import React from 'react';
import { useDrop } from 'react-dnd';

const MealSlot = ({ day, type, onDrop, children }) => {
  const [{ isOver }, drop] = useDrop(() => ({
    accept: 'meal',
    drop: (item) => onDrop(item, { day, type }),
    collect: (monitor) => ({
      isOver: !!monitor.isOver(),
    }),
  }));

  return (
    <div
      ref={drop}
      style={{
        backgroundColor: isOver ? '#f0f9ff' : 'transparent',
        border: isOver ? '2px dashed #0284c7' : '2px dashed transparent',
        borderRadius: '8px',
        minHeight: '100px',
        transition: 'background-color 0.2s, border 0.2s',
      }}
    >
      {children}
    </div>
  );
};

export default MealSlot;
