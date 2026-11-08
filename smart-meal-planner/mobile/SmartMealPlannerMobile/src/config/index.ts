// src/config/index.ts
import AsyncStorage from '@react-native-async-storage/async-storage';

export const PROD_API_URL = 'https://api.smartmealplanner.com/api';
export const DEFAULT_DEV_API_URL = 'http://10.0.2.2:8000/api'; // Android emulator localhost
export const DEFAULT_LAN_API_URL = 'http://192.168.1.100:8000/api'; // Local LAN fallback

export const CUSTOM_API_URL_STORAGE_KEY = '@custom_lan_api_url';

let activeCustomApiUrl: string | null = null;

export const setCustomApiBaseUrl = async (url: string | null) => {
  activeCustomApiUrl = url;
  try {
    if (url) {
      await AsyncStorage.setItem(CUSTOM_API_URL_STORAGE_KEY, url);
    } else {
      await AsyncStorage.removeItem(CUSTOM_API_URL_STORAGE_KEY);
    }
  } catch (e) {
    console.warn('Failed to persist custom API URL to AsyncStorage:', e);
  }
};

export const getApiBaseUrl = async (): Promise<string> => {
  if (activeCustomApiUrl) {
    return activeCustomApiUrl;
  }
  try {
    const saved = await AsyncStorage.getItem(CUSTOM_API_URL_STORAGE_KEY);
    if (saved) {
      activeCustomApiUrl = saved;
      return saved;
    }
  } catch (e) {
    // AsyncStorage unavailable, fallback to default
  }
  const isDevelopment = process.env.NODE_ENV === 'development';
  return isDevelopment ? DEFAULT_DEV_API_URL : PROD_API_URL;
};

// Backward-compatible default export
export const API_BASE_URL = process.env.NODE_ENV === 'development' ? DEFAULT_DEV_API_URL : PROD_API_URL;
