import React, { useState, useEffect, useMemo } from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts';
import { getNutritionGoal, getNutritionSummary } from '../services/nutritionService';
import { Activity, Target, PieChart as PieChartIcon, Info } from 'lucide-react';
import clsx from 'clsx';

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

    const weeklyAverages = useMemo(() => {
        if (!summary.length) return null;
        const count = summary.length;
        return {
            calories: Math.round(summary.reduce((acc, curr) => acc + curr.calories, 0) / count),
            protein: Math.round(summary.reduce((acc, curr) => acc + curr.protein, 0) / count),
            carbs: Math.round(summary.reduce((acc, curr) => acc + curr.carbs, 0) / count),
            fats: Math.round(summary.reduce((acc, curr) => acc + (curr.fats || 0), 0) / count),
        };
    }, [summary]);

    const macroData = useMemo(() => {
        if (!weeklyAverages) return [];
        return [
            { name: 'Protein', value: weeklyAverages.protein * 4, color: '#82ca9d' },
            { name: 'Carbs', value: weeklyAverages.carbs * 4, color: '#ffc658' },
            { name: 'Fats', value: weeklyAverages.fats * 9, color: '#ff8042' },
        ];
    }, [weeklyAverages]);

    const getGoalStatus = (current, target) => {
        if (!target) return 'neutral';
        const percent = (current / target) * 100;
        if (percent >= 90 && percent <= 110) return 'success';
        if (percent < 90) return 'warning';
        return 'danger';
    };

    if (loading) {
        return (
            <div className="flex items-center justify-center min-h-[60vh]">
                <div className="animate-spin rounded-full h-12 w-12 border-4 border-primary-200 border-t-primary-600"></div>
            </div>
        );
    }

    return (
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-3xl font-bold text-gray-900 flex items-center gap-3">
                        <Activity className="text-primary-600" />
                        Nutritional Dashboard
                    </h1>
                    <p className="text-gray-500 mt-1">Track your macro distribution and muscle-building goals.</p>
                </div>
            </div>

            {/* Top Stats: Weekly Average vs Goals */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
                {[
                    { label: 'Calories', current: weeklyAverages?.calories, target: goal?.target_calories, unit: 'kcal' },
                    { label: 'Protein', current: weeklyAverages?.protein, target: goal?.target_protein, unit: 'g' },
                    { label: 'Carbs', current: weeklyAverages?.carbs, target: goal?.target_carbs, unit: 'g' },
                    { label: 'Fats', current: weeklyAverages?.fats, target: goal?.target_fats, unit: 'g' },
                ].map((stat) => {
                    const status = getGoalStatus(stat.current, stat.target);
                    return (
                        <div key={stat.label} className="bg-white p-6 rounded-2xl shadow-sm border border-gray-100 flex flex-col justify-between">
                            <div>
                                <p className="text-sm font-medium text-gray-500 uppercase tracking-wider">{stat.label}</p>
                                <div className="flex items-baseline gap-2 mt-2">
                                    <span className="text-3xl font-bold text-gray-900">{stat.current || 0}</span>
                                    <span className="text-gray-400 text-sm">{stat.unit} avg</span>
                                </div>
                            </div>
                            <div className="mt-4 pt-4 border-t border-gray-50">
                                <div className="flex justify-between text-xs mb-1.5">
                                    <span className="text-gray-500">Target: {stat.target || '--'} {stat.unit}</span>
                                    <span className={clsx(
                                        "font-bold uppercase tracking-tighter",
                                        status === 'success' ? "text-green-600" : status === 'warning' ? "text-amber-500" : status === 'danger' ? "text-red-500" : "text-gray-400"
                                    )}>
                                        {stat.target ? `${Math.round((stat.current / stat.target) * 100)}%` : 'No Goal'}
                                    </span>
                                </div>
                                <div className="w-full bg-gray-100 rounded-full h-2 overflow-hidden">
                                    <div
                                        className={clsx(
                                            "h-full rounded-full transition-all duration-1000",
                                            status === 'success' ? "bg-green-500" : status === 'warning' ? "bg-amber-400" : status === 'danger' ? "bg-red-500" : "bg-gray-300"
                                        )}
                                        style={{ width: `${Math.min(100, (stat.current / (stat.target || 1)) * 100)}%` }}
                                    />
                                </div>
                            </div>
                        </div>
                    );
                })}
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
                {/* Daily Progress Chart */}
                <div className="lg:col-span-2 bg-white p-6 rounded-2xl shadow-sm border border-gray-100">
                    <h2 className="text-xl font-bold text-gray-900 mb-6 flex items-center gap-2">
                        <Target className="text-primary-500 w-5 h-5" />
                        Daily Macro Intake
                    </h2>
                    <div className="h-[400px] w-full">
                        <ResponsiveContainer width="100%" height="100%">
                            <BarChart data={summary} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f3f4f6" />
                                <XAxis
                                    dataKey="date"
                                    axisLine={false}
                                    tickLine={false}
                                    tick={{ fill: '#9ca3af', fontSize: 12 }}
                                    dy={10}
                                />
                                <YAxis
                                    axisLine={false}
                                    tickLine={false}
                                    tick={{ fill: '#9ca3af', fontSize: 12 }}
                                />
                                <Tooltip
                                    cursor={{ fill: '#f9fafb' }}
                                    contentStyle={{ borderRadius: '12px', border: 'none', boxShadow: '0 10px 15px -3px rgb(0 0 0 / 0.1)' }}
                                />
                                <Legend wrapperStyle={{ paddingTop: '20px' }} />
                                <Bar dataKey="protein" fill="#82ca9d" name="Protein (g)" radius={[4, 4, 0, 0]} />
                                <Bar dataKey="carbs" fill="#ffc658" name="Carbs (g)" radius={[4, 4, 0, 0]} />
                                <Bar dataKey="fats" fill="#ff8042" name="Fats (g)" radius={[4, 4, 0, 0]} />
                            </BarChart>
                        </ResponsiveContainer>
                    </div>
                </div>

                {/* Macro Breakdown Pie Chart */}
                <div className="bg-white p-6 rounded-2xl shadow-sm border border-gray-100">
                    <h2 className="text-xl font-bold text-gray-900 mb-6 flex items-center gap-2">
                        <PieChartIcon className="text-primary-500 w-5 h-5" />
                        Caloric Split
                    </h2>
                    <div className="h-[300px]">
                        <ResponsiveContainer width="100%" height="100%">
                            <PieChart>
                                <Pie
                                    data={macroData}
                                    cx="50%"
                                    cy="50%"
                                    innerRadius={60}
                                    outerRadius={80}
                                    paddingAngle={5}
                                    dataKey="value"
                                >
                                    {macroData.map((entry, index) => (
                                        <Cell key={`cell-${index}`} fill={entry.color} />
                                    ))}
                                </Pie>
                                <Tooltip
                                    formatter={(value) => `${value} kcal`}
                                    contentStyle={{ borderRadius: '12px', border: 'none', boxShadow: '0 10px 15px -3px rgb(0 0 0 / 0.1)' }}
                                />
                            </PieChart>
                        </ResponsiveContainer>
                    </div>
                    <div className="mt-4 space-y-3">
                        {macroData.map((macro) => (
                            <div key={macro.name} className="flex items-center justify-between">
                                <div className="flex items-center gap-2">
                                    <div className="w-3 h-3 rounded-full" style={{ backgroundColor: macro.color }} />
                                    <span className="text-sm font-medium text-gray-700">{macro.name}</span>
                                </div>
                                <span className="text-sm font-bold text-gray-900">
                                    {Math.round((macro.value / (macroData.reduce((acc, curr) => acc + curr.value, 0) || 1)) * 100)}%
                                </span>
                            </div>
                        ))}
                    </div>
                    <div className="mt-8 p-4 bg-blue-50 rounded-xl border border-blue-100 flex gap-3">
                        <Info className="w-5 h-5 text-blue-500 flex-shrink-0" />
                        <p className="text-xs text-blue-800 leading-relaxed">
                            Recommended muscle-building split: 30% Protein, 40% Carbs, 30% Fats. Adjust your goals in Settings.
                        </p>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default NutritionDashboard;
