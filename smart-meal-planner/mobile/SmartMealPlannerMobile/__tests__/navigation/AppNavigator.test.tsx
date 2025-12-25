import React from 'react';
import {render, screen, fireEvent} from '@testing-library/react-native';
import {NavigationContainer} from '@react-navigation/native';
import AppNavigator from '../../src/navigation/AppNavigator';

test('renders the initial screen and can navigate to other tabs', async () => {
  render(
    <NavigationContainer>
      <AppNavigator />
    </NavigationContainer>,
  );

  // 1. Verify the initial screen is rendered
  expect(await screen.findByText('Meal Plan Screen')).toBeTruthy();

  // 2. Navigate to Shopping List and verify its screen is rendered
  fireEvent.press(screen.getByLabelText('Shopping List, tab, 2 of 3'));
  expect(await screen.findByText('Shopping List Screen')).toBeTruthy();

  // 3. Navigate to Notifications and verify its screen is rendered
  fireEvent.press(screen.getByLabelText('Notifications, tab, 3 of 3'));
  expect(await screen.findByText('Notifications Screen')).toBeTruthy();
});
