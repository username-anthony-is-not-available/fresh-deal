import React, { useEffect, useState } from 'react';
import DealCard from '../components/DealCard';
import { Search, Filter } from 'lucide-react';

const DealsPage = () => {
  const [deals, setDeals] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('');

  // We need to fetch deals. The current backend doesn't have a direct "list all deals" endpoint
  // other than seed, but we can assume we'd add one or just use seed for now.
  // I will add a temporary fetch logic. For now, let's Mock it on client side if API is missing,
  // but better to actually fetch. I'll implement a simple endpoint in next steps.
  // For now, I'll assume an endpoint /api/deals exists (I'll add it in backend step).

  useEffect(() => {
    fetchDeals();
  }, []);

  const fetchDeals = async () => {
    try {
      // NOTE: I will need to add this endpoint to the backend in the next major step.
      // For now, this will 404 until I add it.
      const res = await fetch('http://localhost:8000/api/deals');
      if (res.ok) {
        const data = await res.json();
        setDeals(data);
      } else {
        // Fallback for dev if endpoint not ready yet
        console.warn("Deals endpoint not ready");
        setDeals([]);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
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
           <button className="flex items-center gap-2 px-4 py-2 border border-gray-300 rounded-lg bg-white hover:bg-gray-50 text-gray-700">
              <Filter className="w-4 h-4" />
              Filter
           </button>
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
             onClick={async () => {
                await fetch('http://localhost:8000/api/data/seed', { method: 'POST' });
                fetchDeals();
             }}
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
