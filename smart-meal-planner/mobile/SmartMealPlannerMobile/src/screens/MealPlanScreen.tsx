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
import AsyncStorage from '@react-native-async-storage/async-storage';
import {getLatestMealPlan} from '../services/api';
import MealCard from '../components/MealCard';
import {useAuth} from '../context/AuthContext';

interface Meal {
  recipe_id: number;
  recipe_name: string;
  reason: string;
  image?: string;
  servings?: number;
}

interface DailyPlan {
  day: number;
  day_name: string;
  date: string;
  breakfast: Meal;
  lunch: Meal;
  dinner: Meal;
}

interface MealPlanResponse {
  meal_plan: DailyPlan[];
  id?: number;
}

const CACHE_KEY = 'cached_meal_plan';
const TIMESTAMP_KEY = 'meal_plan_timestamp';

const MealPlanScreen = () => {
  const [mealPlan, setMealPlan] = useState<DailyPlan[] | null>(null);
  const [lastUpdated, setLastUpdated] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const {user} = useAuth();

  const loadCache = useCallback(async () => {
    try {
      const cachedData = await AsyncStorage.getItem(CACHE_KEY);
      const timestamp = await AsyncStorage.getItem(TIMESTAMP_KEY);
      if (cachedData) {
        setMealPlan(JSON.parse(cachedData));
        setLastUpdated(timestamp);
      }
    } catch (e) {
      console.error('Failed to load meal plan cache', e);
    }
  }, []);

  const fetchMealPlan = useCallback(async (showLoading = true) => {
    if (!user) {
      setError('You must be logged in to see your meal plan.');
      setLoading(false);
      return;
    }
    if (showLoading) {setLoading(true);}
    try {
      setError(null);
      const data: MealPlanResponse | null = await getLatestMealPlan(user.id);
      if (data && data.meal_plan) {
        setMealPlan(data.meal_plan);
        const now = new Date().toLocaleString();
        setLastUpdated(now);
        await AsyncStorage.setItem(CACHE_KEY, JSON.stringify(data.meal_plan));
        await AsyncStorage.setItem(TIMESTAMP_KEY, now);
      } else {
        setMealPlan(null);
      }
    } catch (e) {
      setError('Failed to load meal plan. Showing cached data if available.');
      console.error(e);
      await loadCache();
    } finally {
      setLoading(false);
    }
  }, [user, loadCache]);

  useEffect(() => {
    const init = async () => {
      await loadCache();
      fetchMealPlan(false);
    };
    init();
  }, [fetchMealPlan, loadCache]);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await fetchMealPlan(false);
    setRefreshing(false);
  }, [fetchMealPlan]);

  if (loading && !mealPlan) {
    return (
      <View style={styles.centered}>
        <ActivityIndicator size="large" />
      </View>
    );
  }

  if (error && !mealPlan) {
    return (
      <View style={styles.centered}>
        <Text style={styles.errorText}>{error}</Text>
      </View>
    );
  }

  const structuredMealPlan = (mealPlan || []).flatMap(dayPlan => [
    {
      ...dayPlan.breakfast,
      day: dayPlan.day_name,
      date: dayPlan.date,
      type: 'Breakfast' as const,
      id: `${dayPlan.date}-breakfast`,
    },
    {
      ...dayPlan.lunch,
      day: dayPlan.day_name,
      date: dayPlan.date,
      type: 'Lunch' as const,
      id: `${dayPlan.date}-lunch`,
    },
    {
      ...dayPlan.dinner,
      day: dayPlan.day_name,
      date: dayPlan.date,
      type: 'Dinner' as const,
      id: `${dayPlan.date}-dinner`,
    },
  ]);

  return (
    <SafeAreaView style={styles.container}>
      <FlatList
        data={structuredMealPlan}
        keyExtractor={item => item.id}
        renderItem={({item}) => (
          <MealCard
            day={`${item.day} (${item.date})`}
            mealType={item.type}
            meal={{
              name: item.recipe_name,
              recipe: item.reason,
            }}
          />
        )}
        contentContainerStyle={styles.list}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
        }
        ListHeaderComponent={
          <View style={styles.headerContainer}>
            <Text style={styles.header}>Your Weekly Meal Plan</Text>
            {lastUpdated && (
              <Text style={styles.timestamp}>Last updated: {lastUpdated}</Text>
            )}
            {!mealPlan && !loading && (
               <Text style={styles.emptyText}>No meal plan found. Go generate one on the website!</Text>
            )}
          </View>
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
    marginBottom: 10,
  },
  list: {
    paddingBottom: 16,
  },
  headerContainer: {
    backgroundColor: 'white',
    padding: 16,
    borderBottomWidth: 1,
    borderBottomColor: '#eee',
  },
  header: {
    fontSize: 24,
    fontWeight: 'bold',
  },
  timestamp: {
    fontSize: 12,
    color: '#666',
    marginTop: 4,
  },
  emptyText: {
    marginTop: 20,
    textAlign: 'center',
    color: '#666',
  },
});

export default MealPlanScreen;
