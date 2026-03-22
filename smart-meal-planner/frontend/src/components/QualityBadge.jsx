import React from 'react';
import { CheckCircle, AlertCircle, TrendingDown, Info } from 'lucide-react';

const QualityBadge = ({ level, score }) => {
  const configs = {
    excellent: {
      color: 'bg-green-100 text-green-800 border-green-200',
      icon: <TrendingDown className="w-3 h-3 mr-1" />,
      label: 'Excellent Deal'
    },
    good: {
      color: 'bg-blue-100 text-blue-800 border-blue-200',
      icon: <CheckCircle className="w-3 h-3 mr-1" />,
      label: 'Good Value'
    },
    average: {
      color: 'bg-gray-100 text-gray-800 border-gray-200',
      icon: <Info className="w-3 h-3 mr-1" />,
      label: 'Average'
    },
    poor: {
      color: 'bg-yellow-100 text-yellow-800 border-yellow-200',
      icon: <AlertCircle className="w-3 h-3 mr-1" />,
      label: 'Poor Value'
    },
    noise: {
      color: 'bg-red-100 text-red-800 border-red-200',
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
