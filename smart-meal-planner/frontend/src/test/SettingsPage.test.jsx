import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import SettingsPage from '../pages/SettingsPage';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import toast from 'react-hot-toast';
import SettingsService from '../services/SettingsService';

// Mock the services and hooks
vi.mock('../services/SettingsService');
vi.mock('react-hot-toast');
vi.mock('../context/AuthContext', () => ({
  useAuth: () => ({ currentUser: { id: 1, name: 'Test User' } }),
}));
vi.mock('react-i18next', () => ({
    useTranslation: () => ({
        t: (key) => key,
        i18n: {
            changeLanguage: vi.fn(),
            language: 'en',
        },
    }),
}));

describe('SettingsPage', () => {
  beforeEach(() => {
    SettingsService.getUserSettings.mockResolvedValue({
      data: {
        postal_code: 'H4T 1V6',
        household_size: 4,
        dietary_preferences: 'None',
      },
    });
    SettingsService.updateUserSettings.mockResolvedValue({});
  });

  it('renders and loads initial data', async () => {
    render(<BrowserRouter><SettingsPage /></BrowserRouter>);

    // Wait for the postal code field to be populated
    const postalCodeInput = await screen.findByDisplayValue('H4T 1V6');
    expect(postalCodeInput).toBeInTheDocument();

    expect(screen.getByLabelText('household_size')).toHaveValue('4');

    // Check that no dietary preferences are selected
    const vegetarianCheckbox = await screen.findByLabelText('vegetarian');
    expect(vegetarianCheckbox).not.toBeChecked();
  });

  it('updates form data on input change', async () => {
    render(<BrowserRouter><SettingsPage /></BrowserRouter>);

    const postalCodeInput = await screen.findByLabelText('postal_code');
    fireEvent.change(postalCodeInput, { target: { value: 'G1A 1A1' } });
    expect(postalCodeInput).toHaveValue('G1A 1A1');
  });
});
