import React from 'react';
import { Store, Star } from 'lucide-react';

const StoreComparison = ({ stores, preferredStores = [], onTogglePreference }) => {
  // stores = [{ name: 'Walmart', total: 145.20, items_count: 24, savings: 12.50, trip_efficiency: 85.5 }, ...]

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

             const isPreferred = preferredStores.includes(store.name);

             return (
               <div key={store.name} className={`p-4 flex items-center justify-between ${isPreferred ? 'bg-amber-50/50' : ''}`}>
                  <div className="flex items-center gap-3">
                     <button
                        onClick={() => onTogglePreference(store.name)}
                        className={`p-1 rounded-full transition-colors ${isPreferred ? 'text-amber-500 hover:bg-amber-100' : 'text-gray-300 hover:bg-gray-100'}`}
                        title={isPreferred ? "Remove from priority" : "Prioritize this store"}
                     >
                        <Star className={`w-5 h-5 ${isPreferred ? 'fill-current' : ''}`} />
                     </button>
                     <div className="bg-gray-100 p-2 rounded-full">
                        <Store className="w-5 h-5 text-gray-600" />
                     </div>
                     <div>
                        <div className="font-medium text-gray-900">
                           {store.name}
                        </div>
                        <div className="text-[10px] text-gray-500">
                           {store.items_count} items • {store.trip_efficiency}% coverage
                        </div>
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
