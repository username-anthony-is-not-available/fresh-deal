import React from 'react';
import { render, screen, fireEvent, act, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MemoryRouter, Routes, Route } from 'react-router-dom';

// Stable translation object: SettingsPage's effect depends on [currentUser, t],
// so `t` must keep its identity across renders or the effect re-fetches in
// an infinite microtask loop that starves timers.
const translationMock = vi.hoisted(() => {
  const t = (key) => key;
  const i18n = { changeLanguage: vi.fn(), language: 'en' };
  return { t, i18n };
});
vi.mock('react-i18next', () => ({
  useTranslation: () => translationMock,
}));

const toastMock = vi.hoisted(() => {
  const fn = vi.fn(() => 'toast-id');
  fn.success = vi.fn();
  fn.error = vi.fn();
  fn.loading = vi.fn(() => 'toast-id');
  return fn;
});
vi.mock('react-hot-toast', () => ({
  default: toastMock,
  toast: toastMock,
  Toaster: () => null,
}));

vi.mock('../services/api', () => ({
  default: { post: vi.fn(), get: vi.fn(), delete: vi.fn() },
}));
vi.mock('../services/SettingsService');
vi.mock('../services/nutritionService', () => ({
  getNutritionGoal: vi.fn(),
  createOrUpdateNutritionGoal: vi.fn(),
  getNutritionSummary: vi.fn(),
  getNutritionCompliance: vi.fn(),
  getDietaryProfiles: vi.fn(),
  getRecommendedNutritionGoal: vi.fn(),
}));
const authState = vi.hoisted(() => ({
  user: { id: 1, name: 'Test User' },
  currentUser: { id: 1, name: 'Test User' },
}));
// Keep the real AuthProvider/default context (PrivateRoute reads the real
// context via useContext); only useAuth is overridden for useAuth consumers.
// The real AuthProvider sets the user in a useEffect, which is too late:
// the first render already redirects to /login. This synchronous provider
// mirrors main.jsx's ThemeProvider/AuthProvider nesting with the user
// available on the first render.
vi.mock('../context/AuthContext', async (importOriginal) => {
  const actual = await importOriginal();
  const SyncAuthProvider = ({ children }) => (
    <actual.default.Provider
      value={{
        user: authState.user,
        currentUser: authState.currentUser,
        login: vi.fn(),
        logout: vi.fn(),
        register: vi.fn(),
      }}
    >
      {children}
    </actual.default.Provider>
  );
  return { ...actual, useAuth: () => authState, AuthProvider: SyncAuthProvider };
});
vi.mock('../services/authService', () => ({
  default: {
    getCurrentUser: vi.fn(),
    login: vi.fn(),
    logout: vi.fn(),
    register: vi.fn(),
  },
}));
vi.mock('../hooks/useNetworkStatus', () => ({
  useNetworkStatus: () => useNetworkStatusMock(),
}));
const useNetworkStatusMock = vi.hoisted(() => vi.fn(() => true));

import api from '../services/api';
import authService from '../services/authService';
import SettingsService from '../services/SettingsService';
import { ThemeProvider } from '../context/ThemeContext';
import {
  getNutritionGoal,
  createOrUpdateNutritionGoal,
  getNutritionSummary,
  getNutritionCompliance,
} from '../services/nutritionService';
import Layout from '../layouts/Layout';
import App from '../App';
import VerifyPriceComparison from '../pages/VerifyPriceComparison';
import FeedbackDashboardPage from '../pages/FeedbackDashboardPage';
import SettingsPage from '../pages/SettingsPage';
import NutritionDashboard from '../pages/NutritionDashboard';
import MealCard from '../components/MealCard';
import PantryPage from '../pages/PantryPage';
import NetworkStatusIndicator from '../components/NetworkStatusIndicator';
import pantryService from '../services/pantryService';

