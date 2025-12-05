import React from 'react';
import clsx from 'clsx';
import { TrendingDown } from 'lucide-react';

const SavingsBadge = ({ amount, percentage, className }) => {
  if (!amount && !percentage) return null;

  return (
    <span className={clsx(
      "inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-accent-100 text-accent-600",
      className
    )}>
      <TrendingDown className="w-3 h-3 mr-1" />
      {amount && <span>Save ${amount.toFixed(2)}</span>}
      {amount && percentage && <span className="mx-1">•</span>}
      {percentage && <span>{percentage}% Off</span>}
    </span>
  );
};

export default SavingsBadge;
