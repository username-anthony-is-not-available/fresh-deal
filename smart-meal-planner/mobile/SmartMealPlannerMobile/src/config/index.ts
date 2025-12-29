// src/config/index.ts
const PROD_API_URL = 'https://api.smartmealplanner.com/api';
const DEV_API_URL = 'http://10.0.2.2:8000/api'; // Android emulator localhost

// A simple way to toggle between environments.
// In a real app, this would be managed by environment variables.
const isDevelopment = process.env.NODE_ENV === 'development';

export const API_BASE_URL = isDevelopment ? DEV_API_URL : PROD_API_URL;
