// src/services/api.ts
import {API_BASE_URL} from '../config';

export const getLatestMealPlan = async (userId: number) => {
  try {
    const response = await fetch(`${API_BASE_URL}/plans/${userId}/latest`);
    if (!response.ok) {
      if (response.status === 404) {
        return null; // Handle case where user has no plan yet
      }
      throw new Error('Failed to fetch meal plan');
    }
    const data = await response.json();
    return data.content;
  } catch (error) {
    console.error('Error fetching meal plan:', error);
    throw error;
  }
};

export const getShoppingList = async (userId: number) => {
  try {
    const response = await fetch(
      `${API_BASE_URL}/shopping/optimize?user_id=${userId}`,
    );
    if (!response.ok) {
      throw new Error('Failed to fetch shopping list');
    }
    return await response.json();
  } catch (error) {
    console.error('Error fetching shopping list:', error);
    throw error;
  }
};
