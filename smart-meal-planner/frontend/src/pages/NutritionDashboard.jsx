import React, { useState, useEffect } from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { getNutritionGoal, getNutritionSummary } from '../services/nutritionService';

const NutritionDashboard = () => {
    const [goal, setGoal] = useState(null);
    const [summary, setSummary] = useState([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const fetchData = async () => {
            try {
                const goalData = await getNutritionGoal();
                setGoal(goalData);

                const endDate = new Date();
                const startDate = new Date();
                startDate.setDate(endDate.getDate() - 6);

                const summaryData = await getNutritionSummary(startDate.toISOString().split('T')[0], endDate.toISOString().split('T')[0]);
                setSummary(summaryData);
            } catch (error) {
                console.error("Error fetching nutrition data:", error);
            } finally {
                setLoading(false);
            }
        };

        fetchData();
    }, []);

    if (loading) {
        return <div>Loading...</div>;
    }

    return (
        <div className="p-4 sm:p-6 lg:p-8">
            <h1 className="text-2xl font-bold mb-4">Nutrition Dashboard</h1>

            {goal && (
                <div className="mb-8 p-4 bg-white rounded-lg shadow">
                    <h2 className="text-xl font-semibold mb-2">Your Nutrition Goals ({goal.goal_type})</h2>
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                        <p><strong>Calories:</strong> {goal.target_calories || 'Not set'} kcal</p>
                        <p><strong>Protein:</strong> {goal.target_protein || 'Not set'} g</p>
                        <p><strong>Carbs:</strong> {goal.target_carbs || 'Not set'} g</p>
                        <p><strong>Fats:</strong> {goal.target_fats || 'Not set'} g</p>
                    </div>
                </div>
            )}

            <div className="p-4 bg-white rounded-lg shadow">
                <h2 className="text-xl font-semibold mb-4">Last 7 Days Nutrition Summary</h2>
                <ResponsiveContainer width="100%" height={400}>
                    <BarChart data={summary}>
                        <CartesianGrid strokeDasharray="3 3" />
                        <XAxis dataKey="date" />
                        <YAxis />
                        <Tooltip />
                        <Legend />
                        <Bar dataKey="calories" fill="#8884d8" name="Calories (kcal)" />
                        <Bar dataKey="protein" fill="#82ca9d" name="Protein (g)" />
                        <Bar dataKey="carbs" fill="#ffc658" name="Carbs (g)" />
                        <Bar dataKey="fats" fill="#ff8042" name="Fats (g)" />
                    </BarChart>
                </ResponsiveContainer>
            </div>
        </div>
    );
};

export default NutritionDashboard;
