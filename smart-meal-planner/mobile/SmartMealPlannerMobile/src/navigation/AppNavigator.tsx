// src/navigation/AppNavigator.tsx
import React from 'react';
import {createBottomTabNavigator} from '@react-navigation/bottom-tabs';
import {createStackNavigator} from '@react-navigation/stack';
import MealPlanScreen from '../screens/MealPlanScreen';
import ShoppingListScreen from '../screens/ShoppingListScreen';
import NotificationsScreen from '../screens/NotificationsScreen';
import LoginScreen from '../screens/LoginScreen';
import {useAuth} from '../context/AuthContext';
import {ActivityIndicator, View} from 'react-native';

const Tab = createBottomTabNavigator();
const Stack = createStackNavigator();

const MainAppTabs = () => (
  <Tab.Navigator>
    <Tab.Screen name="Meal Plan" component={MealPlanScreen} />
    <Tab.Screen name="Shopping List" component={ShoppingListScreen} />
    <Tab.Screen name="Notifications" component={NotificationsScreen} />
  </Tab.Navigator>
);

const AuthStack = () => (
  <Stack.Navigator>
    <Stack.Screen
      name="Login"
      component={LoginScreen}
      options={{headerShown: false}}
    />
  </Stack.Navigator>
);

const AppNavigator = () => {
  const {user, isLoading} = useAuth();

  if (isLoading) {
    return (
      <View style={{flex: 1, justifyContent: 'center', alignItems: 'center'}}>
        <ActivityIndicator size="large" />
      </View>
    );
  }

  return user ? <MainAppTabs /> : <AuthStack />;
};

export default AppNavigator;
