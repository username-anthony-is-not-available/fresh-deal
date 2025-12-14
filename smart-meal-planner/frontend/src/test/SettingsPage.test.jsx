import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
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
    render(<SettingsPage />);

    // Wait for the postal code field to be populated
    const postalCodeInput = await screen.findByDisplayValue('H4T 1V6');
    expect(postalCodeInput).toBeInTheDocument();

    expect(screen.getByLabelText('Household Size')).toHaveValue('4');
    expect(screen.getByLabelText('Dietary Preferences')).toHaveValue('None');
  });

  it('updates form data on input change', async () => {
    render(<SettingsPage />);

    const postalCodeInput = await screen.findByLabelText('Postal Code');
    fireEvent.change(postalCodeInput, { target: { value: 'G1A 1A1' } });
    expect(postalCodeInput).toHaveValue('G1A 1A1');
  });
});
