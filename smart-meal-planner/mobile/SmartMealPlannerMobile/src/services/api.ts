// src/services/api.ts
import apiClient from './apiClient';
import AsyncStorage from '@react-native-async-storage/async-storage';

const CACHE_KEYS = {
  MEAL_PLAN: (userId: number) => `meal_plan_${userId}`,
  SHOPPING_LIST: (userId: number) => `shopping_list_${userId}`,
  CHECKED_ITEMS: (userId: number) => `shopping_checked_items_${userId}`,
};

export const getLatestMealPlan = async (userId: number) => {
  const cacheKey = CACHE_KEYS.MEAL_PLAN(userId);
  try {
    const data = await apiClient.get(`/plans/${userId}/latest`);
    const result = data?.content || null;

    // Cache the result
    if (result) {
      const cacheData = {
        data: result,
        timestamp: Date.now(),
      };
      await AsyncStorage.setItem(cacheKey, JSON.stringify(cacheData));
    }

    return {
      data: result,
      timestamp: Date.now(),
      isOffline: false,
    };
  } catch (error: any) {
    if (error.message && error.message.includes('404')) {
      return {
        data: null,
        timestamp: Date.now(),
        isOffline: false,
      };
    }

    // Try to get from cache on error (offline)
    const cached = await AsyncStorage.getItem(cacheKey);
    if (cached) {
      const parsed = JSON.parse(cached);
      return {
        data: parsed.data,
        timestamp: parsed.timestamp,
        isOffline: true,
      };
    }

    console.error('Error fetching meal plan:', error);
    throw error;
  }
};

export const getShoppingList = async (userId: number) => {
  const cacheKey = CACHE_KEYS.SHOPPING_LIST(userId);
  try {
    const data = await apiClient.get(`/shopping/optimize?user_id=${userId}`);

    // Cache the result
    if (data) {
      const cacheData = {
        data: data,
        timestamp: Date.now(),
      };
      await AsyncStorage.setItem(cacheKey, JSON.stringify(cacheData));
    }

    return {
      data: data,
      timestamp: Date.now(),
      isOffline: false,
    };
  } catch (error: any) {
    // Try to get from cache on error (offline)
    const cached = await AsyncStorage.getItem(cacheKey);
    if (cached) {
      const parsed = JSON.parse(cached);
      return {
        data: parsed.data,
        timestamp: parsed.timestamp,
        isOffline: true,
      };
    }

    console.error('Error fetching shopping list:', error);
    throw error;
  }
};

export const getOfflineCheckedItems = async (userId: number): Promise<Record<string, boolean>> => {
  try {
    const data = await AsyncStorage.getItem(CACHE_KEYS.CHECKED_ITEMS(userId));
    return data ? JSON.parse(data) : {};
  } catch (e) {
    return {};
  }
};

export const toggleOfflineItemChecked = async (
  userId: number,
  itemKey: string,
): Promise<Record<string, boolean>> => {
  try {
    const current = await getOfflineCheckedItems(userId);
    current[itemKey] = !current[itemKey];
    await AsyncStorage.setItem(
      CACHE_KEYS.CHECKED_ITEMS(userId),
      JSON.stringify(current),
    );
    return current;
  } catch (e) {
    console.error('Failed to toggle offline item checked:', e);
    return {};
  }
};
