import React, { useEffect, useState } from 'react';
import DealCard from '../components/DealCard';
import { Search, Filter } from 'lucide-react';
import api from '../services/api';

const DealsPage = () => {
  const [deals, setDeals] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('');
  const [sortBy, setSortBy] = useState('');

  useEffect(() => {
    fetchDeals();
  }, [sortBy]);

  const fetchDeals = async () => {
    try {
      const params = new URLSearchParams({
        sort_by: sortBy,
      }).toString();
      const data = await api.get(`/deals?${params}`);
      setDeals(data);
    } catch (e) {
      console.warn("Failed to fetch deals", e);
      setDeals([]);
    } finally {
      setLoading(false);
    }
  };

  const seedData = async () => {
    try {
      await api.post('/data/seed');
      fetchDeals();
    } catch (e) {
      console.error("Failed to seed data", e);
    }
  };

  const filteredDeals = deals.filter(d =>
     d.product.name.toLowerCase().includes(filter.toLowerCase()) ||
     d.product.category.toLowerCase().includes(filter.toLowerCase())
  );

  return (
    <div>
      <div className="flex flex-col md:flex-row md:items-center justify-between mb-8 gap-4">
        <div>
           <h1 className="text-3xl font-bold text-gray-900">Weekly Flyers & Deals</h1>
           <p className="text-gray-500 mt-1">Found {deals.length} active deals near you</p>
        </div>

        <div className="flex gap-2">
           <div className="relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-4 h-4" />
              <input
                 type="text"
                 placeholder="Search deals..."
                 className="pl-9 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 outline-none"
                 value={filter}
                 onChange={(e) => setFilter(e.target.value)}
              />
           </div>
           <select
             value={sortBy}
             onChange={(e) => setSortBy(e.target.value)}
             className="flex items-center gap-2 px-4 py-2 border border-gray-300 rounded-lg bg-white hover:bg-gray-50 text-gray-700"
           >
             <option value="">Sort by</option>
             <option value="category">Category</option>
           </select>
        </div>
      </div>

      {loading ? (
        <div className="text-center py-12">
           <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600 mx-auto mb-4"></div>
           <p className="text-gray-500">Loading deals...</p>
        </div>
      ) : filteredDeals.length > 0 ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
          {filteredDeals.map((deal) => (
            <DealCard
               key={deal.id}
               product={deal.product}
               deal={deal}
               store={deal.store}
            />
          ))}
        </div>
      ) : (
        <div className="text-center py-12 bg-white rounded-lg border border-dashed border-gray-300">
           <p className="text-gray-500">No deals found. Try seeding the database first.</p>
           <button
             onClick={seedData}
             className="mt-4 text-primary-600 font-medium hover:underline"
           >
             Seed Mock Data
           </button>
        </div>
      )}
    </div>
  );
};

export default DealsPage;
