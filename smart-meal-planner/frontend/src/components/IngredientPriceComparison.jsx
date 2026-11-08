import React from 'react';
import { TrendingDown, Award, Store } from 'lucide-react';

const IngredientPriceComparison = ({ detailedComparison, allStores: providedStores, projectedSavings }) => {
  if (!detailedComparison || (Array.isArray(detailedComparison) && detailedComparison.length === 0) || (typeof detailedComparison === 'object' && Object.keys(detailedComparison).length === 0)) {
    return (
      <div className="text-gray-500 italic p-6 text-center bg-gray-50 dark:bg-gray-800 rounded-xl border border-gray-100 dark:border-gray-700">
        No detailed ingredient price comparison available for this basket.
      </div>
    );
  }

  // Normalize data into a standard array format
  let items = [];
  let detectedStores = new Set();

  if (Array.isArray(detailedComparison)) {
    items = detailedComparison.map(entry => {
      const prices = entry.prices || {};
      Object.keys(prices).forEach(s => detectedStores.add(s));
      let minPrice = Infinity;
      Object.values(prices).forEach(p => {
        if (typeof p === 'number' && p < minPrice) minPrice = p;
      });
      return {
        ingredient: entry.ingredient || entry.name || 'Item',
        quantity: entry.quantity || entry.qty || 1,
        unit: entry.unit || 'unit',
        prices,
        minPrice: minPrice === Infinity ? null : minPrice,
      };
    });
  } else {
    items = Object.entries(detailedComparison).map(([ingredient, details]) => {
      let minPrice = Infinity;
      const prices = {};
      Object.entries(details).forEach(([key, val]) => {
        if (['quantity', 'unit', 'qty'].includes(key)) return;
        detectedStores.add(key);
        if (typeof val === 'number') {
          prices[key] = val;
          if (val < minPrice) minPrice = val;
        } else if (val && typeof val.price === 'number') {
          prices[key] = val.price;
          if (val.price < minPrice) minPrice = val.price;
        }
      });
      return {
        ingredient,
        quantity: details.quantity || details.qty || 1,
        unit: details.unit || 'unit',
        prices,
        minPrice: minPrice === Infinity ? null : minPrice,
      };
    });
  }

  const stores = (providedStores && providedStores.length > 0) ? providedStores : Array.from(detectedStores);

  // Compute store totals
  const storeTotals = {};
  stores.forEach(s => {
    let total = 0;
    let count = 0;
    items.forEach(itm => {
      const p = itm.prices[s];
      if (typeof p === 'number') {
        total += p;
        count += 1;
      }
    });
    storeTotals[s] = { total: roundVal(total), count };
  });

  function roundVal(v) {
    return Math.round(v * 100) / 100;
  }

  // Find lowest total store with good coverage
  let cheapestStore = null;
  let minBasketTotal = Infinity;
  stores.forEach(s => {
    if (storeTotals[s].count === items.length && storeTotals[s].total < minBasketTotal) {
      minBasketTotal = storeTotals[s].total;
      cheapestStore = s;
    }
  });

  return (
    <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm overflow-hidden border border-gray-200 dark:border-gray-700 transition-colors">
      <div className="p-4 bg-gray-50 dark:bg-gray-850 border-b border-gray-200 dark:border-gray-700 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <Store className="w-5 h-5 text-primary-600 dark:text-primary-400" />
          <h3 className="font-bold text-gray-900 dark:text-white text-base">
            Side-by-Side Store Price Comparison
          </h3>
        </div>
        {projectedSavings && (
          <div className="flex items-center gap-1.5 text-xs font-semibold text-emerald-700 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-950/40 px-3 py-1.5 rounded-full border border-emerald-200 dark:border-emerald-800">
            <TrendingDown className="w-4 h-4" />
            <span>Projected Savings vs Regular: <strong>${projectedSavings.toFixed ? projectedSavings.toFixed(2) : projectedSavings}</strong></span>
          </div>
        )}
      </div>

      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700 text-sm">
          <thead className="bg-gray-100/70 dark:bg-gray-800/80">
            <tr>
              <th scope="col" className="px-5 py-3 text-left font-semibold text-gray-600 dark:text-gray-300">
                Ingredient
              </th>
              <th scope="col" className="px-5 py-3 text-left font-semibold text-gray-600 dark:text-gray-300">
                Qty / Unit
              </th>
              {stores.map(storeName => (
                <th key={storeName} scope="col" className="px-5 py-3 text-right font-semibold text-gray-600 dark:text-gray-300">
                  <div className="flex items-center justify-end gap-1">
                    {storeName === cheapestStore && (
                      <Award className="w-4 h-4 text-emerald-600 dark:text-emerald-400" title="Lowest overall basket" />
                    )}
                    <span>{storeName}</span>
                  </div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100 dark:divide-gray-700">
            {items.map(item => (
              <tr key={item.ingredient} className="hover:bg-gray-50/60 dark:hover:bg-gray-750 transition-colors">
                <td className="px-5 py-3 font-medium text-gray-900 dark:text-gray-100">{item.ingredient}</td>
                <td className="px-5 py-3 text-gray-500 dark:text-gray-400">{`${item.quantity} ${item.unit}`}</td>
                {stores.map(storeName => {
                  const price = item.prices[storeName];
                  const isMinPrice = price !== null && typeof price === 'number' && price === item.minPrice;
                  return (
                    <td key={storeName} className="px-5 py-3 text-right whitespace-nowrap">
                      {price !== null && typeof price === 'number' ? (
                        <span className={isMinPrice ? 'font-bold text-emerald-700 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-950/40 px-2 py-0.5 rounded border border-emerald-200 dark:border-emerald-800' : 'text-gray-700 dark:text-gray-300'}>
                          ${price.toFixed(2)}
                        </span>
                      ) : (
                        <span className="text-gray-400 dark:text-gray-500 italic text-xs">N/A</span>
                      )}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
          <tfoot className="bg-gray-50 dark:bg-gray-850 font-bold border-t-2 border-gray-200 dark:border-gray-700">
            <tr>
              <td colSpan={2} className="px-5 py-3 text-gray-900 dark:text-white">
                Basket Subtotal
              </td>
              {stores.map(s => {
                const isBest = s === cheapestStore;
                const tot = storeTotals[s]?.total;
                return (
                  <td key={s} className="px-5 py-3 text-right whitespace-nowrap">
                    <span className={isBest ? 'text-emerald-700 dark:text-emerald-400 font-extrabold' : 'text-gray-900 dark:text-gray-100'}>
                      ${tot !== undefined ? tot.toFixed(2) : '0.00'}
                    </span>
                  </td>
                );
              })}
            </tr>
          </tfoot>
        </table>
      </div>
    </div>
  );
};

export default IngredientPriceComparison;
