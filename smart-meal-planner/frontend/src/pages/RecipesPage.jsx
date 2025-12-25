import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Search, Filter, Star } from 'lucide-react';
import api from '../services/api';

const RecipesPage = () => {
  const [recipes, setRecipes] = useState([]);
  const [topRated, setTopRated] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [cuisine, setCuisine] = useState('');
  const [prepTime, setPrepTime] = useState('');

  useEffect(() => {
    const fetchInitialData = async () => {
      setLoading(true);
      await Promise.all([fetchRecipes(), fetchTopRatedRecipes()]);
      setLoading(false);
    };
    fetchInitialData();
  }, []);

  const fetchRecipes = async () => {
    try {
      const params = new URLSearchParams({
        search,
        cuisine,
        prep_time: prepTime,
      }).toString();
      const data = await api.get(`/recipes?${params}`);
      setRecipes(data);
    } catch (e) {
      console.warn("Failed to fetch recipes", e);
      setRecipes([]);
    }
  };

  const fetchTopRatedRecipes = async () => {
    try {
      const data = await api.get('/recipes/top-rated');
      setTopRated(data);
    } catch (e) {
      console.warn("Failed to fetch top-rated recipes", e);
      setTopRated([]);
    }
  };

  const handleSearch = (e) => {
    e.preventDefault();
    setLoading(true);
    fetchRecipes().finally(() => setLoading(false));
  };

  return (
    <div className="container mx-auto p-4">
      {/* Top Rated Section */}
      {topRated.length > 0 && (
        <div className="mb-12">
          <h2 className="text-2xl font-bold text-gray-900 mb-4">Top-Rated Recipes</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
            {topRated.map((recipe) => (
              <Link to={`/recipes/${recipe.id}`} key={recipe.id} className="bg-white rounded-lg shadow-md p-4 block hover:shadow-lg transition-shadow">
                <h3 className="text-lg font-bold">{recipe.name}</h3>
                <p className="text-gray-500">{recipe.cuisine}</p>
                <div className="flex items-center mt-2">
                  <Star className="w-5 h-5 text-yellow-400 fill-yellow-400" />
                  <span className="ml-1 text-gray-600">{recipe.average_rating.toFixed(1)}</span>
                </div>
              </Link>
            ))}
          </div>
        </div>
      )}

      {/* All Recipes Section */}
      <div className="flex flex-col md:flex-row md:items-center justify-between mb-8 gap-4">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">All Recipes</h1>
          <p className="text-gray-500 mt-1">Found {recipes.length} recipes</p>
        </div>
        <form onSubmit={handleSearch} className="flex gap-2">
           <div className="relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-4 h-4" />
              <input
                 type="text"
                 placeholder="Search recipes..."
                 className="pl-9 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 outline-none"
                 value={search}
                 onChange={(e) => setSearch(e.target.value)}
              />
           </div>
           <select
             value={cuisine}
             onChange={(e) => setCuisine(e.target.value)}
             className="px-4 py-2 border border-gray-300 rounded-lg bg-white hover:bg-gray-50 text-gray-700"
           >
             <option value="">All Cuisines</option>
             <option value="Italian">Italian</option>
             <option value="Asian">Asian</option>
             <option value="Mexican">Mexican</option>
           </select>
           <input
             type="number"
             placeholder="Prep time (min)"
             className="px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 outline-none"
             value={prepTime}
             onChange={(e) => setPrepTime(e.target.value)}
           />
           <button type="submit" className="flex items-center gap-2 px-4 py-2 border border-gray-300 rounded-lg bg-white hover:bg-gray-50 text-gray-700">
              <Filter className="w-4 h-4" />
              Filter
           </button>
        </form>
      </div>

      {loading ? (
        <div className="text-center py-12">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600 mx-auto mb-4"></div>
          <p className="text-gray-500">Loading recipes...</p>
        </div>
      ) : recipes.length > 0 ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
          {recipes.map((recipe) => (
            <Link to={`/recipes/${recipe.id}`} key={recipe.id} className="bg-white rounded-lg shadow-md p-4 block hover:shadow-lg transition-shadow">
              <h2 className="text-lg font-bold">{recipe.name}</h2>
              <p className="text-gray-500">{recipe.cuisine}</p>
              <div className="flex items-center mt-2">
                <Star className="w-5 h-5 text-yellow-400 fill-yellow-400" />
                <span className="ml-1 text-gray-600">{recipe.average_rating.toFixed(1)}</span>
              </div>
            </Link>
          ))}
        </div>
      ) : (
        <div className="text-center py-12 bg-white rounded-lg border border-dashed border-gray-300">
          <p className="text-gray-500">No recipes found.</p>
        </div>
      )}
    </div>
  );
};

export default RecipesPage;
