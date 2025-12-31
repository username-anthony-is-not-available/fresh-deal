
import React from 'react';
import IngredientPriceComparison from '../components/IngredientPriceComparison';

const mockDetailedComparison = {
  "Chicken Breast": {
    "Provigo": { "price": 10, "unit": "kg" },
    "Walmart": { "price": 9.5, "unit": "kg" },
    "Metro": { "price": 11, "unit": "kg" },
  },
  "Milk": {
    "Provigo": { "price": 2.5, "unit": "L" },
    "Walmart": { "price": 2.4, "unit": "L" },
  },
  "Eggs": {
    "Metro": { "price": 3, "unit": "dozen" },
  }
};

const mockAllStores = ["Provigo", "Walmart", "Metro"];

const VerifyPriceComparison = () => {
  return (
    <div className="p-8">
      <h1 className="text-2xl font-bold mb-4">Verification Page</h1>
      <IngredientPriceComparison
        detailedComparison={mockDetailedComparison}
        allStores={mockAllStores}
      />
    </div>
  );
};

export default VerifyPriceComparison;
