import React, { useState, useEffect, useCallback } from 'react';
import { Play, RefreshCw, CheckCircle, XCircle, Clock, Database, Loader2, Trash2, Square, StopCircle, Zap, Globe } from 'lucide-react';
import clsx from 'clsx';
import api from '../services/api';

// Available Canadian stores in Flipp API
const FLIPP_STORES = [
  { key: 'metro', name: 'Metro' },
  { key: 'maxi', name: 'Maxi' },
  { key: 'provigo', name: 'Provigo' },
  { key: 'super_c', name: 'Super C' },
  { key: 'loblaws', name: 'Loblaws' },
  { key: 'walmart', name: 'Walmart' },
  { key: 'food_basics', name: 'Food Basics' },
  { key: 'iga', name: 'IGA' },
  { key: 'no_frills', name: 'No Frills' },
  { key: 'real_canadian_superstore', name: 'Real Canadian Superstore' },
  { key: 'adonis', name: 'Adonis' },
  { key: 'costco', name: 'Costco' },
];

const ScrapingDashboardPage = () => {
  const [tasks, setTasks] = useState([]);
  const [isSeeding, setIsSeeding] = useState(false);
  const [isScraping, setIsScraping] = useState({});
  const [dealCount, setDealCount] = useState(null);
  
  // Flipp scraper options
  const [selectedStores, setSelectedStores] = useState(['metro', 'maxi', 'walmart', 'super_c']);
  const [postalCode, setPostalCode] = useState('H4T1V6');
  const [itemLimit, setItemLimit] = useState(100);

  const legacyScrapers = [
    { id: 'metro', name: 'Metro (Playwright)', endpoint: '/admin/scrape/metro', color: 'blue', legacy: true },
    { id: 'super_c', name: 'Super C (Playwright)', endpoint: '/admin/scrape/super_c', color: 'green', legacy: true },
    { id: 'maxi', name: 'Maxi (Playwright)', endpoint: '/admin/scrape/maxi', color: 'red', legacy: true },
    { id: 'provigo', name: 'Provigo (Playwright)', endpoint: '/admin/scrape/provigo', color: 'orange', legacy: true },
    { id: 'iga', name: 'IGA (Playwright)', endpoint: '/admin/scrape/iga', color: 'red', legacy: true },
    { id: 'walmart', name: 'Walmart (Playwright)', endpoint: '/admin/scrape/walmart', color: 'blue', legacy: true },
    { id: 'adonis', name: 'Adonis (Flipp API)', endpoint: '/admin/scrape/adonis', color: 'purple', legacy: true },
    { id: 'costco', name: 'Costco (Playwright)', endpoint: '/admin/scrape/costco', color: 'blue', legacy: true },
  ];

  // Fetch deal count on mount
  useEffect(() => {
    fetchDealCount();
  }, []);

  // Poll active tasks
  useEffect(() => {
    const activeTasks = tasks.filter(t => t.status === 'Processing' || t.status === 'Pending' || t.status === 'STARTED');
    if (activeTasks.length === 0) return;

    const interval = setInterval(() => {
      activeTasks.forEach(task => pollTask(task.task_id));
    }, 2000);

    return () => clearInterval(interval);
  }, [tasks]);

  const fetchDealCount = async () => {
    try {
      const data = await api.get('/deals');
      setDealCount(data.length);
    } catch (e) {
      console.error('Failed to fetch deal count', e);
    }
  };

  const pollTask = useCallback(async (taskId) => {
    try {
      const data = await api.get(`/tasks/${taskId}`);
      setTasks(prev => prev.map(t =>
        t.task_id === taskId
          ? { ...t, status: data.status, result: data.result, error: data.error }
          : t
      ));

      // If task completed, refresh deal count
      if (data.status === 'SUCCESS' || data.status === 'FAILURE') {
        fetchDealCount();
      }
    } catch (e) {
      console.error('Failed to poll task', e);
    }
  }, []);

  const triggerScrape = async (scraper) => {
    setIsScraping(prev => ({ ...prev, [scraper.id]: true }));
    try {
      const data = await api.post(scraper.endpoint);
      const newTask = {
        task_id: data.task_id,
        scraper: scraper.name,
        status: data.status,
        startedAt: new Date().toISOString(),
        result: null,
        error: null,
        meta: data
      };
      setTasks(prev => [newTask, ...prev]);
    } catch (e) {
      console.error('Failed to trigger scrape', e);
    } finally {
      setIsScraping(prev => ({ ...prev, [scraper.id]: false }));
    }
  };

  const triggerFlippScrape = async () => {
    setIsScraping(prev => ({ ...prev, flipp: true }));
    try {
      const body = {
        stores: selectedStores.length > 0 ? selectedStores : null,
        postal_code: postalCode,
        limit: itemLimit
      };
      const data = await api.post('/admin/scrape/flipp', body);
      const storeNames = selectedStores.length > 0
        ? selectedStores.map(s => FLIPP_STORES.find(fs => fs.key === s)?.name).join(', ')
        : 'All stores';
      const newTask = {
        task_id: data.task_id,
        scraper: `Flipp API (${storeNames})`,
        status: data.status,
        startedAt: new Date().toISOString(),
        result: null,
        error: null,
        meta: data
      };
      setTasks(prev => [newTask, ...prev]);
    } catch (e) {
      console.error('Failed to trigger Flipp scrape', e);
    } finally {
      setIsScraping(prev => ({ ...prev, flipp: false }));
    }
  };

  const toggleStore = (storeKey) => {
    setSelectedStores(prev => 
      prev.includes(storeKey)
        ? prev.filter(s => s !== storeKey)
        : [...prev, storeKey]
    );
  };

  const selectAllStores = () => {
    setSelectedStores(FLIPP_STORES.map(s => s.key));
  };

  const clearStoreSelection = () => {
    setSelectedStores([]);
  };

  const seedMockData = async () => {
    setIsSeeding(true);
    try {
      const data = await api.post('/data/seed');
      const newTask = {
        task_id: `seed-${Date.now()}`,
        scraper: 'Mock Seeder',
        status: 'SUCCESS',
        startedAt: new Date().toISOString(),
        result: data.message,
        error: null
      };
      setTasks(prev => [newTask, ...prev]);
      fetchDealCount();
    } catch (e) {
      console.error('Failed to seed data', e);
    } finally {
      setIsSeeding(false);
    }
  };

  const clearTasks = () => {
    setTasks([]);
  };

  const stopTask = async (taskId) => {
    try {
      await api.post(`/tasks/${taskId}/stop`);
      setTasks(prev => prev.map(t =>
        t.task_id === taskId
          ? { ...t, status: 'Stopped' }
          : t
      ));
    } catch (e) {
      console.error('Failed to stop task', e);
    }
  };

  const isTaskRunning = (status) => {
    return ['Processing', 'Pending', 'STARTED'].includes(status);
  };

  const getStatusIcon = (status) => {
    switch (status) {
      case 'SUCCESS':
        return <CheckCircle className="w-5 h-5 text-green-500" />;
      case 'FAILURE':
      case 'Failed':
        return <XCircle className="w-5 h-5 text-red-500" />;
      case 'Stopped':
      case 'REVOKED':
        return <StopCircle className="w-5 h-5 text-orange-500" />;
      case 'Processing':
      case 'Pending':
      case 'STARTED':
        return <Loader2 className="w-5 h-5 text-blue-500 animate-spin" />;
      default:
        return <Clock className="w-5 h-5 text-gray-400" />;
    }
  };

  const getStatusBadge = (status) => {
    const styles = {
      SUCCESS: 'bg-green-100 text-green-800',
      FAILURE: 'bg-red-100 text-red-800',
      Failed: 'bg-red-100 text-red-800',
      Stopped: 'bg-orange-100 text-orange-800',
      REVOKED: 'bg-orange-100 text-orange-800',
      Processing: 'bg-blue-100 text-blue-800',
      Pending: 'bg-yellow-100 text-yellow-800',
      STARTED: 'bg-blue-100 text-blue-800',
    };
    return (
      <span className={clsx('px-2 py-1 rounded-full text-xs font-medium', styles[status] || 'bg-gray-100 text-gray-800')}>
        {status}
      </span>
    );
  };

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Scraping Dashboard</h1>
          <p className="text-gray-500 mt-1">Manage deal scrapers and data imports</p>
        </div>
        <div className="flex items-center gap-3">
          <div className="bg-white border border-gray-200 rounded-lg px-4 py-2 flex items-center gap-2">
            <Database className="w-5 h-5 text-gray-400" />
            <span className="text-sm text-gray-600">
              {dealCount !== null ? `${dealCount} deals in database` : 'Loading...'}
            </span>
          </div>
          <button
            onClick={fetchDealCount}
            className="p-2 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-lg transition-colors"
            title="Refresh count"
          >
            <RefreshCw className="w-5 h-5" />
          </button>
        </div>
      </div>

      {/* Flipp API Scraper - Recommended */}
      <div className="bg-white rounded-xl shadow-sm border-2 border-green-300 p-6">
        <div className="flex items-center gap-3 mb-4">
          <div className="p-2 bg-green-100 rounded-lg">
            <Zap className="w-6 h-6 text-green-600" />
          </div>
          <div>
            <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
              Flipp API Scraper
              <span className="px-2 py-0.5 bg-green-100 text-green-800 text-xs font-medium rounded-full">
                Recommended
              </span>
            </h2>
            <p className="text-sm text-gray-500">
              Uses the Flipp public API - Fast, reliable, no bot protection issues
            </p>
          </div>
        </div>

        {/* Store Selection */}
        <div className="mb-4">
          <div className="flex items-center justify-between mb-2">
            <label className="text-sm font-medium text-gray-700">Select Stores</label>
            <div className="flex gap-2">
              <button
                onClick={selectAllStores}
                className="text-xs text-blue-600 hover:text-blue-800"
              >
                Select All
              </button>
              <span className="text-gray-300">|</span>
              <button
                onClick={clearStoreSelection}
                className="text-xs text-gray-500 hover:text-gray-700"
              >
                Clear
              </button>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            {FLIPP_STORES.map(store => (
              <button
                key={store.key}
                onClick={() => toggleStore(store.key)}
                className={clsx(
                  'px-3 py-1.5 rounded-full text-sm font-medium transition-colors',
                  selectedStores.includes(store.key)
                    ? 'bg-green-600 text-white'
                    : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                )}
              >
                {store.name}
              </button>
            ))}
          </div>
        </div>

        {/* Options */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Postal Code
            </label>
            <input
              type="text"
              value={postalCode}
              onChange={(e) => setPostalCode(e.target.value.toUpperCase())}
              placeholder="H4T1V6"
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-green-500"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Max Items
            </label>
            <input
              type="number"
              value={itemLimit}
              onChange={(e) => setItemLimit(parseInt(e.target.value) || 50)}
              min={10}
              max={500}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-green-500"
            />
          </div>
        </div>

        {/* Run Button */}
        <button
          onClick={triggerFlippScrape}
          disabled={isScraping.flipp || selectedStores.length === 0}
          className={clsx(
            'w-full flex items-center justify-center gap-2 px-4 py-3 rounded-lg font-medium transition-colors',
            isScraping.flipp || selectedStores.length === 0
              ? 'bg-gray-100 text-gray-400 cursor-not-allowed'
              : 'bg-green-600 text-white hover:bg-green-700'
          )}
        >
          {isScraping.flipp ? (
            <>
              <Loader2 className="w-5 h-5 animate-spin" />
              Scraping...
            </>
          ) : (
            <>
              <Globe className="w-5 h-5" />
              Scrape {selectedStores.length} Store{selectedStores.length !== 1 ? 's' : ''} via Flipp API
            </>
          )}
        </button>
      </div>

      {/* Other Scraper Controls */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Other Data Sources</h2>
        
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {/* Mock Data Seeder */}
          <div className="border border-gray-200 rounded-lg p-4 hover:border-primary-300 transition-colors">
            <div className="flex items-start justify-between">
              <div>
                <h3 className="font-medium text-gray-900">Mock Data Generator</h3>
                <p className="text-sm text-gray-500 mt-1">
                  Generate ~100 realistic deals for all Quebec stores
                </p>
              </div>
              <span className="px-2 py-1 bg-purple-100 text-purple-800 text-xs font-medium rounded-full">
                Mock
              </span>
            </div>
            <button
              onClick={seedMockData}
              disabled={isSeeding}
              className={clsx(
                'mt-4 w-full flex items-center justify-center gap-2 px-4 py-2 rounded-lg font-medium transition-colors',
                isSeeding
                  ? 'bg-gray-100 text-gray-400 cursor-not-allowed'
                  : 'bg-purple-600 text-white hover:bg-purple-700'
              )}
            >
              {isSeeding ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Seeding...
                </>
              ) : (
                <>
                  <Database className="w-4 h-4" />
                  Seed Mock Data
                </>
              )}
            </button>
          </div>

          {/* Legacy Browser Scrapers */}
          {legacyScrapers.map((scraper) => (
            <div key={scraper.id} className="border border-gray-200 rounded-lg p-4 hover:border-primary-300 transition-colors">
              <div className="flex items-start justify-between">
                <div>
                  <h3 className="font-medium text-gray-900">{scraper.name}</h3>
                  <p className="text-sm text-gray-500 mt-1">
                    Browser automation (often blocked)
                  </p>
                </div>
                <span className="px-2 py-1 bg-orange-100 text-orange-800 text-xs font-medium rounded-full">
                  Legacy
                </span>
              </div>
              <button
                onClick={() => triggerScrape(scraper)}
                disabled={isScraping[scraper.id]}
                className={clsx(
                  'mt-4 w-full flex items-center justify-center gap-2 px-4 py-2 rounded-lg font-medium transition-colors',
                  isScraping[scraper.id]
                    ? 'bg-gray-100 text-gray-400 cursor-not-allowed'
                    : 'bg-orange-600 text-white hover:bg-orange-700'
                )}
              >
                {isScraping[scraper.id] ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Starting...
                  </>
                ) : (
                  <>
                    <Play className="w-4 h-4" />
                    Run Scraper
                  </>
                )}
              </button>
            </div>
          ))}

          {/* No more placeholder - we have all stores via Flipp! */}
        </div>
      </div>

      {/* Task History */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-gray-900">Task History</h2>
          {tasks.length > 0 && (
            <button
              onClick={clearTasks}
              className="flex items-center gap-1 text-sm text-gray-500 hover:text-gray-700"
            >
              <Trash2 className="w-4 h-4" />
              Clear
            </button>
          )}
        </div>

        {tasks.length === 0 ? (
          <div className="text-center py-8 text-gray-500">
            <Clock className="w-12 h-12 mx-auto mb-3 text-gray-300" />
            <p>No tasks yet. Run a scraper to see task history.</p>
          </div>
        ) : (
          <div className="space-y-3">
            {tasks.map((task, idx) => (
              <div
                key={task.task_id || idx}
                className="flex items-center justify-between p-4 bg-gray-50 rounded-lg"
              >
                <div className="flex items-center gap-3">
                  {getStatusIcon(task.status)}
                  <div>
                    <p className="font-medium text-gray-900">{task.scraper}</p>
                    <p className="text-sm text-gray-500">
                      {new Date(task.startedAt).toLocaleTimeString()}
                      {task.result && typeof task.result === 'string' && (
                        <span className="ml-2 text-green-600">• {task.result}</span>
                      )}
                      {task.error && (
                        <span className="ml-2 text-red-600">• {task.error}</span>
                      )}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  {isTaskRunning(task.status) && (
                    <button
                      onClick={() => stopTask(task.task_id)}
                      className="flex items-center gap-1 px-3 py-1.5 bg-red-100 text-red-700 hover:bg-red-200 rounded-lg text-sm font-medium transition-colors"
                      title="Stop task"
                    >
                      <Square className="w-3 h-3" />
                      Stop
                    </button>
                  )}
                  {getStatusBadge(task.status)}
                  <span className="text-xs text-gray-400 font-mono">
                    {task.task_id?.substring(0, 8)}...
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Info Box */}
      <div className="bg-green-50 border border-green-200 rounded-lg p-4">
        <h3 className="font-medium text-green-800 mb-2">🚀 About Flipp API Scraper</h3>
        <ul className="text-sm text-green-700 space-y-1">
          <li>• <strong>Flipp API</strong>: Uses the public Flipp API (flipp.com) to get real flyer deals from 10+ Canadian stores.</li>
          <li>• <strong>No Bot Detection</strong>: Unlike browser scraping, this API method doesn't get blocked by Cloudflare.</li>
          <li>• <strong>Real Data</strong>: Returns actual current weekly deals with prices, sale info, and images.</li>
          <li>• <strong>Fast</strong>: ~10x faster than browser automation since it's a direct API call.</li>
        </ul>
      </div>

      <div className="bg-amber-50 border border-amber-200 rounded-lg p-4">
        <h3 className="font-medium text-amber-800 mb-2">ℹ️ Other Options</h3>
        <ul className="text-sm text-amber-700 space-y-1">
          <li>• <strong>Mock Data</strong>: Instantly generates realistic test deals for development/testing.</li>
          <li>• <strong>Metro (Playwright)</strong>: Legacy browser scraper - often blocked by Cloudflare protection.</li>
          <li>• Background tasks require Redis and Celery workers to be running.</li>
        </ul>
      </div>
    </div>
  );
};

export default ScrapingDashboardPage;
