import React from 'react';
import {
  render,
  screen,
  fireEvent,
  waitFor,
} from '@testing-library/react-native';
import {NavigationContainer} from '@react-navigation/native';
import AppNavigator from '../../src/navigation/AppNavigator';
import * as api from '../../src/services/api';

// Mock the api service
jest.mock('../../src/services/api');
const mockedApi = api as jest.Mocked<typeof api>;

// Mock the AuthContext module to provide a logged-in state
jest.mock('../../src/context/AuthContext', () => ({
  useAuth: jest.fn(() => ({
    user: {id: 1},
    isLoading: false,
  })),
  AuthProvider: ({children}) => <>{children}</>,
}));

test('renders the initial screen and can navigate to other tabs', async () => {
  // Provide mock implementations for the API calls to simulate no data
  mockedApi.getLatestMealPlan.mockResolvedValue(null);
  mockedApi.getShoppingList.mockResolvedValue({min_cost_stores: null});

  render(
    <NavigationContainer>
      <AppNavigator />
    </NavigationContainer>,
  );

  // 1. Verify the initial screen is rendered
  await waitFor(() =>
    expect(
      screen.getByText('No meal plan found. Go generate one on the website!'),
    ).toBeTruthy(),
  );

  // 2. Navigate to Shopping List
  fireEvent.press(screen.getByText('Shopping List'));
  await waitFor(() =>
    expect(
      screen.getByText('No shopping list found. Generate a meal plan first!'),
    ).toBeTruthy(),
  );

  // 3. Navigate to Notifications
  fireEvent.press(screen.getByText('Notifications'));
  await waitFor(() =>
    expect(screen.getByText('This feature is coming soon!')).toBeTruthy(),
  );
});
