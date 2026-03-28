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
import {useTheme} from '../context/ThemeContext';

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
  const [lastUpdated, setLastUpdated] = useState<number | null>(null);
  const [isOffline, setIsOffline] = useState(false);
  const {user} = useAuth();
  const {colors} = useTheme();

  const fetchMealPlan = useCallback(async () => {
    if (!user) {
      setError('You must be logged in to see your meal plan.');
      setLoading(false);
      return;
    }
    try {
      setError(null);
      const result = await getLatestMealPlan(user.id);
      setMealPlan(result.data || null);
      setLastUpdated(result.timestamp);
      setIsOffline(result.isOffline);
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
      <View style={[styles.centered, {backgroundColor: colors.background}]}>
        <ActivityIndicator size="large" color={colors.primary} />
      </View>
    );
  }

  if (error && !mealPlan) {
    return (
      <View style={[styles.centered, {backgroundColor: colors.background}]}>
        <Text style={[styles.errorText, {color: colors.error}]}>{error}</Text>
      </View>
    );
  }

  if (!mealPlan) {
    return (
      <View style={[styles.centered, {backgroundColor: colors.background}]}>
        <Text style={{color: colors.text}}>No meal plan found. Go generate one on the website!</Text>
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
    <SafeAreaView style={[styles.container, {backgroundColor: colors.background}]}>
      {isOffline && (
        <View style={[styles.offlineBanner, {backgroundColor: colors.accent}]}>
          <Text style={styles.offlineText}>Viewing offline version</Text>
        </View>
      )}
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
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.primary} />
        }
        ListHeaderComponent={
          <View style={{backgroundColor: colors.surface}}>
            <Text style={[styles.header, {color: colors.text}]}>Your Weekly Meal Plan</Text>
            {lastUpdated && (
              <Text style={[styles.lastUpdatedText, {color: colors.textSecondary}]}>
                Last updated: {new Date(lastUpdated).toLocaleString()}
              </Text>
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
  },
  centered: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: 20,
  },
  errorText: {
    textAlign: 'center',
  },
  list: {
    paddingBottom: 16,
  },
  header: {
    fontSize: 24,
    fontWeight: 'bold',
    padding: 16,
    paddingBottom: 4,
  },
  lastUpdatedText: {
    fontSize: 12,
    paddingHorizontal: 16,
    paddingBottom: 8,
  },
  offlineBanner: {
    padding: 8,
    alignItems: 'center',
  },
  offlineText: {
    color: '#000',
    fontWeight: 'bold',
  },
});

export default MealPlanScreen;
