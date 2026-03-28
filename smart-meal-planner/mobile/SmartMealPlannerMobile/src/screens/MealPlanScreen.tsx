// src/screens/MealPlanScreen.tsx
import React, {useEffect, useState, useCallback} from 'react';
import {
  View,
  Text,
  FlatList,
  ActivityIndicator,
  StyleSheet,
  RefreshControl,
  SafeAreaView,
} from 'react-native';
import {getLatestMealPlan} from '../services/api';
import MealCard from '../components/MealCard';
import {useAuth} from '../context/AuthContext';

// Define a more specific type for the meal plan data
interface Meal {
  name: string;
  recipe: string;
}

interface DailyPlan {
  Breakfast: Meal;
  Lunch: Meal;
  Dinner: Meal;
}

interface MealPlan {
  [day: string]: DailyPlan;
}

const MealPlanScreen = () => {
  const [mealPlan, setMealPlan] = useState<MealPlan | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const {user} = useAuth();

  const fetchMealPlan = useCallback(async () => {
    if (!user) {
      setError('You must be logged in to see your meal plan.');
      setLoading(false);
      return;
    }
    try {
      setError(null); // Clear previous errors
      const data = await getLatestMealPlan(user.id);
      setMealPlan(data?.meal_plan || null);
    } catch (e) {
      setError('Failed to load meal plan. Please try again later.');
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, [user]);

  useEffect(() => {
    setLoading(true);
    fetchMealPlan();
  }, [fetchMealPlan]);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await fetchMealPlan();
    setRefreshing(false);
  }, [fetchMealPlan]);

  if (loading) {
    return (
      <View style={styles.centered}>
        <ActivityIndicator size="large" />
      </View>
    );
  }

  if (error && !mealPlan) {
    // Show error only if there's no data to display
    return (
      <View style={styles.centered}>
        <Text style={styles.errorText}>{error}</Text>
      </View>
    );
  }

  if (!mealPlan) {
    return (
      <View style={styles.centered}>
        <Text>No meal plan found. Go generate one on the website!</Text>
      </View>
    );
  }

  const structuredMealPlan = Object.entries(mealPlan).flatMap(([day, meals]) =>
    Object.entries(meals).map(([mealType, meal]) => ({
      day,
      mealType,
      meal,
      id: `${day}-${mealType}`,
    })),
  );

  return (
    <SafeAreaView style={styles.container}>
      <FlatList
        data={structuredMealPlan}
        keyExtractor={item => item.id}
        renderItem={({item}) => (
          <MealCard
            day={item.day}
            mealType={item.mealType as 'Breakfast' | 'Lunch' | 'Dinner'}
            meal={item.meal}
          />
        )}
        contentContainerStyle={styles.list}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
        }
        ListHeaderComponent={
          <Text style={styles.header}>Your Weekly Meal Plan</Text>
        }
      />
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f5f5f5',
  },
  centered: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: 20,
  },
  errorText: {
    color: 'red',
    textAlign: 'center',
  },
  list: {
    paddingBottom: 16,
  },
  header: {
    fontSize: 24,
    fontWeight: 'bold',
    padding: 16,
    backgroundColor: 'white',
  },
});

export default MealPlanScreen;
