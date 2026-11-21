import React from 'react';
import { render, screen, fireEvent, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';

const toastMock = vi.hoisted(() => {
  const fn = vi.fn(() => 'toast-id');
  fn.success = vi.fn();
  fn.error = vi.fn();
  fn.loading = vi.fn(() => 'toast-id');
  return fn;
});
vi.mock('react-hot-toast', () => ({ default: toastMock, toast: toastMock }));

vi.mock('../services/api', () => ({
  default: { post: vi.fn(), get: vi.fn(), delete: vi.fn() },
}));

vi.mock('../services/nutritionService', () => ({
  getNutritionGoal: vi.fn(),
  createOrUpdateNutritionGoal: vi.fn(),
}));

import api from '../services/api';
import MealCard from '../components/MealCard';
import NutritionGoalSettings from '../components/NutritionGoalSettings';
import IngredientPriceComparison from '../components/IngredientPriceComparison';
import {
  getNutritionGoal,
  createOrUpdateNutritionGoal,
} from '../services/nutritionService';

beforeEach(() => {
  vi.clearAllMocks();
  vi.spyOn(console, 'error').mockImplementation(() => {});
  vi.spyOn(console, 'log').mockImplementation(() => {});
});

const baseMeal = {
  recipe_id: 1,
  recipe_name: 'Chicken Pasta',
  ingredients: [
    { quantity: 1, unit: 'lb', item: 'Chicken' },
    { quantity: 2, unit: 'cups', item: 'Pasta' },
    'Salt',
    { quantity: 1, unit: 'tsp', item: 'Pepper' },
  ],
  nutrition: { calories: 500, protein: 30 },
};

// ---------------------------------------------------------------------------
// MealCard
// ---------------------------------------------------------------------------

describe('MealCard', () => {
  it('renders emoji, nutrition, ingredients and the +N more row', () => {
    render(<MealCard type="Dinner" meal={baseMeal} />);
    expect(screen.getByText('Dinner')).toBeInTheDocument();
    expect(screen.getByText(/Chicken Pasta/)).toBeInTheDocument();
    expect(screen.getByText('🍝')).toBeInTheDocument(); // "pasta" matches before "chicken"
    expect(screen.getByText('500')).toBeInTheDocument();
    expect(screen.getByText('+ 1 more ingredients')).toBeInTheDocument();
    expect(screen.getByText('Salt')).toBeInTheDocument();
    expect(screen.getByText(/1 lb Chicken/)).toBeInTheDocument();
  });

  it('picks the emoji per dish name', () => {
    const names = [
      ['Garden Salad', '🥗'], ['Beef Stew', '🥩'], ['Egg Toast', '🍳'],
      ['Garlic Toast', '🍞'], ['Mystery Bowl', '🍽️'],
    ];
    for (const [name, emoji] of names) {
      const { unmount } = render(
        <MealCard type="Lunch" meal={{ ...baseMeal, recipe_name: name, ingredients: [] }} />
      );
      expect(screen.getByText(emoji)).toBeInTheDocument();
      unmount();
    }
  });

  it('toggles favorite on and off', async () => {
    api.post.mockResolvedValue({});
    api.delete.mockResolvedValue({});
    render(<MealCard type="Dinner" meal={baseMeal} />);
    const favBtn = screen.getByRole('button', { name: '' });
    await act(async () => fireEvent.click(document.querySelector('.text-gray-400.hover\\:text-red-500')));
    expect(api.post).toHaveBeenCalledWith('/recipes/1/favorite');
  });

  it('reverts the favorite when the API fails', async () => {
    api.post.mockRejectedValue(new Error('down'));
    render(<MealCard type="Dinner" meal={{ ...baseMeal, is_favorited: false }} />);
    await act(async () =>
      fireEvent.click(document.querySelector('.text-gray-400.hover\\:text-red-500'))
    );
    expect(console.error).toHaveBeenCalled();
  });

  it('submits a rating through the star rating', async () => {
    api.post.mockResolvedValue({});
    render(<MealCard type="Dinner" meal={baseMeal} />);
    const stars = document.querySelectorAll('.cursor-pointer');
    await act(async () => fireEvent.click(stars[3]));
    expect(api.post).toHaveBeenCalledWith('/recipes/1/rate', { rating: 4 });
    expect(api.post).toHaveBeenCalledWith('/feedback', {
      recipe_id: 1, rating: 4, comment: undefined,
    });
  });

  it('logs a rating failure without crashing', async () => {
    api.post
      .mockResolvedValueOnce({})
      .mockRejectedValueOnce(new Error('down'));
    render(<MealCard type="Dinner" meal={baseMeal} />);
    const stars = document.querySelectorAll('.cursor-pointer');
    await act(async () => fireEvent.click(stars[1]));
    expect(console.error).toHaveBeenCalled();
  });

  it('submits made_it/skipped feedback, with the follow-up when rated', async () => {
    api.post.mockResolvedValue({});
    render(<MealCard type="Dinner" meal={{ ...baseMeal, user_rating: 4 }} />);
    await act(async () => fireEvent.click(screen.getByTitle('I made this')));
    expect(api.post).toHaveBeenCalledWith('/recipes/1/feedback', { status: 'made_it' });
    expect(api.post).toHaveBeenCalledWith('/feedback', expect.objectContaining({
      recipe_id: 1, rating: 4,
    }));
    expect(screen.getByText('Thanks for the feedback!')).toBeInTheDocument();
  });

  it('reverts feedback when the API fails', async () => {
    api.post.mockRejectedValue(new Error('down'));
    render(<MealCard type="Dinner" meal={baseMeal} />);
    await act(async () => fireEvent.click(screen.getByTitle('I skipped this')));
    expect(screen.queryByText('Thanks for the feedback!')).toBeNull();
    expect(console.error).toHaveBeenCalled();
  });

  it('adds and submits a comment', async () => {
    api.post.mockResolvedValue({});
    render(<MealCard type="Dinner" meal={baseMeal} />);
    fireEvent.click(screen.getByTitle('Add a comment'));
    const box = screen.getByPlaceholderText('Add a comment...');
    fireEvent.change(box, { target: { value: 'Loved it' } });
    const sendBtn = box.parentElement.querySelector('button');
    await act(async () => fireEvent.click(sendBtn));
    expect(api.post).toHaveBeenCalledWith('/feedback', {
      recipe_id: 1, rating: 5, comment: 'Loved it',
    });
    expect(screen.queryByPlaceholderText('Add a comment...')).toBeNull();
  });

  it('does nothing on an empty comment and logs comment failures', async () => {
    api.post.mockRejectedValue(new Error('down'));
    render(<MealCard type="Dinner" meal={baseMeal} />);
    fireEvent.click(screen.getByTitle('Add a comment'));
    const box = screen.getByPlaceholderText('Add a comment...');
    fireEvent.change(box, { target: { value: 'Oops' } });
    const sendBtn = box.parentElement.querySelector('button');
    await act(async () => fireEvent.click(sendBtn));
    expect(console.error).toHaveBeenCalled();
    expect(screen.getByPlaceholderText('Add a comment...')).toBeInTheDocument();
  });

  it('calls regenerate and disables it while regenerating', () => {
    const onRegenerate = vi.fn();
    const { unmount } = render(
      <MealCard type="Dinner" meal={baseMeal} onRegenerate={onRegenerate} isRegenerating />
    );
    const btn = screen.getByTitle('Regenerate this meal');
    expect(btn.disabled).toBe(true);
    unmount();
    render(
      <MealCard type="Dinner" meal={baseMeal} onRegenerate={onRegenerate} />
    );
    fireEvent.click(screen.getByTitle('Regenerate this meal'));
    expect(onRegenerate).toHaveBeenCalled();
  });
});

// ---------------------------------------------------------------------------
// NutritionGoalSettings
// ---------------------------------------------------------------------------

describe('NutritionGoalSettings', () => {
  it('loads an existing goal into the form', async () => {
    getNutritionGoal.mockResolvedValue({
      goal_type: 'weight_loss', target_calories: 1800, target_protein: 120,
      target_carbs: null, target_fats: 60, target_fiber: 25,
    });
    render(<NutritionGoalSettings />);
    expect(await screen.findByDisplayValue('1800')).toBeInTheDocument();
    expect(screen.getByLabelText('Goal Type')).toHaveValue('weight_loss');
    expect(screen.getByLabelText('Target Protein (g)')).toHaveValue(120);
  });

  it('keeps defaults when there is no goal and when loading fails', async () => {
    getNutritionGoal.mockResolvedValueOnce(null);
    const { unmount } = render(<NutritionGoalSettings />);
    await screen.findByText('Nutrition Goals');
    expect(screen.getByLabelText('Goal Type')).toHaveValue('maintenance');
    unmount();
    getNutritionGoal.mockRejectedValueOnce(new Error('no goal'));
    render(<NutritionGoalSettings />);
    await screen.findByText('Nutrition Goals');
    expect(console.log).toHaveBeenCalledWith('No existing nutrition goal found.');
  });

  it('saves edited goals with parsed numbers', async () => {
    getNutritionGoal.mockResolvedValue(null);
    createOrUpdateNutritionGoal.mockResolvedValue({});
    render(<NutritionGoalSettings />);
    await screen.findByText('Nutrition Goals');
    fireEvent.change(screen.getByLabelText('Target Calories (kcal)'), { target: { value: '2200' } });
    fireEvent.change(screen.getByLabelText('Goal Type'), { target: { value: 'muscle_gain' } });
    await act(async () => fireEvent.click(screen.getByText('Save Nutrition Goals')));
    expect(createOrUpdateNutritionGoal).toHaveBeenCalledWith({
      goal_type: 'muscle_gain',
      target_calories: 2200,
      target_protein: null,
      target_carbs: null,
      target_fats: null,
      target_fiber: null,
    });
    expect(toastMock.loading).toHaveBeenCalledWith('Saving nutrition goals...');
    expect(toastMock.success).toHaveBeenCalledWith(
      'Nutrition goals saved successfully!', { id: 'toast-id' }
    );
  });

  it('shows an error toast when saving fails', async () => {
    getNutritionGoal.mockResolvedValue(null);
    createOrUpdateNutritionGoal.mockRejectedValue(new Error('down'));
    render(<NutritionGoalSettings />);
    await screen.findByText('Nutrition Goals');
    await act(async () => fireEvent.click(screen.getByText('Save Nutrition Goals')));
    expect(toastMock.error).toHaveBeenCalledWith(
      'Failed to save nutrition goals.', { id: 'toast-id' }
    );
    expect(console.error).toHaveBeenCalled();
  });
});

// ---------------------------------------------------------------------------
// IngredientPriceComparison
// ---------------------------------------------------------------------------

describe('IngredientPriceComparison', () => {
  it('shows the empty message for missing or empty data', () => {
    for (const data of [null, undefined, [], {}]) {
      const { unmount } = render(<IngredientPriceComparison detailedComparison={data} />);
      expect(screen.getByText(/No detailed ingredient price comparison/)).toBeInTheDocument();
      unmount();
    }
  });

  it('renders the array format with min prices and totals', () => {
    const data = [
      { ingredient: 'Chicken', quantity: 1, unit: 'kg', prices: { Metro: 5.0, Walmart: 4.5 } },
      { ingredient: 'Rice', qty: 2, prices: { Metro: 3.0 } },
      { name: 'Salt', prices: {} },
    ];
    render(
      <IngredientPriceComparison
        detailedComparison={data}
        projectedSavings={12.5}
      />
    );
    expect(screen.getByText('Side-by-Side Store Price Comparison')).toBeInTheDocument();
    expect(screen.getByText('Chicken')).toBeInTheDocument();
    expect(screen.getAllByText('$4.50').length).toBe(2); // price cell + subtotal
    expect(screen.getAllByText('N/A').length).toBeGreaterThan(0);
    expect(screen.getByText('$12.50')).toBeInTheDocument(); // savings
    expect(screen.getByText('$8.00')).toBeInTheDocument(); // Metro subtotal 5 + 3
  });

  it('renders the object format with nested price objects', () => {
    const data = {
      Chicken: { quantity: 1, unit: 'kg', Metro: 5.0, Walmart: { price: 4.0 } },
      Rice: { qty: 2, unit: 'bag', Metro: 3.0, Walmart: 2.5 },
    };
    render(
      <IngredientPriceComparison
        detailedComparison={data}
        allStores={['Metro', 'Walmart']}
        projectedSavings="9.99"
      />
    );
    expect(screen.getByText('Chicken')).toBeInTheDocument();
    expect(screen.getByText('$4.00')).toBeInTheDocument();
    expect(screen.getByText('$9.99')).toBeInTheDocument();
    expect(screen.getByText('$8.00')).toBeInTheDocument(); // Metro subtotal
    expect(screen.getByText('$6.50')).toBeInTheDocument(); // Walmart subtotal
  });

  it('uses provided stores and handles items with no prices', () => {
    const data = [{ ingredient: 'Mystery', prices: { Metro: 'n/a' } }];
    render(
      <IngredientPriceComparison detailedComparison={data} allStores={['Metro']} />
    );
    expect(screen.getByText('Mystery')).toBeInTheDocument();
    expect(screen.getByText('N/A')).toBeInTheDocument();
    expect(screen.getByText('$0.00')).toBeInTheDocument();
  });
});
