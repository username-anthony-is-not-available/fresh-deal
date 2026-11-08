import React, { useState, useEffect, useCallback } from 'react';
import { Play, RefreshCw, CheckCircle, XCircle, Clock, Database, Loader2, Trash2, Square, StopCircle, Zap, Globe, Activity, AlertTriangle, ShieldAlert } from 'lucide-react';
import clsx from 'clsx';
import api from '../services/api';
import toast from 'react-hot-toast';

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
  const [healthMetrics, setHealthMetrics] = useState([]);
  const [healthSummary, setHealthSummary] = useState(null);
  const [isLoadingHealth, setIsLoadingHealth] = useState(true);
  const [scraperLogs, setScraperLogs] = useState([]);
  const [isLoadingLogs, setIsLoadingLogs] = useState(false);
  const [logsOffset, setLogsOffset] = useState(0);
  const [hasMoreLogs, setHasMoreLogs] = useState(true);
  const [selectedLog, setSelectedLog] = useState(null);
  const [isLogModalOpen, setIsLogModalOpen] = useState(false);

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

  // Fetch data on mount
  useEffect(() => {
    fetchDealCount();
    fetchHealthData();
    fetchScraperLogs(0, true);
  }, []);

  const fetchScraperLogs = async (offset = 0, reset = false) => {
    setIsLoadingLogs(true);
    try {
      const data = await api.get(`/admin/scrapers/logs?limit=50&offset=${offset}`);
      const logsArray = Array.isArray(data) ? data : (data?.data || []);
      if (reset) {
        setScraperLogs(logsArray);
      } else {
        setScraperLogs(prev => [...(Array.isArray(prev) ? prev : []), ...logsArray]);
      }
      setHasMoreLogs(logsArray.length === 50);
      setLogsOffset(offset);
    } catch (e) {
      console.error('Failed to fetch scraper logs', e);
      toast.error('Failed to load scraper logs');
    } finally {
      setIsLoadingLogs(false);
    }
  };

  const loadMoreLogs = () => {
    fetchScraperLogs(logsOffset + 50);
  };

  const fetchHealthData = async () => {
    setIsLoadingHealth(true);
    try {
      const [metrics, summary] = await Promise.all([
        api.get('/admin/scrapers/health'),
        api.get('/admin/scrapers/health/summary')
      ]);
      setHealthMetrics(metrics);
      setHealthSummary(summary);
    } catch (e) {
      console.error('Failed to fetch health data', e);
    } finally {
      setIsLoadingHealth(false);
    }
  };

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

      // If task completed, refresh data
      if (data.status === 'SUCCESS' || data.status === 'FAILURE') {
        fetchDealCount();
        fetchHealthData();
        fetchScraperLogs(0, true);
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
      console.error('Failed to trigger scraper', e);
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

  const resetCircuitBreaker = async (storeName) => {
    try {
      await api.post(`/admin/scrapers/${storeName}/reset`);
      toast.success(`Circuit breaker for ${storeName} reset`);
      fetchHealthData();
    } catch {
      toast.error(`Failed to reset circuit breaker for ${storeName}`);
    }
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
            onClick={() => {
              fetchDealCount();
              fetchHealthData();
            }}
            className="p-2 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-lg transition-colors"
            title="Refresh dashboard data"
          >
            <RefreshCw className="w-5 h-5" />
          </button>
        </div>
      </div>

      {/* System Health Summary */}
      {healthSummary && (
        <div className={clsx(
          "grid grid-cols-1 md:grid-cols-4 gap-4 p-4 rounded-xl border-2 transition-colors",
          healthSummary.overall_status === 'healthy' ? "bg-green-50 border-green-200" : "bg-amber-50 border-amber-200"
        )}>
          <div className="flex items-center gap-3">
            <div className={clsx(
              "p-2 rounded-lg",
              healthSummary.overall_status === 'healthy' ? "bg-green-100 text-green-600" : "bg-amber-100 text-amber-600"
            )}>
              <Activity className="w-6 h-6" />
            </div>
            <div>
              <p className="text-xs font-semibold uppercase tracking-wider text-gray-500">System Status</p>
              <p className={clsx(
                "text-lg font-bold",
                healthSummary.overall_status === 'healthy' ? "text-green-700" : "text-amber-700"
              )}>
                {healthSummary.overall_status.toUpperCase()}
              </p>
            </div>
          </div>

          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-gray-500">Success Rate</p>
            <p className="text-2xl font-bold text-gray-900">{healthSummary.overall_success_rate}%</p>
          </div>

          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-gray-500">Active Scrapers</p>
            <p className="text-2xl font-bold text-gray-900">{healthSummary.healthy_scrapers} / {healthSummary.total_scrapers}</p>
          </div>

          <div className="flex items-center justify-end">
            <p className="text-xs text-gray-400 italic">
              Last check: {new Date(healthSummary.timestamp).toLocaleTimeString()}
            </p>
          </div>
        </div>
      )}

      {/* Scraper Reliability & Metrics */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-gray-900">Scraper Reliability & Metrics</h2>
          <button
            onClick={fetchHealthData}
            className="text-primary-600 hover:text-primary-700 text-sm font-medium flex items-center gap-1"
          >
            {isLoadingHealth ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
            Refresh Metrics
          </button>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead className="bg-gray-50 text-gray-500 text-xs uppercase tracking-wider">
              <tr>
                <th className="px-6 py-3 font-semibold">Store</th>
                <th className="px-6 py-3 font-semibold">Status</th>
                <th className="px-6 py-3 font-semibold">Success Rate</th>
                <th className="px-6 py-3 font-semibold">Avg. Duration</th>
                <th className="px-6 py-3 font-semibold">Items (7d)</th>
                <th className="px-6 py-3 font-semibold">Last Error</th>
                <th className="px-6 py-3 font-semibold text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {healthMetrics.length === 0 ? (
                <tr>
                  <td colSpan="7" className="px-6 py-8 text-center text-gray-500 italic">
                    {isLoadingHealth ? "Loading metrics..." : "No health data available yet."}
                  </td>
                </tr>
              ) : healthMetrics.map((metric) => (
                <tr key={metric.store_name} className="hover:bg-gray-50 transition-colors">
                  <td className="px-6 py-4">
                    <p className="font-semibold text-gray-900 capitalize">{metric.store_name}</p>
                    <p className="text-xs text-gray-400">Runs: {metric.total_runs}</p>
                  </td>
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-1.5">
                      {metric.status === 'healthy' ? (
                        <CheckCircle className="w-4 h-4 text-green-500" />
                      ) : metric.status === 'critical' ? (
                        <ShieldAlert className="w-4 h-4 text-red-500" />
                      ) : (
                        <AlertTriangle className="w-4 h-4 text-amber-500" />
                      )}
                      <span className={clsx(
                        "text-xs font-bold uppercase",
                        metric.status === 'healthy' ? "text-green-600" :
                        metric.status === 'critical' ? "text-red-600" : "text-amber-600"
                      )}>
                        {metric.status}
                      </span>
                    </div>
                  </td>
                  <td className="px-6 py-4">
                    <div className="w-full bg-gray-100 rounded-full h-1.5 mb-1 max-w-[80px]">
                      <div
                        className={clsx(
                          "h-1.5 rounded-full",
                          metric.success_rate > 90 ? "bg-green-500" :
                          metric.success_rate > 70 ? "bg-amber-500" : "bg-red-500"
                        )}
                        style={{ width: `${metric.success_rate}%` }}
                      ></div>
                    </div>
                    <span className="text-sm font-medium text-gray-700">{metric.success_rate}%</span>
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-600">
                    {metric.avg_duration_seconds}s
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-600">
                    {metric.total_items_scraped}
                  </td>
                  <td className="px-6 py-4">
                    {metric.last_error ? (
                      <div className="max-w-[150px]">
                         <p className="text-xs text-red-500 truncate" title={metric.last_error}>
                           {metric.last_error}
                         </p>
                         <p className="text-[10px] text-gray-400">
                           {new Date(metric.last_run).toLocaleDateString()}
                         </p>
                      </div>
                    ) : (
                      <span className="text-xs text-gray-400">—</span>
                    )}
                  </td>
                  <td className="px-6 py-4 text-right">
                    {(metric.status === 'critical' || metric.status === 'degraded') && (
                      <button
                        onClick={() => resetCircuitBreaker(metric.store_name)}
                        className="p-1.5 bg-amber-50 text-amber-600 hover:bg-amber-100 rounded-lg transition-colors"
                        title="Reset Circuit Breaker"
                      >
                        <RefreshCw className="w-4 h-4" />
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
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

      {/* Scraper Audit Logs */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-gray-900">Scraper Audit Logs</h2>
          <button
            onClick={() => fetchScraperLogs(0, true)}
            className="text-primary-600 hover:text-primary-700 text-sm font-medium flex items-center gap-1"
          >
            {isLoadingLogs && logsOffset === 0 ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
            Refresh Logs
          </button>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead className="bg-gray-50 text-gray-500 text-xs uppercase tracking-wider">
              <tr>
                <th className="px-6 py-3 font-semibold">Store</th>
                <th className="px-6 py-3 font-semibold">Status</th>
                <th className="px-6 py-3 font-semibold">Type</th>
                <th className="px-6 py-3 font-semibold">Duration</th>
                <th className="px-6 py-3 font-semibold">Items</th>
                <th className="px-6 py-3 font-semibold">Timestamp</th>
                <th className="px-6 py-3 font-semibold text-right">Details</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {(!Array.isArray(scraperLogs) || scraperLogs.length === 0) ? (
                <tr>
                  <td colSpan="7" className="px-6 py-8 text-center text-gray-500 italic">
                    {isLoadingLogs ? "Loading logs..." : "No logs available."}
                  </td>
                </tr>
              ) : scraperLogs.map((log) => (
                <tr key={log.id} className="hover:bg-gray-50 transition-colors">
                  <td className="px-6 py-4">
                    <p className="font-semibold text-gray-900 capitalize">{log.store_name}</p>
                    <p className="text-xs text-gray-400">{log.postal_code || 'No PC'}</p>
                  </td>
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-1.5">
                      {log.status === 'success' ? (
                        <CheckCircle className="w-4 h-4 text-green-500" />
                      ) : (
                        <XCircle className="w-4 h-4 text-red-500" />
                      )}
                      <span className={clsx(
                        "text-xs font-bold uppercase",
                        log.status === 'success' ? "text-green-600" : "text-red-600"
                      )}>
                        {log.status}
                      </span>
                    </div>
                  </td>
                  <td className="px-6 py-4">
                    <span className="px-2 py-0.5 bg-gray-100 text-gray-600 text-[10px] font-bold uppercase rounded">
                      {log.scraper_type}
                    </span>
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-600">
                    {log.duration_seconds}s
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-600 font-medium">
                    {log.items_scraped}
                  </td>
                  <td className="px-6 py-4 text-xs text-gray-500">
                    {new Date(log.timestamp).toLocaleString()}
                  </td>
                  <td className="px-6 py-4 text-right">
                    <button
                      onClick={() => {
                        setSelectedLog(log);
                        setIsLogModalOpen(true);
                      }}
                      className="text-primary-600 hover:text-primary-800 text-sm font-medium"
                    >
                      View
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {hasMoreLogs && (
          <div className="p-4 border-t border-gray-100 text-center">
            <button
              onClick={loadMoreLogs}
              disabled={isLoadingLogs}
              className="px-4 py-2 text-sm font-medium text-gray-600 hover:text-gray-900 disabled:opacity-50"
            >
              {isLoadingLogs ? "Loading..." : "Load More Logs"}
            </button>
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

      {/* Log Details Modal */}
      {isLogModalOpen && selectedLog && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl max-h-[90vh] overflow-hidden flex flex-col">
            <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between bg-gray-50/50">
              <div>
                <h3 className="text-xl font-bold text-gray-900 capitalize">
                  {selectedLog.store_name} Log Details
                </h3>
                <p className="text-sm text-gray-500">
                  {new Date(selectedLog.timestamp).toLocaleString()}
                </p>
              </div>
              <button
                onClick={() => setIsLogModalOpen(false)}
                className="p-2 hover:bg-gray-200 rounded-full transition-colors"
              >
                <XCircle className="w-6 h-6 text-gray-400" />
              </button>
            </div>

            <div className="p-6 overflow-y-auto space-y-6">
              <div className="grid grid-cols-2 gap-4">
                <div className="p-3 bg-gray-50 rounded-xl">
                  <p className="text-xs text-gray-500 uppercase font-bold tracking-wider mb-1">Status</p>
                  <div className="flex items-center gap-2">
                    {selectedLog.status === 'success' ? (
                      <CheckCircle className="w-5 h-5 text-green-500" />
                    ) : (
                      <XCircle className="w-5 h-5 text-red-500" />
                    )}
                    <span className={clsx(
                      "font-bold",
                      selectedLog.status === 'success' ? "text-green-700" : "text-red-700"
                    )}>
                      {selectedLog.status.toUpperCase()}
                    </span>
                  </div>
                </div>
                <div className="p-3 bg-gray-50 rounded-xl">
                  <p className="text-xs text-gray-500 uppercase font-bold tracking-wider mb-1">Scraper Type</p>
                  <p className="font-bold text-gray-900 capitalize">{selectedLog.scraper_type}</p>
                </div>
                <div className="p-3 bg-gray-50 rounded-xl">
                  <p className="text-xs text-gray-500 uppercase font-bold tracking-wider mb-1">Duration</p>
                  <p className="font-bold text-gray-900">{selectedLog.duration_seconds}s</p>
                </div>
                <div className="p-3 bg-gray-50 rounded-xl">
                  <p className="text-xs text-gray-500 uppercase font-bold tracking-wider mb-1">Items Scraped</p>
                  <p className="font-bold text-gray-900">{selectedLog.items_scraped}</p>
                </div>
              </div>

              {selectedLog.error_message && (
                <div className="p-4 bg-red-50 border border-red-100 rounded-xl">
                  <p className="text-xs text-red-600 uppercase font-bold tracking-wider mb-2">Error Message</p>
                  <pre className="text-sm text-red-800 whitespace-pre-wrap font-mono bg-white/50 p-3 rounded-lg border border-red-200">
                    {selectedLog.error_message}
                  </pre>
                </div>
              )}

              {selectedLog.proxy_used && (
                <div>
                  <p className="text-xs text-gray-500 uppercase font-bold tracking-wider mb-1">Proxy Used</p>
                  <p className="text-sm font-mono text-gray-700 bg-gray-100 px-2 py-1 rounded inline-block">
                    {selectedLog.proxy_used}
                  </p>
                </div>
              )}

              <div className="pt-4 border-t border-gray-100">
                <p className="text-xs text-gray-500 uppercase font-bold tracking-wider mb-3">Debug Artifacts</p>
                <div className="flex flex-wrap gap-3">
                  {selectedLog.screenshot_path ? (
                    <a
                      href={`${api.defaults.baseURL}/admin/scrapers/logs/${selectedLog.id}/screenshot`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex items-center gap-2 px-4 py-2 bg-blue-50 text-blue-700 hover:bg-blue-100 rounded-lg font-medium transition-colors"
                    >
                      <Globe className="w-4 h-4" />
                      View Screenshot
                    </a>
                  ) : (
                    <button disabled className="flex items-center gap-2 px-4 py-2 bg-gray-50 text-gray-400 rounded-lg font-medium cursor-not-allowed">
                      <Globe className="w-4 h-4" />
                      No Screenshot
                    </button>
                  )}

                  {selectedLog.html_path ? (
                    <a
                      href={`${api.defaults.baseURL}/admin/scrapers/logs/${selectedLog.id}/html`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex items-center gap-2 px-4 py-2 bg-indigo-50 text-indigo-700 hover:bg-indigo-100 rounded-lg font-medium transition-colors"
                    >
                      <Database className="w-4 h-4" />
                      View HTML Snapshot
                    </a>
                  ) : (
                    <button disabled className="flex items-center gap-2 px-4 py-2 bg-gray-50 text-gray-400 rounded-lg font-medium cursor-not-allowed">
                      <Database className="w-4 h-4" />
                      No HTML Snapshot
                    </button>
                  )}
                </div>
              </div>
            </div>

            <div className="px-6 py-4 border-t border-gray-100 bg-gray-50 flex justify-end">
              <button
                onClick={() => setIsLogModalOpen(false)}
                className="px-6 py-2 bg-gray-900 text-white rounded-xl font-bold hover:bg-black transition-all shadow-lg"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default ScrapingDashboardPage;
