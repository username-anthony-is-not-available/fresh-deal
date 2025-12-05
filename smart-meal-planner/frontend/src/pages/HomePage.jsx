import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ChefHat, ShoppingBag, DollarSign } from 'lucide-react';

const HomePage = () => {
  const navigate = useNavigate();
  const [formData, setFormData] = useState({
    postal_code: 'H4T 1V6',
    household_size: 4,
    dietary_preferences: 'None'
  });
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);

    try {
      // Seed data first to ensure we have products
      await fetch('http://localhost:8000/api/data/seed', { method: 'POST' });

      const response = await fetch('http://localhost:8000/api/onboard', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(formData)
      });

      if (response.ok) {
        const user = await response.json();
        // Store user ID in localStorage for simple session management
        localStorage.setItem('user_id', user.id);
        navigate('/plan');
      }
    } catch (error) {
      console.error('Error onboarding:', error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto">
      <div className="text-center mb-12">
        <h1 className="text-4xl md:text-5xl font-bold text-gray-900 mb-6">
          Eat Healthy. <span className="text-primary-600">Save Money.</span><br />
          Shop Smarter.
        </h1>
        <p className="text-xl text-gray-600 mb-8 max-w-2xl mx-auto">
          Automatically discover grocery deals in Quebec, generate personalized meal plans,
          and save 20-40% on your weekly shopping bill.
        </p>

        <div className="flex justify-center gap-8 mb-12">
           <div className="flex flex-col items-center">
              <div className="bg-primary-100 p-3 rounded-full mb-2">
                 <DollarSign className="w-6 h-6 text-primary-600" />
              </div>
              <span className="font-medium">Find Best Deals</span>
           </div>
           <div className="flex flex-col items-center">
              <div className="bg-accent-100 p-3 rounded-full mb-2">
                 <ChefHat className="w-6 h-6 text-accent-600" />
              </div>
              <span className="font-medium">AI Meal Planning</span>
           </div>
           <div className="flex flex-col items-center">
              <div className="bg-blue-100 p-3 rounded-full mb-2">
                 <ShoppingBag className="w-6 h-6 text-blue-600" />
              </div>
              <span className="font-medium">Smart Lists</span>
           </div>
        </div>
      </div>

      <div className="bg-white p-8 rounded-2xl shadow-xl border border-gray-100 max-w-lg mx-auto">
        <h2 className="text-2xl font-semibold mb-6 text-gray-900">Get Your Free Meal Plan</h2>
        <form onSubmit={handleSubmit} className="space-y-5">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Postal Code</label>
            <input
              type="text"
              value={formData.postal_code}
              onChange={(e) => setFormData({...formData, postal_code: e.target.value})}
              placeholder="e.g. H4T 1V6"
              className="block w-full rounded-lg border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm p-3 border"
              required
            />
          </div>

          <div>
             <label className="block text-sm font-medium text-gray-700 mb-1">Household Size</label>
             <select
                value={formData.household_size}
                onChange={(e) => setFormData({...formData, household_size: parseInt(e.target.value)})}
                className="block w-full rounded-lg border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm p-3 border"
             >
               <option value="1">1 Person</option>
               <option value="2">2 People</option>
               <option value="3">3 People</option>
               <option value="4">4 People</option>
               <option value="5">5+ People</option>
             </select>
          </div>

          <div>
             <label className="block text-sm font-medium text-gray-700 mb-1">Dietary Preferences</label>
             <select
                value={formData.dietary_preferences}
                onChange={(e) => setFormData({...formData, dietary_preferences: e.target.value})}
                className="block w-full rounded-lg border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm p-3 border"
             >
               <option value="None">No Restrictions</option>
               <option value="Vegetarian">Vegetarian</option>
               <option value="Vegan">Vegan</option>
               <option value="Gluten-Free">Gluten-Free</option>
               <option value="Keto">Keto</option>
             </select>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-primary-600 text-white py-3 px-4 rounded-lg hover:bg-primary-700 font-bold text-lg shadow-md transition-transform transform hover:-translate-y-0.5 disabled:opacity-70"
          >
            {loading ? 'Setting up...' : 'Start Saving Today'}
          </button>
        </form>
      </div>
    </div>
  );
};

export default HomePage;
