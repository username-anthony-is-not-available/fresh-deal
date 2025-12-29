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

  useEffect(() => {
    const fetchRecipeAndRating = async () => {
      try {
        setLoading(true);
        const recipeData = await api.get(`/recipes/${id}`);
        setRecipe(recipeData);

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

  if (!recipe) {
    return <div>Recipe not found</div>;
  }

  return (
    <div className="container mx-auto p-4">
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
        <h2 className="text-2xl font-bold">Ingredients</h2>
        <ul className="list-disc list-inside mt-2">
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

      <div className="mt-8">
        <h2 className="text-2xl font-bold">Leave Feedback</h2>
        <RecipeFeedbackForm recipeId={id} />
      </div>
    </div>
  );
};

export default RecipeDetailPage;
