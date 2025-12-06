import React from 'react';
import { render, screen } from '@testing-library/react';
import MealCard from '../components/MealCard';
import { describe, it, expect } from 'vitest';

describe('MealCard', () => {
  it('renders meal name and type', () => {
    const meal = {
      name: 'Test Chicken Pasta',
      ingredients: [{ item: 'Chicken' }, { item: 'Pasta' }]
    };
    render(<MealCard type="Dinner" meal={meal} />);

    expect(screen.getByText('Dinner')).toBeInTheDocument();
    expect(screen.getByText(/Test Chicken Pasta/)).toBeInTheDocument();
    expect(screen.getByText('Chicken')).toBeInTheDocument();
  });

  it('renders ingredients correctly when they are strings', () => {
    const meal = {
      name: 'Simple Salad',
      ingredients: ['Lettuce', 'Tomato']
    };
    render(<MealCard type="Lunch" meal={meal} />);

    expect(screen.getByText('Lettuce')).toBeInTheDocument();
  });
});