vi.mock('../services/pantryService', () => ({
  default: {
    getIngredients: vi.fn(),
    addIngredients: vi.fn(),
    deleteIngredient: vi.fn(),
    consumeLatestPlan: vi.fn(),
  },
}));

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
  authState.user = { id: 1, name: 'Test User' };
  authState.currentUser = { id: 1, name: 'Test User' };
  authService.getCurrentUser.mockReturnValue({ id: 1, name: 'Test User' });
  useNetworkStatusMock.mockReturnValue(true);
  vi.spyOn(console, 'error').mockImplementation(() => {});
  vi.spyOn(console, 'warn').mockImplementation(() => {});
});

// ---------------------------------------------------------------------------
// Layout
// ---------------------------------------------------------------------------

describe('Layout', () => {
  const renderLayout = (route = '/deals') =>
    render(
      <ThemeProvider>
        <MemoryRouter initialEntries={[route]}>
          <Routes>
            <Route path="/" element={<Layout />}>
              <Route index element={<div>home content</div>} />
              <Route path="deals" element={<div>deals content</div>} />
            </Route>
          </Routes>
        </MemoryRouter>
      </ThemeProvider>
    );

  it('renders nav, outlet content and footer', () => {
    renderLayout();
    expect(screen.getByText(/SmartMeal/)).toBeInTheDocument();
    expect(screen.getByText('deals content')).toBeInTheDocument();
    expect(screen.getByText(/2025 Smart Meal Planner/)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /deals/ })).toHaveAttribute('href', '/deals');
    // The deals link is active on /deals.
    expect(screen.getByRole('link', { name: /deals/ }).className).toContain('border-primary-500');
    // First test in the file: absorbs the full App import graph, which can
    // take several seconds on a throttled VM.
  }, 20000);

  it('opens the mobile menu and closes it via a nav link', () => {
    renderLayout();
    // The menu button is the last button in the header (after both
    // ThemeToggle instances); the first .sm:hidden button is a ThemeToggle.
    const buttons = document.querySelectorAll('header button');
    const menuButton = buttons[buttons.length - 1];
    fireEvent.click(menuButton);
    expect(screen.getAllByText('deals').length).toBe(2); // desktop + mobile
    fireEvent.click(screen.getAllByRole('link', { name: /deals/ })[1]);
    expect(screen.getAllByText('deals').length).toBe(1);
  }, 20000);
});

// ---------------------------------------------------------------------------
// App / PrivateRoute
// ---------------------------------------------------------------------------

