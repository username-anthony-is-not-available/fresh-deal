import React from 'react';
import { CheckCircle, AlertCircle, TrendingDown, Info } from 'lucide-react';

const QualityBadge = ({ level, score }) => {
  const configs = {
    excellent: {
      color: 'bg-green-100 dark:bg-green-900/30 text-green-800 dark:text-green-400 border-green-200 dark:border-green-800',
      icon: <TrendingDown className="w-3 h-3 mr-1" />,
      label: 'Excellent Deal'
    },
    good: {
      color: 'bg-blue-100 dark:bg-blue-900/30 text-blue-800 dark:text-blue-400 border-blue-200 dark:border-blue-800',
      icon: <CheckCircle className="w-3 h-3 mr-1" />,
      label: 'Good Value'
    },
    average: {
      color: 'bg-gray-100 dark:bg-gray-700 text-gray-800 dark:text-gray-300 border-gray-200 dark:border-gray-600',
      icon: <Info className="w-3 h-3 mr-1" />,
      label: 'Average'
    },
    poor: {
      color: 'bg-yellow-100 dark:bg-yellow-900/30 text-yellow-800 dark:text-yellow-400 border-yellow-200 dark:border-yellow-800',
      icon: <AlertCircle className="w-3 h-3 mr-1" />,
      label: 'Poor Value'
    },
    noise: {
      color: 'bg-red-100 dark:bg-red-900/30 text-red-800 dark:text-red-400 border-red-200 dark:border-red-800',
      icon: <AlertCircle className="w-3 h-3 mr-1" />,
      label: 'Marketing Noise'
    }
  };

  const config = configs[level] || configs.average;

  return (
    <div className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border ${config.color}`} title={`Quality Score: ${score}/100`}>
      {config.icon}
      {config.label}
    </div>
  );
};

export default QualityBadge;
