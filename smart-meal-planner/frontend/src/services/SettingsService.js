import axios from 'axios';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const SettingsService = {
  getUserSettings: (userId) => {
    return axios.get(`${API_URL}/api/users/${userId}`);
  },

  updateUserSettings: (userId, settings) => {
    return axios.patch(`${API_URL}/api/users/${userId}`, settings);
  }
};

export default SettingsService;
