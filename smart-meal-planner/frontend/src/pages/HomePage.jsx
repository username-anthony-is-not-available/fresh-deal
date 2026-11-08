import React, { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { ChefHat, ShoppingBag, DollarSign, RefreshCw, CheckCircle2, Clock, Sparkles } from "lucide-react";
import api from "../services/api";
import toast from "react-hot-toast";

const HomePage = () => {
  const [isScraping, setIsScraping] = useState(false);
  const [lastScraped, setLastScraped] = useState(null);
  const [activeDealsCount, setActiveDealsCount] = useState(null);

  useEffect(() => {
    fetchLastScrapedInfo();
  }, []);

  const fetchLastScrapedInfo = async () => {
    try {
      const data = await api.get("/scrape/last-scraped");
      if (data) {
        setLastScraped(data.last_scraped_at);
        setActiveDealsCount(data.total_active_deals);
      }
    } catch (e) {
      console.warn("Could not fetch last scraped timestamp", e);
    }
  };

  const handleScrapeLocalFlyers = async () => {
    setIsScraping(true);
    const toastId = toast.loading("Scraping Quebec flyers (Metro, Maxi, Super C, IGA, Walmart)...");
    try {
      const res = await api.post("/scrape/trigger");
      toast.success("Quebec weekly flyers scraped & updated successfully!", { id: toastId });
      if (res && res.timestamp) {
        setLastScraped(res.timestamp);
      }
      fetchLastScrapedInfo();
    } catch (err) {
      console.error("Flyer scrape failed", err);
      toast.error("Failed to scrape flyers. Please try again or check logs.", { id: toastId });
    } finally {
      setIsScraping(false);
    }
  };

  const formattedDate = lastScraped
    ? new Date(lastScraped).toLocaleDateString("en-CA", {
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      })
    : null;

  return (
    <div className="max-w-4xl mx-auto">
      <div className="text-center mb-8">
        <h1 className="text-4xl md:text-5xl font-bold text-gray-900 dark:text-white mb-6 transition-colors">
          Eat Healthy. <span className="text-primary-600">Save Money.</span>
          <br />
          Shop Smarter.
        </h1>
        <p className="text-xl text-gray-600 dark:text-gray-400 mb-8 max-w-2xl mx-auto transition-colors">
          Automatically discover grocery deals in Quebec, generate personalized
          meal plans, and save $30–$50 on your weekly shopping bill.
        </p>

        {/* One-Click Scrape Local Flyers Action Card */}
        <div className="bg-gradient-to-r from-emerald-500/10 via-primary-500/10 to-teal-500/10 border border-emerald-500/30 dark:border-emerald-500/20 rounded-2xl p-6 mb-10 shadow-sm max-w-2xl mx-auto backdrop-blur-sm">
          <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
            <div className="text-left">
              <div className="flex items-center gap-2">
                <Sparkles className="w-5 h-5 text-emerald-600 dark:text-emerald-400" />
                <h3 className="text-lg font-bold text-gray-900 dark:text-white">
                  Local Quebec Flyers
                </h3>
              </div>
              <p className="text-sm text-gray-600 dark:text-gray-400 mt-1 flex items-center gap-1.5">
                <Clock className="w-4 h-4 text-gray-400" />
                {formattedDate ? (
                  <span>
                    Last updated: <strong className="text-gray-800 dark:text-gray-200">{formattedDate}</strong>
                    {activeDealsCount !== null && ` (${activeDealsCount} active deals)`}
                  </span>
                ) : (
                  <span>Flyers ready for weekly sync</span>
                )}
              </p>
            </div>

            <button
              id="scrape-flyers-now-btn"
              onClick={handleScrapeLocalFlyers}
              disabled={isScraping}
              className={`flex items-center gap-2 px-5 py-2.5 rounded-xl font-semibold text-sm text-white shadow transition-all ${
                isScraping
                  ? "bg-gray-400 cursor-not-allowed"
                  : "bg-emerald-600 hover:bg-emerald-700 active:scale-95 shadow-emerald-600/20"
              }`}
            >
              <RefreshCw className={`w-4 h-4 ${isScraping ? "animate-spin" : ""}`} />
              {isScraping ? "Scraping Circulars..." : "Scrape Local Flyers Now"}
            </button>
          </div>
        </div>

        <div className="flex justify-center gap-8 mb-12">
          <div className="flex flex-col items-center">
            <div className="bg-primary-100 dark:bg-primary-900/20 p-3 rounded-full mb-2 transition-colors">
              <DollarSign className="w-6 h-6 text-primary-600" />
            </div>
            <span className="font-medium dark:text-gray-300">Find Best Deals</span>
          </div>
          <div className="flex flex-col items-center">
            <div className="bg-accent-100 dark:bg-accent-900/20 p-3 rounded-full mb-2 transition-colors">
              <ChefHat className="w-6 h-6 text-accent-600" />
            </div>
            <span className="font-medium dark:text-gray-300">AI Meal Planning</span>
          </div>
          <div className="flex flex-col items-center">
            <div className="bg-blue-100 dark:bg-blue-900/20 p-3 rounded-full mb-2 transition-colors">
              <ShoppingBag className="w-6 h-6 text-blue-600" />
            </div>
            <span className="font-medium dark:text-gray-300">Smart Lists</span>
          </div>
        </div>
      </div>

      <div className="text-center">
        <Link
          to="/register"
          className="bg-primary-600 text-white py-3 px-8 rounded-lg hover:bg-primary-700 font-bold text-lg shadow-md transition-transform transform hover:-translate-y-0.5"
        >
          Get Started
        </Link>
        <p className="mt-4 text-gray-600 dark:text-gray-400">
          Already have an account?{" "}
          <Link to="/login" className="text-primary-600 hover:underline">
            Login
          </Link>
        </p>
      </div>
    </div>
  );
};

export default HomePage;
