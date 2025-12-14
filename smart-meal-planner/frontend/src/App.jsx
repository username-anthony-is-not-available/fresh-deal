import React, { useContext } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import Layout from './layouts/Layout';
import HomePage from './pages/HomePage';
import DealsPage from './pages/DealsPage';
import MealPlanPage from './pages/MealPlanPage';
import ShoppingListPage from './pages/ShoppingListPage';
import SettingsPage from './pages/SettingsPage';
import ScrapingDashboardPage from './pages/ScrapingDashboardPage';
import LoginPage from './pages/LoginPage';
import RegisterPage from './pages/RegisterPage';
import FavoritesPage from './pages/FavoritesPage';
import RecipesPage from './pages/RecipesPage';
import RecipeDetailPage from './pages/RecipeDetailPage';
import NutritionDashboard from './pages/NutritionDashboard';
import AuthContext, { AuthProvider } from './context/AuthContext';
import { Toaster } from 'react-hot-toast';

const PrivateRoute = ({ children }) => {
  const { user } = useContext(AuthContext);
  return user ? children : <Navigate to="/login" />;
};

function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<Layout />}>
        <Route index element={<HomePage />} />
        <Route path="login" element={<LoginPage />} />
        <Route path="register" element={<RegisterPage />} />
        <Route
          path="deals"
          element={<PrivateRoute><DealsPage /></PrivateRoute>}
        />
        <Route
          path="plan"
          element={<PrivateRoute><MealPlanPage /></PrivateRoute>}
        />
        <Route
          path="list"
          element={<PrivateRoute><ShoppingListPage /></PrivateRoute>}
        />
        <Route
          path="scraping"
          element={<PrivateRoute><ScrapingDashboardPage /></PrivateRoute>}
        />
        <Route
          path="settings"
          element={<PrivateRoute><SettingsPage /></PrivateRoute>}
        />
        <Route
          path="favorites"
          element={<PrivateRoute><FavoritesPage /></PrivateRoute>}
        />
        <Route
          path="nutrition"
          element={<PrivateRoute><NutritionDashboard /></PrivateRoute>}
        />
        <Route
          path="recipes"
          element={<PrivateRoute><RecipesPage /></PrivateRoute>}
        />
        <Route
          path="recipes/:id"
          element={<PrivateRoute><RecipeDetailPage /></PrivateRoute>}
        />
      </Route>
    </Routes>
  );
}

function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Toaster position="top-center" reverseOrder={false} />
        <AppRoutes />
      </AuthProvider>
    </BrowserRouter>
  );
}

export default App;
