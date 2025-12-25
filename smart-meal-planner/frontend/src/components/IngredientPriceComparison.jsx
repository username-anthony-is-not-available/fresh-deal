import React from 'react';

const IngredientPriceComparison = ({ detailedComparison, allStores }) => {
  if (!detailedComparison || detailedComparison.length === 0) {
    return null;
  }

  // Find the minimum price for each ingredient to highlight it in the table
  const itemsWithMinPrice = detailedComparison.map(item => {
    const validPrices = Object.values(item.prices).filter(price => price !== null);
    const minPrice = validPrices.length > 0 ? Math.min(...validPrices) : null;
    return { ...item, minPrice };
  });

  return (
    <div className="mt-8">
      <h3 className="text-xl font-semibold mb-4 text-gray-800">Ingredient Price Breakdown</h3>
      <div className="overflow-x-auto rounded-lg border border-gray-200 shadow-sm">
        <table className="min-w-full divide-y divide-gray-200 bg-white">
          <thead className="bg-gray-50">
            <tr>
              <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Ingredient
              </th>
              <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Quantity
              </th>
              {allStores.map(storeName => (
                <th key={storeName} scope="col" className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                  {storeName}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200">
            {itemsWithMinPrice.map(item => (
              <tr key={item.ingredient} className="hover:bg-gray-50">
                <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">{item.ingredient}</td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{`${item.quantity} ${item.unit}`}</td>
                {allStores.map(storeName => {
                  const price = item.prices[storeName];
                  const isMinPrice = price !== null && price === item.minPrice;
                  return (
                    <td key={storeName} className="px-6 py-4 whitespace-nowrap text-sm text-right">
                      {price !== null ? (
                        <span className={isMinPrice ? 'font-bold text-primary-600' : 'text-gray-700'}>
                          ${price.toFixed(2)}
                        </span>
                      ) : (
                        <span className="text-gray-400 italic">N/A</span>
                      )}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default IngredientPriceComparison;