describe('App', () => {
  it('redirects logged-out users to login', async () => {
    authState.user = null;
    authState.currentUser = null;
    authService.getCurrentUser.mockReturnValue(null);
    window.history.pushState({}, '', '/deals');
    render(<ThemeProvider><App /></ThemeProvider>);
    expect(await screen.findByRole('heading', { name: 'Login' })).toBeInTheDocument();
  });

  it('renders the home page at / when logged in', async () => {
    api.get.mockResolvedValue(null);
    window.history.pushState({}, '', '/');
    render(<ThemeProvider><App /></ThemeProvider>);
    expect(await screen.findByText(/Eat Healthy/)).toBeInTheDocument();
  });

  it('renders a private page when logged in', async () => {
    api.get.mockResolvedValue([]);
    window.history.pushState({}, '', '/deals');
    render(<ThemeProvider><App /></ThemeProvider>);
    expect(await screen.findByText('Weekly Flyers & Deals')).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// VerifyPriceComparison
// ---------------------------------------------------------------------------

describe('VerifyPriceComparison', () => {
  it('renders the comparison table with mock data', () => {
    render(<VerifyPriceComparison />);
    expect(screen.getByText('Verification Page')).toBeInTheDocument();
    expect(screen.getByText('Chicken Breast')).toBeInTheDocument();
    expect(screen.getByText('$10.00')).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// NetworkStatusIndicator (offline branch)
// ---------------------------------------------------------------------------

describe('NetworkStatusIndicator', () => {
  it('shows the offline banner when offline', () => {
    useNetworkStatusMock.mockReturnValue(false);
    render(<NetworkStatusIndicator />);
    expect(screen.getByText(/You are currently offline/)).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// FeedbackDashboardPage gaps
// ---------------------------------------------------------------------------

describe('FeedbackDashboardPage gaps', () => {
  const items = [
    { id: 1, recipe_id: 5, meal_plan_id: null, rating: 5, comment: 'Great', created_at: '2026-11-01' },
    { id: 2, recipe_id: null, meal_plan_id: 3, rating: 3, comment: null, created_at: '2026-11-02' },
  ];
  const summary = {
    total_feedback_count: 2, average_recipe_rating: 4.5, average_meal_plan_rating: 3.0,
  };

  beforeEach(() => {
    api.get.mockImplementation((url) =>
      url === '/feedback/summary' ? Promise.resolve(summary) : Promise.resolve(items)
    );
  });

  it('filters by recipe and meal plan', async () => {
    render(<FeedbackDashboardPage />);
    expect(await screen.findByText('Feedback Dashboard')).toBeInTheDocument();
    expect(screen.getByText('Recipe Feedback')).toBeInTheDocument();
    fireEvent.click(screen.getByText('Recipes'));
    expect(screen.getByText('Recipe Feedback')).toBeInTheDocument();
    expect(screen.queryByText('Meal Plan Feedback')).toBeNull();
    fireEvent.click(screen.getByText('Meal Plans'));
    expect(screen.getByText('Meal Plan Feedback')).toBeInTheDocument();
    expect(screen.queryByText('Recipe Feedback')).toBeNull();
    fireEvent.click(screen.getByText('All Feedback'));
    expect(screen.getByText('Recipe Feedback')).toBeInTheDocument();
    expect(screen.getByText('Meal Plan Feedback')).toBeInTheDocument();
  });

  it('shows the empty state and logs fetch failures', async () => {
    api.get.mockRejectedValue(new Error('down'));
    render(<FeedbackDashboardPage />);
    expect(await screen.findByText('No feedback found for this category.')).toBeInTheDocument();
    expect(console.error).toHaveBeenCalled();
  });
});

// ---------------------------------------------------------------------------
// SettingsPage gaps
// ---------------------------------------------------------------------------

describe('SettingsPage gaps', () => {
  beforeEach(() => {
    SettingsService.getUserSettings.mockResolvedValue({
      data: {
        postal_code: 'H2X1Y2', household_size: 2,
        dietary_preferences: ['vegan'], allergies: ['peanuts'],
      },
    });
    SettingsService.updateUserSettings.mockResolvedValue({});
    getNutritionGoal.mockResolvedValue(null);
  });

  it('loads settings and toggles dietary preferences', async () => {
    render(<SettingsPage />);
    expect(await screen.findByDisplayValue('H2X1Y2')).toBeInTheDocument();
    const vegan = screen.getByDisplayValue('vegan');
    expect(vegan.checked).toBe(true);
    fireEvent.click(vegan);
    expect(vegan.checked).toBe(false);
    fireEvent.click(vegan);
    expect(vegan.checked).toBe(true);
  });

  it('does not fetch when there is no current user', () => {
    authState.user = null;
    authState.currentUser = null;
    authService.getCurrentUser.mockReturnValue(null);
    render(<SettingsPage />);
    expect(SettingsService.getUserSettings).not.toHaveBeenCalled();
  });

  it('shows an error toast when loading fails', async () => {
    SettingsService.getUserSettings.mockRejectedValue(new Error('down'));
    render(<SettingsPage />);
    await waitFor(() => expect(toastMock.error).toHaveBeenCalledWith('failed_to_load_settings'));
    expect(console.error).toHaveBeenCalled();
  });

  it('saves settings and handles save failures', async () => {
    render(<SettingsPage />);
    await screen.findByDisplayValue('H2X1Y2');
    fireEvent.change(screen.getByLabelText('excluded_ingredients'), {
      target: { value: 'peanuts, cilantro' },
    });
    await act(async () => fireEvent.click(screen.getByText('save_changes')));
    expect(SettingsService.updateUserSettings).toHaveBeenCalledWith(1, {
      postal_code: 'H2X1Y2',
      household_size: 2,
      dietary_preferences: ['vegan'],
      allergies: ['peanuts', 'cilantro'],
    });
    expect(toastMock.success).toHaveBeenCalledWith(
      'settings_saved_successfully', { id: 'toast-id' }
    );

    SettingsService.updateUserSettings.mockRejectedValueOnce(new Error('down'));
    await act(async () => fireEvent.click(screen.getByText('save_changes')));
    expect(toastMock.error).toHaveBeenCalledWith(
      'failed_to_save_settings', { id: 'toast-id' }
    );
  });

  it('changes the language', async () => {
    render(<SettingsPage />);
    await screen.findByDisplayValue('H2X1Y2');
    fireEvent.change(screen.getByLabelText('language'), { target: { value: 'fr' } });
    expect(translationMock.i18n.changeLanguage).toHaveBeenCalledWith('fr');
  });
});

// ---------------------------------------------------------------------------
// NutritionDashboard gaps
// ---------------------------------------------------------------------------

describe('NutritionDashboard gaps', () => {
  it('marks goals warning/danger and shows compliance warnings', async () => {
    getNutritionGoal.mockResolvedValue({
      goal_type: 'maintenance', target_calories: 2000, target_protein: 150,
      target_carbs: 250, target_fats: 70, target_fiber: 30,
    });
    getNutritionSummary.mockResolvedValue([
      { date: '2026-11-20', calories: 3000, protein: 50, carbs: 100, fats: 20, fiber: 5 },
    ]);
    getNutritionCompliance.mockResolvedValue({
      compliance_score: 60, status: 'at_risk', restrictions: [],
      warnings: ['Low fiber intake', 'Watch sodium'],
      micronutrients_to_watch: [],
    });
    render(<NutritionDashboard />);
    expect(await screen.findByText('Low fiber intake')).toBeInTheDocument();
    expect(screen.getByText('Watch sodium')).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// MealCard gaps
// ---------------------------------------------------------------------------

describe('MealCard gaps', () => {
  const meal = {
    recipe_id: 1, recipe_name: 'Chicken Pasta',
    ingredients: [{ item: 'Chicken' }],
  };

  it('unfavorites via the delete endpoint', async () => {
    api.delete.mockResolvedValue({});
    render(<MealCard type="Dinner" meal={{ ...meal, is_favorited: true }} />);
    await act(async () =>
      fireEvent.click(document.querySelector('.text-gray-400.hover\\:text-red-500'))
    );
    expect(api.delete).toHaveBeenCalledWith('/recipes/1/favorite');
  });

  it('ignores a comment submit with empty text', async () => {
    render(<MealCard type="Dinner" meal={meal} />);
    fireEvent.click(screen.getByTitle('Add a comment'));
    const box = screen.getByPlaceholderText('Add a comment...');
    const sendBtn = box.parentElement.querySelector('button');
    expect(sendBtn.disabled).toBe(true);
    await act(async () => fireEvent.click(sendBtn));
    expect(api.post).not.toHaveBeenCalled();
  });
});

// ---------------------------------------------------------------------------
// PantryPage gaps
// ---------------------------------------------------------------------------

describe('PantryPage gaps', () => {
  it('returns early on an empty add form and honors the unit select', async () => {
    pantryService.getIngredients.mockResolvedValue([]);
    pantryService.addIngredients.mockResolvedValue({});
    render(<PantryPage />);
    await screen.findByText('Your pantry is empty');
    fireEvent.submit(document.querySelector('form'));
    expect(pantryService.addIngredients).not.toHaveBeenCalled();
    fireEvent.change(screen.getByPlaceholderText('e.g., Flour, Olive Oil'), {
      target: { value: 'Sugar' },
    });
    fireEvent.change(screen.getByPlaceholderText('1.0'), { target: { value: '1' } });
    fireEvent.change(document.querySelectorAll('select')[0], { target: { value: 'kg' } });
    await act(async () => fireEvent.click(screen.getByText('Add to Pantry')));
    expect(pantryService.addIngredients).toHaveBeenCalledWith(1, [
      { name: 'Sugar', quantity: 1, unit: 'kg' },
    ]);
  });
});
