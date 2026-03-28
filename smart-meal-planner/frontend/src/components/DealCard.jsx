import React from 'react';
import { useTranslation } from 'react-i18next';
import SavingsBadge from './SavingsBadge';
import LoyaltyBadge from './LoyaltyBadge';
import QualityBadge from './QualityBadge';
import { Tag, AlertTriangle, MapPin } from 'lucide-react';

const DealCard = ({ deal }) => {
  const { t } = useTranslation();
  const { product, store, loyalty_program, loyalty_points, effective_price, quality_level, quality_score, image_url, sale_info, distance } = deal;

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 overflow-hidden hover:shadow-md transition-shadow flex flex-col h-full">
      {image_url && (
        <div className="h-48 overflow-hidden bg-gray-100 dark:bg-gray-700 flex items-center justify-center">
          <img
            src={image_url}
            alt={product.name}
            className="w-full h-full object-contain"
            onError={(e) => { e.target.style.display = 'none'; }}
          />
        </div>
      )}
      <div className="p-4 flex-grow">
        <div className="flex justify-between items-start mb-2">
           <QualityBadge level={quality_level} score={quality_score} />
           {quality_level === 'poor' && (
             <AlertTriangle className="w-4 h-4 text-yellow-500" title="Possible quality issues detected" />
           )}
        </div>
        <div className="flex justify-between items-start">
          <div className="flex-1">
            <span className="text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wider font-semibold">{product.category}</span>
            <h3 className="text-lg font-medium text-gray-900 dark:text-white mt-1">{product.name}</h3>
            <div className="text-sm text-gray-500 dark:text-gray-400 mt-1 flex items-center gap-1">
              <span className="font-medium text-gray-700 dark:text-gray-300">{store.name}</span>
              {distance !== null && distance !== undefined && (
                <span className="flex items-center text-xs text-gray-400 dark:text-gray-500">
                  • <MapPin className="w-3 h-3 ml-1 mr-0.5" /> {distance}km
                </span>
              )}
            </div>
          </div>
          {deal.discount_pct > 0 && (
            <div className="bg-accent-500 text-white text-xs font-bold px-2 py-1 rounded ml-2">
              {deal.discount_pct}%
            </div>
          )}
        </div>

        <div className="mt-4">
          <div className="flex items-baseline gap-2">
            <span className="text-2xl font-bold text-primary-600">${deal.price.toFixed(2)}</span>
            {deal.original_price && (
              <span className="text-sm text-gray-400 dark:text-gray-500 line-through">${deal.original_price.toFixed(2)}</span>
            )}
            <span className="text-sm text-gray-500 dark:text-gray-400">/ {product.unit_type}</span>
          </div>

          {effective_price < deal.price && (
            <div className="text-sm text-green-600 dark:text-green-400 font-semibold mt-1">
              {t('effective_price')}: ${effective_price.toFixed(2)}
            </div>
          )}

          {sale_info && (
            <div className="mt-2 text-sm text-accent-700 dark:text-accent-300 bg-accent-50 dark:bg-accent-900/20 px-2 py-1 rounded inline-block font-medium">
              {sale_info}
            </div>
          )}
        </div>
      </div>

      <div className="px-4 pb-4 mt-auto">
        <div className="h-6 mb-2">
            <LoyaltyBadge program={loyalty_program} points={loyalty_points} />
        </div>
        <div className="pt-4 border-t border-gray-100 dark:border-gray-700 flex justify-between items-center">
          <SavingsBadge
            amount={deal.original_price ? deal.original_price - deal.price : null}
          />
          <div className="text-xs text-gray-400 dark:text-gray-500">
            {t('valid_until')} {new Date(deal.valid_until).toLocaleDateString()}
          </div>
        </div>
      </div>
    </div>
  );
};

export default DealCard;
