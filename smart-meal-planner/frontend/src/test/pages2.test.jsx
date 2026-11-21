import React from 'react';
import { render, screen, fireEvent, act, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MemoryRouter, Routes, Route } from 'react-router-dom';

vi.mock('../services/api', () => ({
  default: { post: vi.fn(), get: vi.fn(), delete: vi.fn() },
}));
vi.mock('../services/pantryService', () => ({
  default: {
    getIngredients: vi.fn(),
    addIngredients: vi.fn(),
    deleteIngredient: vi.fn(),
    consumeLatestPlan: vi.fn(),
  },
}));
vi.mock('../utils/toast', () => ({
  showSuccessToast: vi.fn(),
  showErrorToast: vi.fn(),
}));
const toastMock = vi.hoisted(() => {
  const fn = vi.fn();
  fn.success = vi.fn();
  fn.error = vi.fn();
  return fn;
});
vi.mock('react-hot-toast', () => ({ default: toastMock, toast: toastMock }));

import api from '../services/api';
import pantryService from '../services/pantryService';
import { showSuccessToast, showErrorToast } from '../utils/toast';
import FavoritesPage from '../pages/FavoritesPage';
import RecipesPage from '../pages/RecipesPage';
import RecipeDetailPage from '../pages/RecipeDetailPage';
import PantryPage from '../pages/PantryPage';
import ShoppingListPage from '../pages/ShoppingListPage';

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
  vi.spyOn(console, 'error').mockImplementation(() => {});
  vi.spyOn(console, 'warn').mockImplementation(() => {});
});

const recipe = (overrides = {}) => ({
  id: 1,
  name: 'Chicken Pasta',
  cuisine: 'Italian',
  average_rating: 4.5,
  servings: 4,
  meal_type: 'Dinner',
  ingredients: [
    { quantity: 2, unit: 'cups', item: 'Pasta' },
    { quantity: 1, unit: 'lb', item: 'Chicken' },
    'Salt',
  ],
  substitutions: { Chicken: ['Turkey', 'Tofu'] },
  ...overrides,
});

// ---------------------------------------------------------------------------
// FavoritesPage
// ---------------------------------------------------------------------------

describe('FavoritesPage', () => {
  it('renders favorite recipes as meal cards', async () => {
    api.get.mockResolvedValue([recipe()]);
    render(<FavoritesPage />);
    expect(screen.getByText('Loading...')).toBeInTheDocument();
    expect(await screen.findByText('My Favorite Recipes')).toBeInTheDocument();
    expect(screen.getByText(/Chicken Pasta/)).toBeInTheDocument();
  });

  it('unwraps a { data } response and shows the empty state', async () => {
    api.get.mockResolvedValue({ data: [] });
    render(<FavoritesPage />);
    expect(await screen.findByText("You haven't favorited any recipes yet.")).toBeInTheDocument();
  });

  it('shows an error when fetching fails', async () => {
    api.get.mockRejectedValue(new Error('down'));
    render(<FavoritesPage />);
    expect(await screen.findByText('Failed to fetch favorites.')).toBeInTheDocument();
    expect(console.error).toHaveBeenCalled();
  });
});

// ---------------------------------------------------------------------------
// RecipesPage
// ---------------------------------------------------------------------------

