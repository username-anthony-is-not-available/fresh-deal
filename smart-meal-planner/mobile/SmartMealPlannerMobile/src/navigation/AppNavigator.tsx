import React from 'react';
import {createBottomTabNavigator} from '@react-navigation/bottom-tabs';
import MealPlanScreen from '../screens/MealPlanScreen';
import ShoppingListScreen from '../screens/ShoppingListScreen';
import NotificationsScreen from '../screens/NotificationsScreen';

const Tab = createBottomTabNavigator();

const AppNavigator = () => {
  return (
    <Tab.Navigator>
      <Tab.Screen name="Meal Plan" component={MealPlanScreen} />
      <Tab.Screen name="Shopping List" component={ShoppingListScreen} />
      <Tab.Screen name="Notifications" component={NotificationsScreen} />
    </Tab.Navigator>
  );
};

export default AppNavigator;
