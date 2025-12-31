// src/services/api.ts
import apiClient from './apiClient';

export const getLatestMealPlan = async (userId: number) => {
  try {
    const data = await apiClient.get(`/plans/${userId}/latest`);
    return data?.content || null;
  } catch (error) {
    // The old implementation returned null on 404, let's check for that
    if (error.message.includes('404')) {
      return null;
    }
    console.error('Error fetching meal plan:', error);
    throw error;
  }
};

export const getShoppingList = async (userId: number) => {
  try {
    const data = await apiClient.get(`/shopping/optimize?user_id=${userId}`);
    return data;
  } catch (error) {
    console.error('Error fetching shopping list:', error);
    throw error;
  }
};
