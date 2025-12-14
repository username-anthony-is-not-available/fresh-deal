import axios from 'axios';
import { showErrorToast } from '../utils/toast';

const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';

const api = axios.create({
  baseURL: BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

api.interceptors.response.use(
  (response) => response.data,
  (error) => {
    const { config, response } = error;
    const originalRequest = config;

    // Retry logic for 5xx server errors
    if (response && response.status >= 500 && !originalRequest._retry) {
      originalRequest._retry = true;
      showErrorToast('A server error occurred, retrying the request...');
      return new Promise((resolve) => {
        setTimeout(() => resolve(api(originalRequest)), 1000);
      });
    }

    const errorMessage =
      error.response?.data?.detail ||
      'An unexpected error occurred. Please try again.';

    showErrorToast(errorMessage);

    return Promise.reject(error);
  }
);

export default api;
