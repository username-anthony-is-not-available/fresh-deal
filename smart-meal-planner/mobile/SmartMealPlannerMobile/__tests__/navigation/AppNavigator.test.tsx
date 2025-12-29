import React from 'react';
import {render, screen, fireEvent} from '@testing-library/react-native';
import {NavigationContainer} from '@react-navigation/native';
import AppNavigator from '../../src/navigation/AppNavigator';
import {AuthProvider} from '../../src/context/AuthContext'; // Import AuthProvider
import * as api from '../../src/services/api';

// Mock the api service
jest.mock('../../src/services/api');
const mockedApi = api as jest.Mocked<typeof api>;

test('renders the initial screen and can navigate to other tabs', async () => {
  // Provide mock implementations for the API calls to simulate no data
  mockedApi.getLatestMealPlan.mockResolvedValue(null);
  mockedApi.getShoppingList.mockResolvedValue({min_cost_stores: null});

  render(
    <AuthProvider>
      <NavigationContainer>
        <AppNavigator />
      </NavigationContainer>
    </AuthProvider>,
  );

  // 1. Verify the initial screen renders its "no data" state
  expect(
    await screen.findByText('No meal plan found. Go generate one on the website!'),
  ).toBeTruthy();

  // 2. Navigate to Shopping List and verify its "no data" state
  fireEvent.press(screen.getByLabelText('Shopping List, tab, 2 of 3'));
  expect(
    await screen.findByText('No shopping list found. Generate a meal plan first!'),
  ).toBeTruthy();

  // 3. Navigate to Notifications and verify its placeholder state
  fireEvent.press(screen.getByLabelText('Notifications, tab, 3 of 3'));
  expect(await screen.findByText('This feature is coming soon!')).toBeTruthy();
});
