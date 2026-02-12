import React, { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import api from '../services/api';
import StarRating from '../components/StarRating';
import RecipeFeedbackForm from '../components/RecipeFeedbackForm';

const RecipeDetailPage = () => {
  const { id } = useParams();
  const [recipe, setRecipe] = useState(null);
  const [loading, setLoading] = useState(true);
  const [userRating, setUserRating] = useState(0);
  const [servings, setServings] = useState(4);
  const [baseRecipe, setBaseRecipe] = useState(null);

  useEffect(() => {
    const fetchRecipeAndRating = async () => {
      try {
        setLoading(true);
        const recipeData = await api.get(`/recipes/${id}`);
        setRecipe(recipeData);
        setBaseRecipe(recipeData);
        setServings(recipeData.servings);

        // Fetch the user's rating
        try {
          const ratingData = await api.get(`/recipes/${id}/my-rating`);
          if (ratingData && ratingData.rating) {
            setUserRating(ratingData.rating);
          }
        } catch (ratingError) {
          // It's okay if the user hasn't rated it yet, 404 is expected
          if (ratingError.response && ratingError.response.status !== 404) {
             console.warn("Failed to fetch user rating", ratingError);
          }
        }

      } catch (e) {
        console.warn("Failed to fetch recipe", e);
      } finally {
        setLoading(false);
      }
    };
    fetchRecipeAndRating();
  }, [id]);

  const handleRatingSubmit = (newRating) => {
    setUserRating(newRating);
    // Optimistically update the average rating
    setRecipe((prevRecipe) => ({
      ...prevRecipe,
      average_rating: (prevRecipe.average_rating + newRating) / 2, // simplified update
    }));
  };

  if (loading) {
    return <div>Loading...</div>;
  }

  const handleServingsChange = (newServings) => {
    if (newServings < 1) return;
    const ratio = newServings / baseRecipe.servings;
    const scaledIngredients = baseRecipe.ingredients.map(ing => {
      if (typeof ing === 'object' && ing !== null && 'quantity' in ing) {
        return { ...ing, quantity: Math.round(ing.quantity * ratio * 100) / 100 };
      }
      return ing;
    });
    setServings(newServings);
    setRecipe(prev => ({ ...prev, ingredients: scaledIngredients, servings: newServings }));
  };

  if (!recipe) {
    return <div>Recipe not found</div>;
  }

  const formatIngredient = (ing) => {
    if (typeof ing === 'string') return ing;
    return `${ing.quantity} ${ing.unit} ${ing.item}`;
  };

  return (
    <div className="container mx-auto p-4 max-w-4xl">
      <h1 className="text-3xl font-bold">{recipe.name}</h1>
      <p className="text-gray-500">{recipe.cuisine}</p>

      <div className="mt-4 flex items-center space-x-2">
        <StarRating
          recipeId={id}
          initialRating={userRating}
          onRatingSubmit={handleRatingSubmit}
        />
        <span className="text-gray-600">
          ({recipe.average_rating.toFixed(1)} average rating)
        </span>
      </div>

      <div className="mt-8">
        <div className="flex justify-between items-center">
          <h2 className="text-2xl font-bold">Ingredients</h2>
          <div className="flex items-center space-x-2 bg-gray-100 p-2 rounded-lg">
            <span className="text-sm font-medium">Servings:</span>
            <button
              onClick={() => handleServingsChange(servings - 1)}
              className="w-8 h-8 flex items-center justify-center bg-white rounded border border-gray-300 hover:bg-gray-50"
            >
              -
            </button>
            <span className="w-8 text-center font-bold">{servings}</span>
            <button
              onClick={() => handleServingsChange(servings + 1)}
              className="w-8 h-8 flex items-center justify-center bg-white rounded border border-gray-300 hover:bg-gray-50"
            >
              +
            </button>
          </div>
        </div>
        <ul className="list-disc list-inside mt-4 space-y-2">
          {recipe.ingredients.map((ingredient, idx) => (
            <li key={idx}>
              <span className="font-medium">{formatIngredient(ingredient)}</span>
              {recipe.substitutions[ingredient.item || ingredient] && (
                <span className="text-gray-500 ml-2 text-sm italic">
                  (Try: {recipe.substitutions[ingredient.item || ingredient].join(', ')})
                </span>
              )}
            </li>
          ))}
        </ul>
      </div>

      <div className="mt-8">
        <h2 className="text-2xl font-bold">Leave Feedback</h2>
        <RecipeFeedbackForm recipeId={id} />
      </div>
    </div>
  );
};

export default RecipeDetailPage;
