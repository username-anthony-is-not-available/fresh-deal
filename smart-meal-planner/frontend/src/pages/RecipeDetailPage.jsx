import React, { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import api from '../services/api';

const RecipeDetailPage = () => {
  const { id } = useParams();
  const [recipe, setRecipe] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchRecipe = async () => {
      try {
        const data = await api.get(`/recipes/${id}`);
        setRecipe(data);
      } catch (e) {
        console.warn("Failed to fetch recipe", e);
      } finally {
        setLoading(false);
      }
    };
    fetchRecipe();
  }, [id]);

  if (loading) {
    return <div>Loading...</div>;
  }

  if (!recipe) {
    return <div>Recipe not found</div>;
  }

  return (
    <div>
      <h1 className="text-3xl font-bold">{recipe.name}</h1>
      <p className="text-gray-500">{recipe.cuisine}</p>
      <div className="mt-4">
        <h2 className="text-xl font-bold">Ingredients</h2>
        <ul>
          {recipe.ingredients.map((ingredient) => (
            <li key={ingredient}>
              {ingredient}
              {recipe.substitutions[ingredient] && (
                <span className="text-gray-500 ml-2">
                  (Substitutes: {recipe.substitutions[ingredient].join(', ')})
                </span>
              )}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
};

export default RecipeDetailPage;
