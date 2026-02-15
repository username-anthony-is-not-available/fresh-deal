import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import MealPlanPage from '../pages/MealPlanPage';
import api from '../services/api';
import { vi, describe, it, expect, beforeEach } from 'vitest';

// Mock the API service
vi.mock('../services/api');

// Mock react-dnd as it depends on browser environment that might be incomplete in JSDOM
vi.mock('react-dnd', () => ({
  DndProvider: ({ children }) => <div>{children}</div>,
  useDrag: () => [{ isDragging: false }, vi.fn()],
  useDrop: () => [{ isOver: false }, vi.fn()],
}));

vi.mock('react-dnd-html5-backend', () => ({
  HTML5Backend: {},
}));

const mockPlan = {
  meal_plan: [
    {
      day: 1,
      day_name: 'Monday',
      date: '2023-12-04',
      meals: [
        {
          recipe_id: 1,
          recipe_name: 'Chicken Curry',
          type: 'Dinner',
          ingredients: [{ item: 'Chicken' }, { item: 'Curry Paste' }]
        },
        {
          recipe_id: 2,
          recipe_name: 'Beef Tacos',
          type: 'Lunch',
          ingredients: [{ item: 'Ground Beef' }, { item: 'Tortillas' }]
        }
      ]
    },
    {
      day: 2,
      day_name: 'Tuesday',
      date: '2023-12-05',
      meals: [
        {
          recipe_id: 3,
          recipe_name: 'Pasta Marinara',
          type: 'Dinner',
          ingredients: [{ item: 'Pasta' }, { item: 'Tomato Sauce' }]
        }
      ]
    }
  ],
  shopping_summary: { estimated_savings: 10 }
};

describe('MealPlanPage Filter', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.get.mockImplementation((url) => {
      if (url.includes('/latest')) return Promise.resolve(mockPlan);
      if (url.includes('/users/')) return Promise.resolve({ dietary_preferences: [] });
      return Promise.resolve({});
    });
    // Mock localStorage
    Storage.prototype.getItem = vi.fn(() => '1');
  });

  it('renders all meals initially', async () => {
    render(<MealPlanPage />);
    await waitFor(() => {
      expect(screen.getByText('Chicken Curry')).toBeInTheDocument();
      expect(screen.getByText('Beef Tacos')).toBeInTheDocument();
      expect(screen.getByText('Pasta Marinara')).toBeInTheDocument();
    });
  });

  it('filters meals by recipe name', async () => {
    render(<MealPlanPage />);
    await waitFor(() => screen.getByText('Chicken Curry'));

    const searchInput = screen.getByPlaceholderText(/Search recipes or ingredients/i);
    fireEvent.change(searchInput, { target: { value: 'chicken' } });

    expect(screen.getByText('Chicken Curry')).toBeInTheDocument();
    expect(screen.queryByText('Beef Tacos')).not.toBeInTheDocument();
    expect(screen.queryByText('Pasta Marinara')).not.toBeInTheDocument();
  });

  it('filters meals by ingredient', async () => {
    render(<MealPlanPage />);
    await waitFor(() => screen.getByText('Beef Tacos'));

    const searchInput = screen.getByPlaceholderText(/Search recipes or ingredients/i);
    fireEvent.change(searchInput, { target: { value: 'tortillas' } });

    expect(screen.getByText('Beef Tacos')).toBeInTheDocument();
    expect(screen.queryByText('Chicken Curry')).not.toBeInTheDocument();
  });

  it('updates search when quick filter chip is clicked', async () => {
    render(<MealPlanPage />);
    await waitFor(() => screen.getByText('Chicken Curry'));

    const chickenChip = screen.getByRole('button', { name: /Chicken/i });
    fireEvent.click(chickenChip);

    expect(screen.getByText('Chicken Curry')).toBeInTheDocument();
    expect(screen.queryByText('Beef Tacos')).not.toBeInTheDocument();

    // Toggle off
    fireEvent.click(chickenChip);
    await waitFor(() => {
        expect(screen.getByText('Beef Tacos')).toBeInTheDocument();
    });
  });

  it('shows no results message when no matches found', async () => {
    render(<MealPlanPage />);
    await waitFor(() => screen.getByText('Chicken Curry'));

    const searchInput = screen.getByPlaceholderText(/Search recipes or ingredients/i);
    fireEvent.change(searchInput, { target: { value: 'nonexistent' } });

    expect(screen.getByText('No matching meals found')).toBeInTheDocument();
  });
});
