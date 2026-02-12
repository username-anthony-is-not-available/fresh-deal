import React, { useState } from 'react';
import { ChevronDown, ChevronUp, Filter } from 'lucide-react';

const dietaryOptions = ["vegetarian", "vegan", "gluten-free", "keto", "paleo"];

const DietaryFilters = ({ selected, onChange, initialOpen = false }) => {
  const [isOpen, setIsOpen] = useState(initialOpen);

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full px-6 py-4 flex items-center justify-between hover:bg-gray-50 transition-colors md:cursor-default md:hover:bg-white"
      >
        <div className="flex items-center gap-2">
          <Filter className="w-4 h-4 text-gray-500" />
          <h3 className="text-base font-semibold text-gray-900">Dietary Preferences</h3>
          {selected.length > 0 && (
            <span className="bg-primary-100 text-primary-700 text-xs font-bold px-2 py-0.5 rounded-full ml-1">
              {selected.length}
            </span>
          )}
        </div>
        <div className="md:hidden">
          {isOpen ? <ChevronUp className="w-5 h-5 text-gray-400" /> : <ChevronDown className="w-5 h-5 text-gray-400" />}
        </div>
      </button>

      <div className={`px-6 pb-6 ${isOpen ? 'block' : 'hidden'} md:block`}>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
          {dietaryOptions.map(option => (
            <label key={option} className="flex items-center space-x-3 cursor-pointer group">
              <input
                type="checkbox"
                value={option}
                checked={selected.includes(option)}
                onChange={onChange}
                className="h-5 w-5 rounded border-gray-300 text-primary-600 focus:ring-primary-500 transition-colors"
              />
              <span className="text-sm text-gray-700 group-hover:text-primary-600 transition-colors">
                {option.charAt(0).toUpperCase() + option.slice(1)}
              </span>
            </label>
          ))}
        </div>
      </div>
    </div>
  );
};

export default DietaryFilters;