describe('RecipesPage', () => {
  it('loads recipes and top-rated recipes', async () => {
    api.get.mockImplementation((url) =>
      url === '/recipes/top-rated'
        ? Promise.resolve([recipe({ id: 9, name: 'Top Soup', average_rating: 5.0 })])
        : Promise.resolve([recipe()])
    );
    render(
      <MemoryRouter><RecipesPage /></MemoryRouter>
    );
    expect(screen.getByText('Loading recipes...')).toBeInTheDocument();
    expect(await screen.findByText('Top-Rated Recipes')).toBeInTheDocument();
    expect(screen.getByText('Top Soup')).toBeInTheDocument();
    expect(screen.getByText('Found 1 recipes')).toBeInTheDocument();
    expect(screen.getByText('5.0')).toBeInTheDocument();
  });

  it('searches with filters', async () => {
    api.get.mockImplementation((url) =>
      url === '/recipes/top-rated' ? Promise.resolve([]) : Promise.resolve([recipe()])
    );
    render(<MemoryRouter><RecipesPage /></MemoryRouter>);
    await screen.findByText('All Recipes');
    fireEvent.change(screen.getByPlaceholderText('Search recipes...'), {
      target: { value: 'pasta' },
    });
    const selects = document.querySelectorAll('select');
    fireEvent.change(selects[0], { target: { value: 'Italian' } });
    fireEvent.change(screen.getByPlaceholderText('Prep time (min)'), {
      target: { value: '30' },
    });
    fireEvent.click(screen.getByText('Filter'));
    await waitFor(() =>
      expect(api.get).toHaveBeenCalledWith(
        expect.stringContaining('search=pasta')
      )
    );
    expect(api.get.mock.calls.at(-1)[0]).toContain('cuisine=Italian');
    expect(api.get.mock.calls.at(-1)[0]).toContain('prep_time=30');
  });

  it('shows the empty state and warns on fetch failures', async () => {
    api.get.mockImplementation((url) =>
      url === '/recipes/top-rated'
        ? Promise.reject(new Error('down'))
        : Promise.resolve([])
    );
    render(<MemoryRouter><RecipesPage /></MemoryRouter>);
    expect(await screen.findByText('No recipes found.')).toBeInTheDocument();
    expect(console.warn).toHaveBeenCalled();
  });

  it('warns when the main list fails', async () => {
    api.get.mockImplementation((url) =>
      url === '/recipes/top-rated'
        ? Promise.resolve([])
        : Promise.reject(new Error('down'))
    );
    render(<MemoryRouter><RecipesPage /></MemoryRouter>);
    expect(await screen.findByText('No recipes found.')).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// RecipeDetailPage
// ---------------------------------------------------------------------------

describe('RecipeDetailPage', () => {
  const renderDetail = () =>
    render(
      <MemoryRouter initialEntries={['/recipes/5']}>
        <Routes>
          <Route path="/recipes/:id" element={<RecipeDetailPage />} />
        </Routes>
      </MemoryRouter>
    );

  it('loads the recipe, rating, scales servings and shows substitutions', async () => {
    api.get.mockImplementation((url) =>
      url === '/recipes/5/my-rating'
        ? Promise.resolve({ rating: 4 })
        : Promise.resolve(recipe({ id: 5 }))
    );
    renderDetail();
    expect(screen.getByText('Loading...')).toBeInTheDocument();
    expect(await screen.findByText('Chicken Pasta')).toBeInTheDocument();
    expect(screen.getByText('(4.5 average rating)')).toBeInTheDocument();
    expect(screen.getByText('(Try: Turkey, Tofu)')).toBeInTheDocument();
    expect(screen.getByText('2 cups Pasta')).toBeInTheDocument();
    fireEvent.click(screen.getByText('+'));
    expect(screen.getByText('5')).toBeInTheDocument();
    expect(screen.getByText('2.5 cups Pasta')).toBeInTheDocument();
    fireEvent.click(screen.getByText('-'));
    expect(screen.getByText('4')).toBeInTheDocument();
  });

  it('ignores a servings change below 1', async () => {
    api.get.mockImplementation((url) =>
      url === '/recipes/5/my-rating'
        ? Promise.resolve({})
        : Promise.resolve(recipe({ id: 5, servings: 1 }))
    );
    renderDetail();
    await screen.findByText('Chicken Pasta');
    fireEvent.click(screen.getByText('-'));
    expect(screen.getByText('1')).toBeInTheDocument();
  });

  it('updates the average rating when a star is submitted', async () => {
    api.get.mockImplementation((url) =>
      url === '/recipes/5/my-rating'
        ? Promise.resolve({})
        : Promise.resolve(recipe({ id: 5 }))
    );
    api.post.mockResolvedValue({});
    renderDetail();
    await screen.findByText('Chicken Pasta');
    const stars = document.querySelectorAll('.cursor-pointer');
    await act(async () => fireEvent.click(stars[4]));
    expect(await screen.findByText('(4.8 average rating)')).toBeInTheDocument();
  });

  it('treats a missing user rating as unrated', async () => {
    const err = new Error('not found');
    err.response = { status: 404 };
    api.get.mockImplementation((url) =>
      url === '/recipes/5/my-rating'
        ? Promise.reject(err)
        : Promise.resolve(recipe({ id: 5 }))
    );
    renderDetail();
    expect(await screen.findByText('Chicken Pasta')).toBeInTheDocument();
    expect(console.warn).not.toHaveBeenCalled();
  });

  it('warns on non-404 rating errors', async () => {
    const err = new Error('server error');
    err.response = { status: 500 };
    api.get.mockImplementation((url) =>
      url === '/recipes/5/my-rating'
        ? Promise.reject(err)
        : Promise.resolve(recipe({ id: 5 }))
    );
    renderDetail();
    await screen.findByText('Chicken Pasta');
    expect(console.warn).toHaveBeenCalled();
  });

  it('shows not found when the recipe fetch fails', async () => {
    api.get.mockRejectedValue(new Error('down'));
    renderDetail();
    expect(await screen.findByText('Recipe not found')).toBeInTheDocument();
    expect(console.warn).toHaveBeenCalled();
  });
});

// ---------------------------------------------------------------------------
// PantryPage
// ---------------------------------------------------------------------------

describe('PantryPage', () => {
  const items = [
    { id: 1, name: 'Rice', quantity: 2, unit: 'kg' },
    { id: 2, name: 'Flour', quantity: 1, unit: 'kg' },
  ];

  it('lists pantry items', async () => {
    pantryService.getIngredients.mockResolvedValue(items);
    render(<PantryPage />);
    expect(await screen.findByText('Rice')).toBeInTheDocument();
    expect(screen.getByText('2 kg')).toBeInTheDocument();
    expect(pantryService.getIngredients).toHaveBeenCalledWith(1);
  });

  it('shows the empty state', async () => {
    pantryService.getIngredients.mockResolvedValue([]);
    render(<PantryPage />);
    expect(await screen.findByText('Your pantry is empty')).toBeInTheDocument();
  });

  it('logs fetch failures', async () => {
    pantryService.getIngredients.mockRejectedValue(new Error('down'));
    render(<PantryPage />);
    await screen.findByText('Your pantry is empty');
    expect(console.error).toHaveBeenCalled();
  });

  it('adds an item and resets the form', async () => {
    pantryService.getIngredients.mockResolvedValue(items);
    pantryService.addIngredients.mockResolvedValue({});
    render(<PantryPage />);
    await screen.findByText('Rice');
    fireEvent.change(screen.getByPlaceholderText('e.g., Flour, Olive Oil'), {
      target: { value: 'Sugar' },
    });
    fireEvent.change(screen.getByPlaceholderText('1.0'), { target: { value: '0.5' } });
    await act(async () => fireEvent.click(screen.getByText('Add to Pantry')));
    expect(pantryService.addIngredients).toHaveBeenCalledWith(1, [
      { name: 'Sugar', quantity: 0.5, unit: 'each' },
    ]);
    expect(showSuccessToast).toHaveBeenCalledWith('Item added to pantry');
    expect(screen.getByPlaceholderText('e.g., Flour, Olive Oil').value).toBe('');
  });

  it('does not add an item with a missing name', async () => {
    pantryService.getIngredients.mockResolvedValue([]);
    render(<PantryPage />);
    await screen.findByText('Your pantry is empty');
    await act(async () => fireEvent.click(screen.getByText('Add to Pantry')));
    expect(pantryService.addIngredients).not.toHaveBeenCalled();
  });

  it('shows an error toast when adding fails', async () => {
    pantryService.getIngredients.mockResolvedValue(items);
    pantryService.addIngredients.mockRejectedValue(new Error('down'));
    render(<PantryPage />);
    await screen.findByText('Rice');
    fireEvent.change(screen.getByPlaceholderText('e.g., Flour, Olive Oil'), {
      target: { value: 'Sugar' },
    });
    fireEvent.change(screen.getByPlaceholderText('1.0'), { target: { value: '1' } });
    await act(async () => fireEvent.click(screen.getByText('Add to Pantry')));
    expect(showErrorToast).toHaveBeenCalledWith('Failed to add item');
  });

  it('deletes an item', async () => {
    pantryService.getIngredients.mockResolvedValue(items);
    pantryService.deleteIngredient.mockResolvedValue({});
    render(<PantryPage />);
    await screen.findByText('Rice');
    await act(async () => fireEvent.click(screen.getAllByTitle('Remove item')[0]));
    expect(pantryService.deleteIngredient).toHaveBeenCalledWith(1, 1);
    expect(showSuccessToast).toHaveBeenCalledWith('Item removed');
  });

  it('shows an error toast when deleting fails', async () => {
    pantryService.getIngredients.mockResolvedValue(items);
    pantryService.deleteIngredient.mockRejectedValue(new Error('down'));
    render(<PantryPage />);
    await screen.findByText('Rice');
    await act(async () => fireEvent.click(screen.getAllByTitle('Remove item')[0]));
    expect(showErrorToast).toHaveBeenCalledWith('Failed to remove item');
  });

  it('consumes the latest plan after confirmation', async () => {
    pantryService.getIngredients.mockResolvedValue(items);
    pantryService.consumeLatestPlan.mockResolvedValue({ consumed_count: 3 });
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    render(<PantryPage />);
    await screen.findByText('Rice');
    await act(async () => fireEvent.click(screen.getByText('Consume Latest Plan')));
    expect(pantryService.consumeLatestPlan).toHaveBeenCalledWith(1);
    expect(showSuccessToast).toHaveBeenCalledWith('Consumed 3 items from pantry');
  });

  it('does nothing when consumption is not confirmed', async () => {
    pantryService.getIngredients.mockResolvedValue(items);
    vi.spyOn(window, 'confirm').mockReturnValue(false);
    render(<PantryPage />);
    await screen.findByText('Rice');
    await act(async () => fireEvent.click(screen.getByText('Consume Latest Plan')));
    expect(pantryService.consumeLatestPlan).not.toHaveBeenCalled();
  });

  it('shows an error toast when consumption fails', async () => {
    pantryService.getIngredients.mockResolvedValue(items);
    pantryService.consumeLatestPlan.mockRejectedValue(new Error('down'));
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    render(<PantryPage />);
    await screen.findByText('Rice');
    await act(async () => fireEvent.click(screen.getByText('Consume Latest Plan')));
    expect(showErrorToast).toHaveBeenCalledWith('Failed to consume plan');
  });
});

// ---------------------------------------------------------------------------
// ShoppingListPage
// ---------------------------------------------------------------------------

describe('ShoppingListPage', () => {
  const listData = {
    recommended_stores: [
      {
        store: 'Metro',
        subtotal: 12.5,
        savings: 3.0,
        items: [
          { name: 'Chicken', qty: 1, unit: 'kg', cost: 5.0, discount_pct: 20, category: 'Meat' },
          { name: 'Rice', qty: 2, unit: 'kg', cost: 7.5, discount_pct: 0, category: 'Grocery' },
        ],
      },
    ],
    unmatched_items: ['Truffle Oil'],
    total_cost: 12.5,
    total_savings: 3.0,
    total_regular_cost: 15.5,
    trip_efficiency: 90,
    total_items_count: 3,
    single_store_comparison: [
      { name: 'Metro', total: 14.0, items_count: 2, savings: 1.5, trip_efficiency: 90 },
      { name: 'Walmart', total: 16.0, items_count: 2, savings: 0, trip_efficiency: 80 },
    ],
    detailed_comparison: [
      { ingredient: 'Chicken', quantity: 1, unit: 'kg', prices: { Metro: 5.0, Walmart: 6.0 } },
    ],
    all_stores: ['Metro', 'Walmart'],
  };

  it('shows the loading state then the optimized list', async () => {
    api.get.mockResolvedValue(listData);
    render(<ShoppingListPage />);
    expect(screen.getByText('Optimizing your shopping list...')).toBeInTheDocument();
    expect(await screen.findByText('Shopping List')).toBeInTheDocument();
    expect(screen.getByText('Chicken')).toBeInTheDocument();
    expect(screen.getByText('$3.00')).toBeInTheDocument(); // total savings
    expect(screen.getByText('Items Not Found in Deal Database')).toBeInTheDocument();
    expect(screen.getByText('Truffle Oil')).toBeInTheDocument();
    expect(screen.getByText('19% off regular prices')).toBeInTheDocument();
    expect(api.get).toHaveBeenCalledWith(
      '/shopping/optimize?user_id=1&strategy=min_cost'
    );
  });

  it('shows the empty state when there is no data', async () => {
    api.get.mockResolvedValue(null);
    render(<ShoppingListPage />);
    expect(await screen.findByText(/No shopping list available/)).toBeInTheDocument();
  });

  it('logs fetch failures', async () => {
    api.get.mockRejectedValue(new Error('down'));
    render(<ShoppingListPage />);
    expect(await screen.findByText(/No shopping list available/)).toBeInTheDocument();
    expect(console.error).toHaveBeenCalled();
  });

  it('toggles items and persists the checked state', async () => {
    api.get.mockResolvedValue(listData);
    render(<ShoppingListPage />);
    await screen.findByText('Chicken');
    const checkbox = document.querySelector('input[type="checkbox"]');
    fireEvent.click(checkbox);
    expect(JSON.parse(localStorage.getItem('checked_items_1'))['Metro-Chicken']).toBe(true);
    fireEvent.click(checkbox);
    expect(JSON.parse(localStorage.getItem('checked_items_1'))['Metro-Chicken']).toBe(false);
  });

  it('restores checked items and handles corrupt storage', async () => {
    localStorage.setItem('checked_items_1', '{bad json');
    api.get.mockResolvedValue(listData);
    render(<ShoppingListPage />);
    await screen.findByText('Chicken');
    expect(console.error).toHaveBeenCalledWith(
      'Failed to parse checked items', expect.anything()
    );
  });

  it('switches strategy and shows the details table', async () => {
    api.get.mockResolvedValue(listData);
    render(<ShoppingListPage />);
    await screen.findByText('Shopping List');
    fireEvent.change(document.querySelector('select'), { target: { value: 'convenience' } });
    await waitFor(() =>
      expect(api.get).toHaveBeenCalledWith(
        '/shopping/optimize?user_id=1&strategy=convenience'
      )
    );
    expect(document.querySelector('select').value).toBe('convenience');
    expect(screen.queryByText('Maximum Savings')).toBeNull();
    fireEvent.click(screen.getByText('Show Details'));
    expect(screen.getByText('Side-by-Side Store Price Comparison')).toBeInTheDocument();
    fireEvent.click(screen.getByText('Hide Details'));
    expect(screen.queryByText('Side-by-Side Store Price Comparison')).toBeNull();
  });

  it('toggles preferred stores and refetches with them', async () => {
    api.get.mockResolvedValue(listData);
    render(<ShoppingListPage />);
    await screen.findByText('Shopping List');
    const star = screen.getAllByTitle('Prioritize this store')[1]; // Walmart
    fireEvent.click(star);
    expect(JSON.parse(localStorage.getItem('preferred_stores_1'))).toEqual(['Walmart']);
    await waitFor(() =>
      expect(api.get.mock.calls.at(-1)[0]).toContain('preferred_stores=Walmart')
    );
    // Clicking again removes the store from the preferred list.
    fireEvent.click(screen.getByTitle('Remove from priority'));
    expect(JSON.parse(localStorage.getItem('preferred_stores_1'))).toEqual([]);
  });
});
