import React, { useState, useEffect } from 'react';
import { api } from '../services/api';
import MealCard from '../components/MealCard'; // Assuming MealCard is reusable for favorite recipes

const FavoritesPage = () => {
  const [favorites, setFavorites] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchFavorites = async () => {
      try {
        const response = await api.get('/users/me/favorites');
        setFavorites(response.data);
      } catch (err) {
        setError('Failed to fetch favorites.');
        console.error(err);
      } finally {
        setLoading(false);
      }
    };

    fetchFavorites();
  }, []);

  if (loading) return <div>Loading...</div>;
  if (error) return <div className="text-red-500">{error}</div>;

  return (
    <div className="container mx-auto p-4">
      <h1 className="text-3xl font-bold mb-6">My Favorite Recipes</h1>
      {favorites.length === 0 ? (
        <p>You haven't favorited any recipes yet.</p>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {favorites.map((recipe) => (
            <MealCard key={recipe.id} type={recipe.meal_type} meal={{...recipe, recipe_id: recipe.id, recipe_name: recipe.name, is_favorited: true}} />
          ))}
        </div>
      )}
    </div>
  );
};

export default FavoritesPage;
