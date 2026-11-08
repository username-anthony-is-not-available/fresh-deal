
import React, { useState, useEffect } from 'react';
import ShoppingListItem from '../components/ShoppingListItem';
import StoreComparison from '../components/StoreComparison';
import IngredientPriceComparison from '../components/IngredientPriceComparison';
import { Download, Share2, TrendingDown, MapPin, DollarSign, ListCollapse, Zap } from 'lucide-react';
import api from '../services/api';

const ShoppingListPage = () => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [strategy, setStrategy] = useState("min_cost");
  const [showDetailed, setShowDetailed] = useState(false);
  const userId = localStorage.getItem('user_id') || 1;
  const [checkedItems, setCheckedItems] = useState({});
  const storageKey = `checked_items_${userId}`;
  const [preferredStores, setPreferredStores] = useState(() => {
    const saved = localStorage.getItem(`preferred_stores_${userId}`);
    return saved ? JSON.parse(saved) : [];
  });

  useEffect(() => {
    const saved = localStorage.getItem(storageKey);
    if (saved) {
      try {
        setCheckedItems(JSON.parse(saved));
      } catch (e) {
        console.error("Failed to parse checked items", e);
      }
    }
  }, [storageKey]);

  const toggleItem = (storeName, itemName) => {
    const key = `${storeName}-${itemName}`;
    setCheckedItems(prev => {
      const newChecked = {
        ...prev,
        [key]: !prev[key]
      };
      localStorage.setItem(storageKey, JSON.stringify(newChecked));
      return newChecked;
    });
  };

  const toggleStorePreference = (storeName) => {
    setPreferredStores(prev => {
      const updated = prev.includes(storeName)
        ? prev.filter(s => s !== storeName)
        : [...prev, storeName];
      localStorage.setItem(`preferred_stores_${userId}`, JSON.stringify(updated));
      return updated;
    });
  };

  const groupByCategory = (items) => {
    return items.reduce((groups, item) => {
      const category = item.category || 'Grocery';
      if (!groups[category]) {
        groups[category] = [];
      }
      groups[category].push(item);
      return groups;
    }, {});
  };

  useEffect(() => {
    const fetchList = async () => {
      setLoading(true);
      try {
        let url = `/shopping/optimize?user_id=${userId}&strategy=${strategy}`;
        if (preferredStores.length > 0) {
          preferredStores.forEach(s => {
            url += `&preferred_stores=${encodeURIComponent(s)}`;
          });
        }
        const result = await api.get(url);
        setData(result);
      } catch (e) {
        console.error("Failed to fetch shopping list", e);
      } finally {
        setLoading(false);
      }
    };
    fetchList();
  }, [userId, strategy, preferredStores]);

  if (loading) {
      return <div className="p-8 text-center text-gray-500">Optimizing your shopping list...</div>;
  }

  if (!data || !data.recommended_stores) {
      return <div className="p-8 text-center">No shopping list available. Generate a meal plan first!</div>;
  }

  // Format comparison for the chart component
  // The component likely expects { name, total, savings }
  // We construct mock comparison for the other stores vs our optimized total
  // const comparisonData = [
  //    // We can just show the recommended breakdown for now as "Optimized"
  //    // Or ideally, the backend should return "Single Store" estimates.
  //    // For MVP, we will visualize the Savings.
  //    { name: 'Optimized', total: data.total_cost, savings: data.total_savings },
  //    { name: 'Regular Price', total: data.total_regular_cost, savings: 0 }
  // ];

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
      <div className="lg:col-span-2">
        <div className="flex flex-col md:flex-row md:items-center justify-between mb-6 gap-4">
           <div>
               <h1 className="text-3xl font-bold text-gray-900">Shopping List</h1>
               <p className="text-sm text-gray-500 mt-1">
                   Strategy: <span className="font-medium text-gray-700">{strategy === 'min_cost' ? 'Maximum Savings' : 'Convenience'}</span>
               </p>
           </div>

           <div className="flex gap-2">
                <select
                    value={strategy}
                    onChange={(e) => setStrategy(e.target.value)}
                    className="border border-gray-300 rounded-lg px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-accent-500"
                >
                    <option value="min_cost">Max Savings (Multi-Store)</option>
                    <option value="convenience">Convenience (Fewer Stops)</option>
                </select>

              <button className="p-2 text-gray-600 hover:bg-gray-100 rounded-lg">
                 <Share2 className="w-5 h-5" />
              </button>
              <button
                  onClick={() => setShowDetailed(!showDetailed)}
                  className="p-2 px-3 text-gray-600 hover:bg-gray-100 rounded-lg flex items-center gap-2 border border-gray-300 bg-white"
                >
                   <ListCollapse className="w-5 h-5" />
                   <span className="text-sm font-medium">{showDetailed ? 'Hide' : 'Show'} Details</span>
                </button>
           </div>
        </div>

        <div className="space-y-6">
           {data.recommended_stores.map((storeData, idx) => (
              <div key={idx} className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden relative">
                 {/* Store Header */}
                 <div className="bg-gray-50 px-4 py-3 border-b border-gray-200 flex justify-between items-center">
                    <div className="flex items-center gap-3">
                        <div className="bg-blue-100 text-blue-800 font-bold w-8 h-8 flex items-center justify-center rounded-full text-sm">
                            {idx + 1}
                        </div>
                        <div>
                            <h3 className="font-bold text-gray-900 text-lg">{storeData.store}</h3>
                            <span className="text-xs text-gray-500 flex items-center gap-1">
                                <MapPin className="w-3 h-3" /> Stop #{idx + 1}
                            </span>
                        </div>
                    </div>
                    <div className="text-right">
                        <div className="font-bold text-gray-900">${storeData.subtotal.toFixed(2)}</div>
                        {storeData.savings > 0 && (
                            <div className="text-xs text-green-600 font-medium">Save ${storeData.savings.toFixed(2)}</div>
                        )}
                    </div>
                 </div>

                 {/* Items List */}
                 <div className="flex flex-col">
                    {Object.entries(groupByCategory(storeData.items)).map(([category, items]) => (
                        <div key={category} className="border-b last:border-b-0 border-gray-100">
                            <div className="bg-gray-50/50 px-4 py-1.5 flex items-center justify-between border-b border-gray-100">
                                <h4 className="text-[10px] font-bold text-gray-400 uppercase tracking-widest">
                                    {category}
                                </h4>
                                <span className="text-[10px] font-medium text-gray-400">{items.length} {items.length === 1 ? 'item' : 'items'}</span>
                            </div>
                            <div className="divide-y divide-gray-100">
                                {items.map((item, i) => {
                                   const isChecked = !!checkedItems[`${storeData.store}-${item.name}`];
                                   return (
                                   <div key={i} className={`flex items-center p-4 hover:bg-gray-50 transition-colors ${isChecked ? 'bg-gray-50/50 opacity-60' : ''}`}>
                                       <input
                                            type="checkbox"
                                            checked={isChecked}
                                            onChange={() => toggleItem(storeData.store, item.name)}
                                            className="w-5 h-5 text-accent-600 rounded border-gray-300 focus:ring-accent-500 mr-4 cursor-pointer"
                                       />
                                       <div className="flex-1">
                                           <p className={`font-medium text-gray-900 ${isChecked ? 'line-through text-gray-500' : ''}`}>{item.name}</p>
                                           <p className="text-xs text-gray-500">{item.qty} {item.unit}</p>
                                       </div>
                                       <div className="text-right">
                                           <div className={`font-medium ${isChecked ? 'text-gray-400' : 'text-gray-900'}`}>${item.cost.toFixed(2)}</div>
                                           {item.discount_pct > 0 && !isChecked && (
                                               <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-red-100 text-red-800">
                                                   -{item.discount_pct}%
                                               </span>
                                           )}
                                       </div>
                                   </div>
                                )})}
                            </div>
                        </div>
                    ))}
                 </div>
              </div>
           ))}

           {data.unmatched_items.length > 0 && (
               <div className="bg-gray-50 p-4 rounded-lg border border-gray-200">
                   <h4 className="font-bold text-gray-700 mb-2">Items Not Found in Deal Database</h4>
                   <ul className="list-disc list-inside text-sm text-gray-600">
                       {data.unmatched_items.map((item, i) => (
                           <li key={i}>{item}</li>
                       ))}
                   </ul>
               </div>
           )}

           {showDetailed && data.detailed_comparison && (
             <IngredientPriceComparison
               detailedComparison={data.detailed_comparison}
               allStores={data.all_stores}
             />
           )}
        </div>
      </div>

      {/* Sidebar Stats */}
      <div>
         <div className="sticky top-24 space-y-6">
            <div className="bg-gradient-to-br from-green-50 to-emerald-50 p-6 rounded-2xl border border-green-100 text-center shadow-sm">
               <span className="inline-flex items-center justify-center p-3 bg-green-100 rounded-full mb-3 text-green-600">
                   <DollarSign className="w-6 h-6" />
               </span>
               <span className="text-gray-600 font-medium block mb-1 uppercase text-xs tracking-wider">Total Savings</span>
               <span className="text-4xl font-extrabold text-green-600">${data.total_savings.toFixed(2)}</span>
               <p className="text-sm text-green-700 mt-2 font-medium">
                  {(data.total_savings / data.total_regular_cost * 100).toFixed(0)}% off regular prices
               </p>
            </div>

            <div className="bg-gradient-to-br from-blue-50 to-indigo-50 p-6 rounded-2xl border border-blue-100 text-center shadow-sm">
               <span className="inline-flex items-center justify-center p-3 bg-blue-100 rounded-full mb-3 text-blue-600">
                   <Zap className="w-6 h-6" />
               </span>
               <span className="text-gray-600 font-medium block mb-1 uppercase text-xs tracking-wider">Trip Efficiency</span>
               <span className="text-4xl font-extrabold text-blue-600">{data.trip_efficiency}%</span>
               <p className="text-sm text-blue-700 mt-2 font-medium">
                  Coverage: {data.total_items_count - data.unmatched_items.length}/{data.total_items_count} items
               </p>
            </div>

            {data.single_store_comparison && data.single_store_comparison.length > 0 && (
                <StoreComparison
                  stores={data.single_store_comparison}
                  preferredStores={preferredStores}
                  onTogglePreference={toggleStorePreference}
                />
            )}

            <div className="bg-white p-6 rounded-xl border border-gray-200 shadow-sm">
                <h3 className="font-bold text-gray-900 mb-4 flex items-center gap-2">
                    <TrendingDown className="w-5 h-5 text-gray-500" />
                    Cost Breakdown
                </h3>
                <div className="space-y-3">
                    <div className="flex justify-between text-sm">
                        <span className="text-gray-500">Regular Price</span>
                        <span className="font-medium text-gray-900 line-through">${data.total_regular_cost.toFixed(2)}</span>
                    </div>
                    <div className="flex justify-between text-sm">
                        <span className="text-gray-500">Optimized Price</span>
                        <span className="font-bold text-accent-600">${data.total_cost.toFixed(2)}</span>
                    </div>
                    <div className="h-px bg-gray-100 my-2"></div>
                    <div className="flex justify-between text-sm font-bold">
                        <span className="text-green-600">Your Savings</span>
                        <span className="text-green-600">-${data.total_savings.toFixed(2)}</span>
                    </div>
                </div>
            </div>

            <div className="bg-blue-50 p-4 rounded-xl border border-blue-100">
                <h4 className="font-bold text-blue-900 text-sm mb-2">Why these stores?</h4>
                <p className="text-xs text-blue-700 leading-relaxed">
                    We found that splitting your trip between <strong>{data.recommended_stores.map(s => s.store).join(' and ')}</strong> saves you the most money this week based on active flyers.
                </p>
            </div>
         </div>
      </div>
    </div>
  );
};

export default ShoppingListPage;
