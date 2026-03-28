// src/navigation/AppNavigator.tsx
import React from 'react';
import {createBottomTabNavigator} from '@react-navigation/bottom-tabs';
import {createStackNavigator} from '@react-navigation/stack';
import MealPlanScreen from '../screens/MealPlanScreen';
import ShoppingListScreen from '../screens/ShoppingListScreen';
import NotificationsScreen from '../screens/NotificationsScreen';
import LoginScreen from '../screens/LoginScreen';
import {useAuth} from '../context/AuthContext';
import {ActivityIndicator, View, Button} from 'react-native';
import {useTheme} from '../context/ThemeContext';

const Tab = createBottomTabNavigator();
const Stack = createStackNavigator();

const MainAppTabs = () => {
  const {toggleTheme, isDark, colors} = useTheme();

  return (
    <Tab.Navigator
      screenOptions={{
        headerRight: () => (
          <View style={{marginRight: 10}}>
            <Button
              title={isDark ? "Light" : "Dark"}
              onPress={toggleTheme}
              color={colors.primary}
            />
          </View>
        ),
      }}
    >
      <Tab.Screen name="Meal Plan" component={MealPlanScreen} />
      <Tab.Screen name="Shopping List" component={ShoppingListScreen} />
      <Tab.Screen name="Notifications" component={NotificationsScreen} />
    </Tab.Navigator>
  );
};

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
  const {colors} = useTheme();

  if (isLoading) {
    return (
      <View style={{flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: colors.background}}>
        <ActivityIndicator size="large" color={colors.primary} />
      </View>
    );
  }

  return user ? <MainAppTabs /> : <AuthStack />;
};

export default AppNavigator;
