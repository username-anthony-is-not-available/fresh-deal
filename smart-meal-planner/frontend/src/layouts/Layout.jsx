import React from 'react';
import { NavLink, Outlet } from 'react-router-dom';
import { Home, ShoppingCart, Calendar, Tag, Settings, Menu, Activity, Heart, BookOpen, MessageSquare, Package } from 'lucide-react';
import clsx from 'clsx';
import { useTranslation } from 'react-i18next';
import NetworkStatusIndicator from '../components/NetworkStatusIndicator';
import ThemeToggle from '../components/ThemeToggle';

const Layout = () => {
  const { t } = useTranslation();
  const [isMobileMenuOpen, setIsMobileMenuOpen] = React.useState(false);

  const navItems = [
    { name: t('home'), path: '/', icon: Home },
    { name: t('deals'), path: '/deals', icon: Tag },
    { name: t('recipes'), path: '/recipes', icon: BookOpen },
    { name: t('meal_plan'), path: '/plan', icon: Calendar },
    { name: t('shopping_list'), path: '/list', icon: ShoppingCart },
    { name: t('pantry'), path: '/pantry', icon: Package },
    { name: t('favorites', 'My Favorites'), path: '/favorites', icon: Heart },
    { name: t('feedback', 'Feedback'), path: '/feedback', icon: MessageSquare },
    { name: t('scraping'), path: '/scraping', icon: Activity },
    { name: t('settings'), path: '/settings', icon: Settings },
  ];

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-800 flex flex-col">
      <NetworkStatusIndicator />
      {/* Header */}
      <header className="bg-white dark:bg-gray-900 shadow-sm sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between h-16">
            <div className="flex items-center">
              <span className="text-2xl font-bold text-primary-600 flex items-center gap-2">
                 🥗 SmartMeal
              </span>
            </div>

            {/* Desktop Nav */}
            <div className="hidden sm:flex space-x-8 items-center">
              {navItems.map((item) => (
                <NavLink
                  key={item.name}
                  to={item.path}
                  className={({ isActive }) =>
                    clsx(
                      'flex items-center gap-2 px-1 pt-1 border-b-2 text-sm font-medium transition-colors',
                      isActive
                        ? 'border-primary-500 text-gray-900 dark:text-white'
                        : 'border-transparent text-gray-500 dark:text-gray-400 hover:border-gray-300 dark:hover:border-gray-500 hover:text-gray-700 dark:hover:text-white'
                    )
                  }
                >
                  <item.icon className="w-4 h-4" />
                  {item.name}
                </NavLink>
              ))}
              <ThemeToggle />
            </div>

            {/* Mobile Menu Button */}
            <div className="flex items-center sm:hidden">
              <ThemeToggle />
              <button
                onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
                className="p-2 rounded-md text-gray-400 dark:text-gray-400 hover:text-gray-500 dark:hover:text-white hover:bg-gray-100 dark:hover:bg-gray-700 focus:outline-none"
              >
                <Menu className="w-6 h-6" />
              </button>
            </div>
          </div>
        </div>

        {/* Mobile Nav */}
        {isMobileMenuOpen && (
          <div className="sm:hidden bg-white dark:bg-gray-900 border-t border-gray-200 dark:border-gray-700">
            <div className="pt-2 pb-3 space-y-1">
              {navItems.map((item) => (
                <NavLink
                  key={item.name}
                  to={item.path}
                  onClick={() => setIsMobileMenuOpen(false)}
                  className={({ isActive }) =>
                    clsx(
                      'block pl-3 pr-4 py-2 border-l-4 text-base font-medium',
                      isActive
                        ? 'bg-primary-50 dark:bg-primary-900/10 border-primary-500 text-primary-700 dark:text-white'
                        : 'border-transparent text-gray-500 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-800 hover:border-gray-300 dark:hover:border-gray-600 hover:text-gray-700 dark:hover:text-white'
                    )
                  }
                >
                  <div className="flex items-center gap-3">
                    <item.icon className="w-5 h-5" />
                    {item.name}
                  </div>
                </NavLink>
              ))}
            </div>
          </div>
        )}
      </header>

      {/* Main Content */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <Outlet />
      </main>

      {/* Footer */}
      <footer className="bg-white dark:bg-gray-900 border-t border-gray-200 dark:border-gray-700 mt-auto">
        <div className="max-w-7xl mx-auto py-6 px-4 sm:px-6 lg:px-8">
          <p className="text-center text-sm text-gray-500 dark:text-gray-400">
            &copy; 2025 Smart Meal Planner. Quebec Edition.
          </p>
        </div>
      </footer>
    </div>
  );
};

export default Layout;