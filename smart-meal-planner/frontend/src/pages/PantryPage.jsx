import React, { useState, useEffect } from 'react';
import { Plus, Trash2, Loader2, Package, RefreshCw, AlertCircle } from 'lucide-react';
import pantryService from '../services/pantryService';
import { showSuccessToast, showErrorToast } from '../utils/toast';

const PantryPage = () => {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [isAdding, setIsAdding] = useState(false);
  const [isConsuming, setIsConsuming] = useState(false);
  const [newItem, setNewItem] = useState({ name: '', quantity: '', unit: 'each' });
  const userId = localStorage.getItem('user_id') || 1;

  const fetchPantry = async () => {
    setLoading(true);
    try {
      const data = await pantryService.getIngredients(userId);
      setItems(data);
    } catch (error) {
      console.error('Failed to fetch pantry', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPantry();
  }, [userId]);

  const handleAddItem = async (e) => {
    e.preventDefault();
    if (!newItem.name || !newItem.quantity) return;

    setIsAdding(true);
    try {
      await pantryService.addIngredients(userId, [{
        name: newItem.name,
        quantity: parseFloat(newItem.quantity),
        unit: newItem.unit
      }]);
      showSuccessToast('Item added to pantry');
      setNewItem({ name: '', quantity: '', unit: 'each' });
      fetchPantry();
    } catch (error) {
      console.error(error);
      showErrorToast('Failed to add item');
    } finally {
      setIsAdding(false);
    }
  };

  const handleDeleteItem = async (itemId) => {
    try {
      await pantryService.deleteIngredient(userId, itemId);
      showSuccessToast('Item removed');
      fetchPantry();
    } catch (error) {
      console.error(error);
      showErrorToast('Failed to remove item');
    }
  };

  const handleConsumeLatestPlan = async () => {
    if (!window.confirm('This will subtract ingredients used in your latest meal plan from your pantry. Continue?')) {
      return;
    }

    setIsConsuming(true);
    try {
      const result = await pantryService.consumeLatestPlan(userId);
      showSuccessToast(`Consumed ${result.consumed_count} items from pantry`);
      fetchPantry();
    } catch (error) {
      console.error(error);
      showErrorToast('Failed to consume plan');
    } finally {
      setIsConsuming(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto p-4 sm:p-6 lg:p-8">
      <div className="flex flex-col md:flex-row md:items-center justify-between mb-8 gap-4">
        <div>
          <h1 className="text-3xl font-bold text-gray-900 dark:text-white">Pantry Inventory</h1>
          <p className="text-gray-500 dark:text-gray-400 mt-1">
            Keep track of staples you already have to save on your shopping list.
          </p>
        </div>
        <button
          onClick={handleConsumeLatestPlan}
          disabled={isConsuming || items.length === 0}
          className="flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50 transition-colors shadow-sm"
        >
          {isConsuming ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
          Consume Latest Plan
        </button>
      </div>

      {/* Add Item Form */}
      <div className="bg-white dark:bg-gray-900 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 p-6 mb-8">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
          <Plus className="w-5 h-5 text-indigo-500" /> Add New Item
        </h2>
        <form onSubmit={handleAddItem} className="grid grid-cols-1 sm:grid-cols-4 gap-4">
          <div className="sm:col-span-2">
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Item Name</label>
            <input
              type="text"
              placeholder="e.g., Flour, Olive Oil"
              value={newItem.name}
              onChange={(e) => setNewItem({ ...newItem, name: e.target.value })}
              className="w-full px-4 py-2 rounded-lg border border-gray-300 dark:border-gray-600 dark:bg-gray-800 dark:text-white focus:ring-2 focus:ring-indigo-500 outline-none"
              required
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Quantity</label>
            <input
              type="number"
              step="0.1"
              placeholder="1.0"
              value={newItem.quantity}
              onChange={(e) => setNewItem({ ...newItem, quantity: e.target.value })}
              className="w-full px-4 py-2 rounded-lg border border-gray-300 dark:border-gray-600 dark:bg-gray-800 dark:text-white focus:ring-2 focus:ring-indigo-500 outline-none"
              required
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Unit</label>
            <select
              value={newItem.unit}
              onChange={(e) => setNewItem({ ...newItem, unit: e.target.value })}
              className="w-full px-4 py-2 rounded-lg border border-gray-300 dark:border-gray-600 dark:bg-gray-800 dark:text-white focus:ring-2 focus:ring-indigo-500 outline-none"
            >
              <option value="each">each</option>
              <option value="kg">kg</option>
              <option value="g">g</option>
              <option value="L">L</option>
              <option value="ml">ml</option>
              <option value="lb">lb</option>
              <option value="tsp">tsp</option>
              <option value="tbsp">tbsp</option>
              <option value="cup">cup</option>
            </select>
          </div>
          <div className="sm:col-span-4 flex justify-end">
            <button
              type="submit"
              disabled={isAdding}
              className="px-6 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50 transition-colors shadow-sm font-medium"
            >
              {isAdding ? 'Adding...' : 'Add to Pantry'}
            </button>
          </div>
        </form>
      </div>

      {/* Pantry List */}
      {loading ? (
        <div className="flex justify-center py-12">
          <Loader2 className="w-8 h-8 animate-spin text-indigo-500" />
        </div>
      ) : items.length === 0 ? (
        <div className="text-center py-16 bg-gray-50 dark:bg-gray-800/50 rounded-2xl border-2 border-dashed border-gray-200 dark:border-gray-700">
          <Package className="w-12 h-12 text-gray-300 dark:text-gray-600 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-gray-900 dark:text-white">Your pantry is empty</h3>
          <p className="text-gray-500 dark:text-gray-400 mt-1">Add staples to exclude them from your shopping list.</p>
        </div>
      ) : (
        <div className="bg-white dark:bg-gray-900 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left">
              <thead>
                <tr className="bg-gray-50 dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700">
                  <th className="px-6 py-3 text-xs font-bold text-gray-500 dark:text-gray-400 uppercase tracking-wider">Item</th>
                  <th className="px-6 py-3 text-xs font-bold text-gray-500 dark:text-gray-400 uppercase tracking-wider">Quantity</th>
                  <th className="px-6 py-3 text-right text-xs font-bold text-gray-500 dark:text-gray-400 uppercase tracking-wider">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
                {items.map((item) => (
                  <tr key={item.id} className="hover:bg-gray-50 dark:hover:bg-gray-800/50 transition-colors">
                    <td className="px-6 py-4">
                      <div className="font-medium text-gray-900 dark:text-white">{item.name}</div>
                    </td>
                    <td className="px-6 py-4">
                      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-indigo-100 dark:bg-indigo-900/30 text-indigo-800 dark:text-indigo-300">
                        {item.quantity} {item.unit}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-right">
                      <button
                        onClick={() => handleDeleteItem(item.id)}
                        className="text-red-500 hover:text-red-700 dark:hover:text-red-400 p-2 transition-colors"
                        title="Remove item"
                      >
                        <Trash2 className="w-5 h-5" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Info Box */}
      <div className="mt-8 bg-blue-50 dark:bg-blue-900/20 rounded-xl p-4 flex gap-3 border border-blue-100 dark:border-blue-900/30">
        <AlertCircle className="w-5 h-5 text-blue-500 flex-shrink-0 mt-0.5" />
        <div className="text-sm text-blue-700 dark:text-blue-300">
          <p className="font-semibold mb-1">How it works:</p>
          <ul className="list-disc list-inside space-y-1 opacity-90">
            <li>Items here are automatically subtracted from generated shopping lists.</li>
            <li>Use <strong>"Consume Latest Plan"</strong> after cooking to update your stock.</li>
            <li>Unit matching is automatic (e.g., if a recipe needs grams and you have kg).</li>
          </ul>
        </div>
      </div>
    </div>
  );
};

export default PantryPage;
