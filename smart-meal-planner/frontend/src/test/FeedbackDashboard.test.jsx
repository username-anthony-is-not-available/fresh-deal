import { render, screen, waitFor } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import FeedbackDashboardPage from '../pages/FeedbackDashboardPage';
import { BrowserRouter } from 'react-router-dom';
import api from '../services/api';

vi.mock('../services/api');

describe('FeedbackDashboardPage', () => {
  it('renders loading state and then feedback items', async () => {
    api.get.mockImplementation((url) => {
      if (url === '/feedback') {
        return Promise.resolve([
          { id: 1, rating: 5, comment: 'Great meal!', created_at: '2024-01-01T00:00:00Z', recipe_id: 1, meal_plan_id: null },
          { id: 2, rating: 4, comment: 'Nice variety.', created_at: '2024-01-02T00:00:00Z', recipe_id: null, meal_plan_id: 1 }
        ]);
      }
      if (url === '/feedback/summary') {
        return Promise.resolve({
          average_recipe_rating: 5.0,
          average_meal_plan_rating: 4.0,
          total_feedback_count: 2
        });
      }
      return Promise.reject(new Error('not found'));
    });

    render(
      <BrowserRouter>
        <FeedbackDashboardPage />
      </BrowserRouter>
    );

    expect(screen.getByText(/Loading dashboard.../i)).toBeDefined();

    await waitFor(() => {
      expect(screen.getByText('Feedback Dashboard')).toBeDefined();
    });

    expect(screen.getByText(/Great meal!/i)).toBeDefined();
    expect(screen.getByText(/Nice variety./i)).toBeDefined();
    expect(screen.getByText('Recipe Feedback')).toBeDefined();
    expect(screen.getByText('Meal Plan Feedback')).toBeDefined();
  });
});
