import React, { createContext, useState, useEffect } from 'react';
import authService from '../services/authService';

const AuthContext = createContext();

export const AuthProvider = ({ children }) => {
    const [user, setUser] = useState(null);

    useEffect(() => {
        const currentUser = authService.getCurrentUser();
        if (currentUser) {
            setUser(currentUser);
        }
    }, []);

    const login = async (email, password) => {
        const response = await authService.login(email, password);
        if (response.data.access_token) {
            localStorage.setItem('user', JSON.stringify(response.data));
            setUser(response.data);
        }
        return response;
    };

    const logout = () => {
        authService.logout();
        setUser(null);
    };

    const register = (email, password, postal_code, household_size, dietary_preferences) => {
        return authService.register(email, password, postal_code, household_size, dietary_preferences);
    };

    return (
        <AuthContext.Provider value={{ user, login, logout, register }}>
            {children}
        </AuthContext.Provider>
    );
};

export default AuthContext;
