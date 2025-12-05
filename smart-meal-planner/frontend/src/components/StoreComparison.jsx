import React from 'react';
import { Store } from 'lucide-react';

const StoreComparison = ({ stores }) => {
  // stores = [{ name: 'Walmart', total: 145.20, items_count: 24, savings: 12.50 }, ...]

  // Sort by total cost ascending
  const sortedStores = [...stores].sort((a, b) => a.total - b.total);
  const bestStore = sortedStores[0];

  return (
    <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
       <div className="p-4 bg-gray-50 border-b border-gray-200">
          <h3 className="font-semibold text-gray-900">Store Comparison</h3>
       </div>
       <div className="divide-y divide-gray-100">
          {sortedStores.map((store, idx) => {
             const isBest = idx === 0;
             const diff = store.total - bestStore.total;

             return (
               <div key={store.name} className="p-4 flex items-center justify-between">
                  <div className="flex items-center gap-3">
                     <div className="bg-gray-100 p-2 rounded-full">
                        <Store className="w-5 h-5 text-gray-600" />
                     </div>
                     <div>
                        <div className="font-medium text-gray-900">{store.name}</div>
                        <div className="text-xs text-gray-500">{store.items_count} items</div>
                     </div>
                  </div>
                  <div className="text-right">
                     <div className={`font-bold ${isBest ? 'text-primary-600' : 'text-gray-900'}`}>
                        ${store.total.toFixed(2)}
                     </div>
                     {!isBest && (
                        <div className="text-xs text-red-500">
                           +${diff.toFixed(2)}
                        </div>
                     )}
                     {isBest && (
                        <div className="text-xs text-green-600 font-medium">
                           Best Price
                        </div>
                     )}
                  </div>
               </div>
             );
          })}
       </div>
    </div>
  );
};

export default StoreComparison;
