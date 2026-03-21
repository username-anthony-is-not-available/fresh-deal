import React, { useState, useEffect } from 'react';
import { Save } from 'lucide-react';
import toast from 'react-hot-toast';
import { getNutritionGoal, createOrUpdateNutritionGoal } from '../services/nutritionService';

const NutritionGoalSettings = () => {
    const [formData, setFormData] = useState({
        goal_type: 'maintenance',
        target_calories: '',
        target_protein: '',
        target_carbs: '',
        target_fats: '',
    });

    useEffect(() => {
        const fetchGoal = async () => {
            try {
                const response = await getNutritionGoal();
                if (response) {
                    setFormData({
                        goal_type: response.goal_type,
                        target_calories: response.target_calories || '',
                        target_protein: response.target_protein || '',
                        target_carbs: response.target_carbs || '',
                        target_fats: response.target_fats || '',
                    });
                }
            } catch {
                // It's okay if it fails, means no goal is set yet
                console.log("No existing nutrition goal found.");
            }
        };
        fetchGoal();
    }, []);

    const handleChange = (e) => {
        const { name, value } = e.target;
        setFormData(prev => ({ ...prev, [name]: value }));
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        const goalData = {
            goal_type: formData.goal_type,
            target_calories: parseFloat(formData.target_calories) || null,
            target_protein: parseFloat(formData.target_protein) || null,
            target_carbs: parseFloat(formData.target_carbs) || null,
            target_fats: parseFloat(formData.target_fats) || null,
        };

        const toastId = toast.loading('Saving nutrition goals...');
        try {
            await createOrUpdateNutritionGoal(goalData);
            toast.success('Nutrition goals saved successfully!', { id: toastId });
        } catch (error) {
            toast.error('Failed to save nutrition goals.', { id: toastId });
            console.error(error);
        }
    };

    return (
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden mt-8">
            <h2 className="text-xl font-bold text-gray-900 p-6">Nutrition Goals</h2>
            <form onSubmit={handleSubmit} className="p-6 space-y-6">
                <div>
                    <label htmlFor="goal_type" className="block text-sm font-medium text-gray-700 mb-1">Goal Type</label>
                    <select
                        id="goal_type"
                        name="goal_type"
                        value={formData.goal_type}
                        onChange={handleChange}
                        className="block w-full rounded-lg border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm p-2.5 border"
                    >
                        <option value="maintenance">Maintenance</option>
                        <option value="weight_loss">Weight Loss</option>
                        <option value="muscle_gain">Muscle Gain</option>
                    </select>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <div>
                        <label htmlFor="target_calories" className="block text-sm font-medium text-gray-700 mb-1">Target Calories (kcal)</label>
                        <input
                            id="target_calories"
                            type="number"
                            name="target_calories"
                            value={formData.target_calories}
                            onChange={handleChange}
                            className="block w-full rounded-lg border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm p-2.5 border"
                        />
                    </div>
                    <div>
                        <label htmlFor="target_protein" className="block text-sm font-medium text-gray-700 mb-1">Target Protein (g)</label>
                        <input
                            id="target_protein"
                            type="number"
                            name="target_protein"
                            value={formData.target_protein}
                            onChange={handleChange}
                            className="block w-full rounded-lg border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm p-2.5 border"
                        />
                    </div>
                    <div>
                        <label htmlFor="target_carbs" className="block text-sm font-medium text-gray-700 mb-1">Target Carbs (g)</label>
                        <input
                            id="target_carbs"
                            type="number"
                            name="target_carbs"
                            value={formData.target_carbs}
                            onChange={handleChange}
                            className="block w-full rounded-lg border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm p-2.5 border"
                        />
                    </div>
                    <div>
                        <label htmlFor="target_fats" className="block text-sm font-medium text-gray-700 mb-1">Target Fats (g)</label>
                        <input
                            id="target_fats"
                            type="number"
                            name="target_fats"
                            value={formData.target_fats}
                            onChange={handleChange}
                            className="block w-full rounded-lg border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm p-2.5 border"
                        />
                    </div>
                </div>

                <div className="pt-4 border-t border-gray-100 flex justify-end">
                    <button
                        type="submit"
                        className="flex items-center gap-2 bg-primary-600 text-white px-6 py-2.5 rounded-lg font-medium hover:bg-primary-700 shadow-sm"
                    >
                        <Save className="w-4 h-4" />
                        Save Nutrition Goals
                    </button>
                </div>
            </form>
        </div>
    );
};

export default NutritionGoalSettings;
