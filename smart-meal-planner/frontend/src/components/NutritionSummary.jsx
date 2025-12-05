import React from 'react';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts';

const NutritionSummary = ({ data }) => {
  // Mock data structure: [{ name: 'Protein', value: 120, unit: 'g', color: '#8884d8' }, ...]

  return (
    <div className="bg-white p-4 rounded-lg shadow-sm border border-gray-200">
      <h3 className="text-sm font-semibold text-gray-900 mb-4">Daily Average Nutrition</h3>
      <div className="h-48 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} layout="vertical" margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
            <XAxis type="number" hide />
            <YAxis type="category" dataKey="name" tick={{ fontSize: 12 }} width={60} />
            <Tooltip
                cursor={{fill: 'transparent'}}
                contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)' }}
            />
            <Bar dataKey="value" radius={[0, 4, 4, 0]} barSize={20}>
              {data.map((entry, index) => (
                <Cell key={`cell-${index}`} fill={entry.color} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
      <div className="grid grid-cols-3 gap-2 mt-4 text-center">
         {data.map((item) => (
            <div key={item.name} className="bg-gray-50 rounded p-2">
                <div className="text-xs text-gray-500">{item.name}</div>
                <div className="text-sm font-bold text-gray-900">{item.value}{item.unit}</div>
            </div>
         ))}
      </div>
    </div>
  );
};

export default NutritionSummary;
