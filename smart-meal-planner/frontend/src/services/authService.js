import axios from 'axios';

const API_URL = 'http://localhost:8000';

const register = (email, password, postal_code, household_size, dietary_preferences) => {
    return axios.post(`${API_URL}/auth/register`, {
        email,
        password,
        postal_code,
        household_size,
        dietary_preferences
    });
};

const login = (email, password) => {
    const params = new URLSearchParams();
    params.append('username', email);
    params.append('password', password);
    return axios.post(`${API_URL}/auth/login/access-token`, params, {
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded'
        }
    });
};

const logout = () => {
    localStorage.removeItem('user');
};

const getCurrentUser = () => {
    return JSON.parse(localStorage.getItem('user'));
};

export default {
    register,
    login,
    logout,
    getCurrentUser
};
