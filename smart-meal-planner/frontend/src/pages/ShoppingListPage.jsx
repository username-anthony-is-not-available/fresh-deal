import React, { useState, useEffect } from 'react';
import ShoppingListItem from '../components/ShoppingListItem';
import StoreComparison from '../components/StoreComparison';
import { Download, Share2 } from 'lucide-react';

const ShoppingListPage = () => {
  const [planSummary, setPlanSummary] = useState("");
  const userId = localStorage.getItem('user_id') || 1;

  useEffect(() => {
    // Fetch latest plan to get the AI summary
    const fetchPlan = async () => {
      try {
        const res = await fetch(`http://localhost:8000/api/plans/${userId}/latest`);
        if (res.ok) {
           const data = await res.json();
           setPlanSummary(data.shopping_list_summary);
        }
      } catch (e) {
         console.error(e);
      }
    };
    fetchPlan();
  }, [userId]);

  // Mock Data for MVP visualization
  // In a real implementation, we would parse the ingredients from the MealPlan and match with Deals.
  // For this MVP, we show a sample static list to demonstrate the UI layout.
  const [items, setItems] = useState([
    { id: 1, name: 'Ground Beef', quantity: 2, unit: 'kg', store: 'Walmart', price: 14.00, is_deal: true, checked: false },
    { id: 2, name: 'Chicken Thighs', quantity: 1.5, unit: 'kg', store: 'Provigo', price: 7.49, is_deal: true, checked: false },
    { id: 3, name: 'Pasta (Spaghetti)', quantity: 2, unit: 'pack', store: 'Walmart', price: 1.94, is_deal: false, checked: false },
    { id: 4, name: 'Tomato Sauce', quantity: 3, unit: 'can', store: 'Walmart', price: 3.00, is_deal: false, checked: true },
    { id: 5, name: 'Eggs (Large)', quantity: 1, unit: 'carton', store: 'IGA', price: 4.50, is_deal: false, checked: false },
    { id: 6, name: 'Milk 2%', quantity: 2, unit: 'L', store: 'IGA', price: 5.20, is_deal: false, checked: false },
    { id: 7, name: 'Apples (Gala)', quantity: 3, unit: 'lb', store: 'Provigo', price: 2.99, is_deal: true, checked: false },
    { id: 8, name: 'Spinach', quantity: 1, unit: 'pack', store: 'Provigo', price: 3.99, is_deal: false, checked: false },
  ]);

  const toggleItem = (id) => {
    setItems(items.map(i => i.id === id ? { ...i, checked: !i.checked } : i));
  };

  const storeComparison = [
    { name: 'Walmart', total: 65.40, items_count: 8, savings: 0 },
    { name: 'Provigo', total: 72.10, items_count: 8, savings: 0 },
    { name: 'IGA', total: 78.50, items_count: 8, savings: 0 },
    { name: 'Optimized Mix', total: 43.11, items_count: 8, savings: 22.29 }, // Demo numbers
  ];

  // Group items by store for the list view
  const groupedItems = items.reduce((acc, item) => {
    if (!acc[item.store]) acc[item.store] = [];
    acc[item.store].push(item);
    return acc;
  }, {});

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
      <div className="lg:col-span-2">
        <div className="flex items-center justify-between mb-6">
           <h1 className="text-3xl font-bold text-gray-900">Shopping List</h1>
           <div className="flex gap-2">
              <button className="p-2 text-gray-600 hover:bg-gray-100 rounded-lg">
                 <Share2 className="w-5 h-5" />
              </button>
              <button className="p-2 text-gray-600 hover:bg-gray-100 rounded-lg">
                 <Download className="w-5 h-5" />
              </button>
           </div>
        </div>

        <div className="space-y-6">
           {planSummary && (
             <div className="bg-blue-50 border border-blue-200 p-4 rounded-lg mb-6">
                <h3 className="font-bold text-blue-800 text-sm mb-1">AI Recommendation</h3>
                <p className="text-blue-700 text-sm">{planSummary}</p>
             </div>
           )}

           {Object.entries(groupedItems).map(([store, storeItems]) => (
              <div key={store} className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
                 <div className="bg-gray-50 px-4 py-3 border-b border-gray-200 flex justify-between items-center">
                    <h3 className="font-bold text-gray-900">{store}</h3>
                    <span className="text-xs font-medium bg-white border border-gray-200 px-2 py-1 rounded">
                       {storeItems.length} items
                    </span>
                 </div>
                 <div className="divide-y divide-gray-100">
                    {storeItems.map(item => (
                       <ShoppingListItem
                          key={item.id}
                          item={item}
                          isChecked={item.checked}
                          onToggle={() => toggleItem(item.id)}
                       />
                    ))}
                 </div>
                 <div className="px-4 py-3 bg-gray-50 border-t border-gray-200 text-right">
                    <span className="text-sm text-gray-500 mr-2">Subtotal:</span>
                    <span className="font-bold text-gray-900">
                       ${storeItems.reduce((sum, i) => sum + i.price, 0).toFixed(2)}
                    </span>
                 </div>
              </div>
           ))}
        </div>
      </div>

      <div>
         <div className="sticky top-24">
            <h2 className="text-xl font-bold text-gray-900 mb-4">Smart Savings</h2>
            <StoreComparison stores={storeComparison} />

            <div className="mt-6 bg-accent-50 p-6 rounded-xl border border-accent-100 text-center">
               <span className="text-accent-800 font-medium block mb-1">Total Savings</span>
               <span className="text-4xl font-bold text-accent-600">$22.29</span>
               <p className="text-sm text-accent-700 mt-2">
                  By shopping at multiple stores instead of just one.
               </p>
            </div>
         </div>
      </div>
    </div>
  );
};

export default ShoppingListPage;
