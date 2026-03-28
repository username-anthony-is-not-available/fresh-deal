import React from 'react';
import { Award } from 'lucide-react';
import { useTranslation } from 'react-i18next';

const programColors = {
  "PC Optimum": "bg-red-100 dark:bg-red-900/30 text-red-800 dark:text-red-400",
  "Scene+": "bg-black dark:bg-gray-700 text-white dark:text-gray-200",
  "Moi": "bg-green-100 dark:bg-green-900/30 text-green-800 dark:text-green-400",
  "AIR MILES": "bg-blue-100 dark:bg-blue-900/30 text-blue-800 dark:text-blue-400",
};

const LoyaltyBadge = ({ program, points }) => {
  const { t } = useTranslation();
  if (!program || !points) {
    return null;
  }

  const colorClasses = programColors[program] || "bg-gray-100 text-gray-800";

  return (
    <div className={`flex items-center gap-1.5 px-2 py-1 rounded-full text-xs font-medium ${colorClasses}`}>
      <Award className="h-4 w-4" />
      <span>{t('earn')} <strong>{points}</strong> {program} {t('points_suffix', { count: points })}</span>
    </div>
  );
};

export default LoyaltyBadge;
