import React from 'react';
import { useTranslation } from 'react-i18next';
import SavingsBadge from './SavingsBadge';
import { Tag } from 'lucide-react';

const DealCard = ({ product, deal, store }) => {
  const { t } = useTranslation();
  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden hover:shadow-md transition-shadow">
      <div className="p-4">
        <div className="flex justify-between items-start">
          <div>
            <span className="text-xs text-gray-500 uppercase tracking-wider font-semibold">{product.category}</span>
            <h3 className="text-lg font-medium text-gray-900 mt-1">{product.name}</h3>
            <div className="text-sm text-gray-500 mt-1 flex items-center gap-1">
              <span className="font-medium text-gray-700">{store.name}</span>
            </div>
          </div>
          {deal.discount_pct && (
            <div className="bg-accent-500 text-white text-xs font-bold px-2 py-1 rounded">
              {deal.discount_pct}%
            </div>
          )}
        </div>

        <div className="mt-4 flex items-end gap-2">
          <span className="text-2xl font-bold text-primary-600">${deal.price.toFixed(2)}</span>
          {deal.original_price && (
            <span className="text-sm text-gray-400 line-through mb-1">${deal.original_price.toFixed(2)}</span>
          )}
          <span className="text-sm text-gray-500 mb-1">/ {product.unit_type}</span>
        </div>

        <div className="mt-4 pt-4 border-t border-gray-100 flex justify-between items-center">
             <SavingsBadge
                amount={deal.original_price ? deal.original_price - deal.price : null}
             />
             <div className="text-xs text-gray-400">
                {t('valid_until')} {new Date(deal.valid_until).toLocaleDateString()}
             </div>
        </div>
      </div>
    </div>
  );
};

export default DealCard;
