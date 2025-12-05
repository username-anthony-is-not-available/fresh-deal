import React, { useState } from 'react';
import { Save } from 'lucide-react';

const SettingsPage = () => {
  const [formData, setFormData] = useState({
    postal_code: 'H4T 1V6',
    household_size: 4,
    dietary_preferences: 'None',
    budget_limit: 200,
    excluded_ingredients: ''
  });

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    alert("Settings saved! (Mock)");
  };

  return (
    <div className="max-w-2xl mx-auto">
      <h1 className="text-3xl font-bold text-gray-900 mb-8">Settings & Preferences</h1>

      <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
        <form onSubmit={handleSubmit} className="p-6 space-y-6">

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
             <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Postal Code</label>
                <input
                  type="text"
                  name="postal_code"
                  value={formData.postal_code}
                  onChange={handleChange}
                  className="block w-full rounded-lg border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm p-2.5 border"
                />
             </div>

             <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Household Size</label>
                <select
                   name="household_size"
                   value={formData.household_size}
                   onChange={handleChange}
                   className="block w-full rounded-lg border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm p-2.5 border"
                >
                  <option value="1">1 Person</option>
                  <option value="2">2 People</option>
                  <option value="3">3 People</option>
                  <option value="4">4 People</option>
                  <option value="5">5+ People</option>
                </select>
             </div>
          </div>

          <div>
             <label className="block text-sm font-medium text-gray-700 mb-1">Dietary Preferences</label>
             <select
                name="dietary_preferences"
                value={formData.dietary_preferences}
                onChange={handleChange}
                className="block w-full rounded-lg border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm p-2.5 border"
             >
               <option value="None">No Restrictions</option>
               <option value="Vegetarian">Vegetarian</option>
               <option value="Vegan">Vegan</option>
               <option value="Gluten-Free">Gluten-Free</option>
               <option value="Keto">Keto</option>
               <option value="Paleo">Paleo</option>
             </select>
          </div>

          <div>
             <label className="block text-sm font-medium text-gray-700 mb-1">Excluded Ingredients (comma separated)</label>
             <input
                type="text"
                name="excluded_ingredients"
                value={formData.excluded_ingredients}
                onChange={handleChange}
                placeholder="e.g. peanuts, cilantro, shellfish"
                className="block w-full rounded-lg border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm p-2.5 border"
             />
          </div>

          <div>
             <label className="block text-sm font-medium text-gray-700 mb-1">Weekly Budget Limit ($)</label>
             <div className="relative rounded-md shadow-sm">
                <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3">
                   <span className="text-gray-500 sm:text-sm">$</span>
                </div>
                <input
                   type="number"
                   name="budget_limit"
                   value={formData.budget_limit}
                   onChange={handleChange}
                   className="block w-full rounded-lg border-gray-300 pl-7 pr-12 focus:border-primary-500 focus:ring-primary-500 sm:text-sm p-2.5 border"
                />
             </div>
          </div>

          <div className="pt-4 border-t border-gray-100 flex justify-end">
             <button
                type="submit"
                className="flex items-center gap-2 bg-primary-600 text-white px-6 py-2.5 rounded-lg font-medium hover:bg-primary-700 shadow-sm"
             >
                <Save className="w-4 h-4" />
                Save Changes
             </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default SettingsPage;
