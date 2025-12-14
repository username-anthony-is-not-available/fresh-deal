import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { Save } from 'lucide-react';
import toast from 'react-hot-toast';
import SettingsService from '../services/SettingsService';
import { useAuth } from '../context/AuthContext.jsx';
import NutritionGoalSettings from '../components/NutritionGoalSettings';

const SettingsPage = () => {
  const { t, i18n } = useTranslation();
  const [formData, setFormData] = useState({
    postal_code: 'H4T 1V6',
    household_size: 4,
    dietary_preferences: 'None',
    budget_limit: 200,
    excluded_ingredients: ''
  });

  const { currentUser } = useAuth();

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
  };

  useEffect(() => {
    if (!currentUser) return;

    const fetchSettings = async () => {
      try {
        const response = await SettingsService.getUserSettings(currentUser.id);
        setFormData({
          postal_code: response.data.postal_code,
          household_size: response.data.household_size,
          dietary_preferences: response.data.dietary_preferences || 'None',
          budget_limit: 200, // Not in model, keeping in state for now
          excluded_ingredients: '' // Not in model
        });
      } catch (error) {
        toast.error(t('failed_to_load_settings'));
        console.error(error);
      }
    };
    fetchSettings();
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    const settingsToUpdate = {
      postal_code: formData.postal_code,
      household_size: parseInt(formData.household_size, 10),
      dietary_preferences: formData.dietary_preferences
    };

    const toastId = toast.loading(t('saving_settings'));
    try {
      await SettingsService.updateUserSettings(currentUser.id, settingsToUpdate);
      toast.success(t('settings_saved_successfully'), { id: toastId });
    } catch (error) {
      toast.error(t('failed_to_save_settings'), { id: toastId });
      console.error(error);
    }
  };

  return (
    <div className="max-w-2xl mx-auto">
      <h1 className="text-3xl font-bold text-gray-900 mb-8">{t('settings_title')}</h1>

      <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
        <form onSubmit={handleSubmit} className="p-6 space-y-6">

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
             <div>
                <label htmlFor="postal_code" className="block text-sm font-medium text-gray-700 mb-1">{t('postal_code')}</label>
                <input
                  id="postal_code"
                  type="text"
                  name="postal_code"
                  value={formData.postal_code}
                  onChange={handleChange}
                  className="block w-full rounded-lg border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm p-2.5 border"
                />
             </div>

             <div>
                <label htmlFor="household_size" className="block text-sm font-medium text-gray-700 mb-1">{t('household_size')}</label>
                <select
                   id="household_size"
                   name="household_size"
                   value={formData.household_size}
                   onChange={handleChange}
                   className="block w-full rounded-lg border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm p-2.5 border"
                >
                  <option value="1">{t('person_one')}</option>
                  <option value="2">{t('people_two')}</option>
                  <option value="3">{t('people_three')}</option>
                  <option value="4">{t('people_four')}</option>
                  <option value="5">{t('people_five_plus')}</option>
                </select>
             </div>
          </div>

          <div>
             <label htmlFor="dietary_preferences" className="block text-sm font-medium text-gray-700 mb-1">{t('dietary_preferences')}</label>
             <select
                id="dietary_preferences"
                name="dietary_preferences"
                value={formData.dietary_preferences}
                onChange={handleChange}
                className="block w-full rounded-lg border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm p-2.5 border"
             >
               <option value="None">{t('no_restrictions')}</option>
               <option value="Vegetarian">{t('vegetarian')}</option>
               <option value="Vegan">{t('vegan')}</option>
               <option value="Gluten-Free">{t('gluten_free')}</option>
               <option value="Keto">{t('keto')}</option>
               <option value="Paleo">{t('paleo')}</option>
             </select>
          </div>

          <div>
             <label htmlFor="excluded_ingredients" className="block text-sm font-medium text-gray-700 mb-1">{t('excluded_ingredients')}</label>
             <input
                id="excluded_ingredients"
                type="text"
                name="excluded_ingredients"
                value={formData.excluded_ingredients}
                onChange={handleChange}
                placeholder="e.g. peanuts, cilantro, shellfish"
                className="block w-full rounded-lg border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm p-2.5 border"
             />
          </div>

          <div>
             <label htmlFor="budget_limit" className="block text-sm font-medium text-gray-700 mb-1">{t('weekly_budget')}</label>
             <div className="relative rounded-md shadow-sm">
                <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3">
                   <span className="text-gray-500 sm:text-sm">$</span>
                </div>
                <input
                   id="budget_limit"
                   type="number"
                   name="budget_limit"
                   value={formData.budget_limit}
                   onChange={handleChange}
                   className="block w-full rounded-lg border-gray-300 pl-7 pr-12 focus:border-primary-500 focus:ring-primary-500 sm:text-sm p-2.5 border"
                />
             </div>
          </div>

          <div>
            <label htmlFor="language" className="block text-sm font-medium text-gray-700 mb-1">{t('language')}</label>
            <select
              id="language"
              name="language"
              value={i18n.language}
              onChange={(e) => i18n.changeLanguage(e.target.value)}
              className="block w-full rounded-lg border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm p-2.5 border"
            >
              <option value="en">English</option>
              <option value="fr">Français</option>
            </select>
          </div>

          <div className="pt-4 border-t border-gray-100 flex justify-end">
             <button
                type="submit"
                className="flex items-center gap-2 bg-primary-600 text-white px-6 py-2.5 rounded-lg font-medium hover:bg-primary-700 shadow-sm"
             >
                <Save className="w-4 h-4" />
                {t('save_changes')}
             </button>
          </div>
        </form>
      </div>
      <NutritionGoalSettings />
    </div>
  );
};

export default SettingsPage;
