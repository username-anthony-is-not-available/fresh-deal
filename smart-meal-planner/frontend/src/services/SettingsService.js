import api from './api';

const SettingsService = {
  getUserSettings: (userId) => {
    return api.get(`/users/${userId}`);
  },

  updateUserSettings: (userId, settings) => {
    return api.patch(`/users/${userId}`, settings);
  }
};

export default SettingsService;
