import React from 'react';
import { render, screen } from '@testing-library/react';
import MealCard from '../components/MealCard';
import { describe, it, expect } from 'vitest';

describe('MealCard', () => {
  it('renders meal name and type', () => {
    const meal = {
      recipe_id: 1,
      recipe_name: 'Test Chicken Pasta',
      ingredients: [{ item: 'Chicken' }, { item: 'Pasta' }]
    };
    render(<MealCard type="Dinner" meal={meal} />);

    expect(screen.getByText('Dinner')).toBeInTheDocument();
    expect(screen.getByText(/Test Chicken Pasta/)).toBeInTheDocument();
    expect(screen.getByText('Chicken')).toBeInTheDocument();
  });

  it('renders ingredients correctly when they are strings', () => {
    const meal = {
      recipe_id: 2,
      recipe_name: 'Simple Salad',
      ingredients: ['Lettuce', 'Tomato']
    };
    render(<MealCard type="Lunch" meal={meal} />);

    expect(screen.getByText('Lettuce')).toBeInTheDocument();
  });

  it('renders nutrition information when available', () => {
    const meal = {
      recipe_id: 3,
      recipe_name: 'Nutritious Meal',
      ingredients: ['Ing 1'],
      nutrition: {
        calories: 500,
        protein: 30
      }
    };
    render(<MealCard type="Dinner" meal={meal} />);

    expect(screen.getByText('500')).toBeInTheDocument();
    expect(screen.getByText(/kcal/)).toBeInTheDocument();
    expect(screen.getByText('30g')).toBeInTheDocument();
    expect(screen.getByText(/protein/)).toBeInTheDocument();
  });
});
