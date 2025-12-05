import React from 'react';
import { Check, ShoppingCart } from 'lucide-react';
import clsx from 'clsx';

const ShoppingListItem = ({ item, isChecked, onToggle }) => {
  return (
    <div
      className={clsx(
        "flex items-center justify-between p-3 border-b border-gray-100 last:border-0 hover:bg-gray-50 transition-colors cursor-pointer",
        isChecked ? "bg-gray-50" : "bg-white"
      )}
      onClick={onToggle}
    >
      <div className="flex items-center gap-3">
        <div
          className={clsx(
            "w-5 h-5 rounded border flex items-center justify-center transition-colors",
            isChecked ? "bg-primary-500 border-primary-500" : "border-gray-300 bg-white"
          )}
        >
          {isChecked && <Check className="w-3.5 h-3.5 text-white" />}
        </div>
        <div className={clsx("flex flex-col", isChecked && "opacity-50")}>
           <span className={clsx("text-sm font-medium text-gray-900", isChecked && "line-through")}>
             {item.name}
           </span>
           <span className="text-xs text-gray-500">
             {item.quantity} {item.unit} • Best price at <span className="font-semibold text-primary-600">{item.store}</span>
           </span>
        </div>
      </div>

      <div className="text-right">
        <div className={clsx("font-medium text-gray-900", isChecked && "opacity-50")}>
           ${item.price.toFixed(2)}
        </div>
        {item.is_deal && (
           <div className="text-xs text-accent-600 font-medium">On Sale</div>
        )}
      </div>
    </div>
  );
};

export default ShoppingListItem;
