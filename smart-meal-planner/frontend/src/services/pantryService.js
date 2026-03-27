import api from './api';

const pantryService = {
  getIngredients: (userId) => api.get(`/pantry/${userId}`),
  addIngredients: (userId, items) => api.post(`/pantry/${userId}/add`, { items }),
  deleteIngredient: (userId, itemId) => api.delete(`/pantry/${userId}/${itemId}`),
  consumeLatestPlan: (userId) => api.post(`/pantry/${userId}/consume-latest-plan`),
};

export default pantryService;
