import React from 'react';

const dietaryOptions = ["vegetarian", "vegan", "gluten-free", "keto", "paleo"];

const DietaryFilters = ({ selected, onChange }) => {
  return (
    <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-200">
      <h3 className="text-lg font-semibold text-gray-900 mb-4">Dietary Preferences</h3>
      <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
        {dietaryOptions.map(option => (
          <label key={option} className="flex items-center space-x-3">
            <input
              type="checkbox"
              value={option}
              checked={selected.includes(option)}
              onChange={onChange}
              className="h-4 w-4 rounded border-gray-300 text-primary-600 focus:ring-primary-500"
            />
            <span className="text-sm text-gray-700">{option.charAt(0).toUpperCase() + option.slice(1)}</span>
          </label>
        ))}
      </div>
    </div>
  );
};

export default DietaryFilters;
