import api from './api';

export const getNutritionGoal = async () => {
    try {
        const response = await api.get('/users/me/nutrition-goal');
        return response?.data !== undefined ? response.data : response;
    } catch (error) {
        console.error('Error fetching nutrition goal:', error);
        throw error;
    }
};

export const createOrUpdateNutritionGoal = async (goalData) => {
    try {
        const response = await api.post('/users/me/nutrition-goal', goalData);
        return response?.data !== undefined ? response.data : response;
    } catch (error) {
        console.error('Error creating/updating nutrition goal:', error);
        throw error;
    }
};

export const getNutritionSummary = async (startDate, endDate) => {
    try {
        const response = await api.get('/users/me/nutrition-summary', {
            params: {
                start_date: startDate,
                end_date: endDate,
            },
        });
        return response?.data !== undefined ? response.data : response;
    } catch (error) {
        console.error('Error fetching nutrition summary:', error);
        throw error;
    }
};
