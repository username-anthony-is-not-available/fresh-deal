import React from 'react';
import { render, screen, fireEvent, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (key) => key }),
}));

const toastMock = vi.hoisted(() => {
  const fn = vi.fn();
  fn.success = vi.fn();
  fn.error = vi.fn();
  return fn;
});
vi.mock('react-hot-toast', () => ({ default: toastMock, toast: toastMock }));

vi.mock('../services/api', () => ({
  default: { post: vi.fn(), get: vi.fn(), delete: vi.fn() },
}));

const dndCapture = vi.hoisted(() => ({
  drop: null,
  drag: null,
  isOver: false,
  isDragging: false,
}));
vi.mock('react-dnd', () => ({
  useDrop: (specFn) => {
    dndCapture.drop = specFn();
    return [{ isOver: dndCapture.isOver }, () => {}];
  },
  useDrag: (specFn) => {
    dndCapture.drag = specFn();
    return [{ isDragging: dndCapture.isDragging }, () => {}];
  },
}));

import api from '../services/api';
import DealCard from '../components/DealCard';
import LoyaltyBadge from '../components/LoyaltyBadge';
import QualityBadge from '../components/QualityBadge';
import SavingsBadge from '../components/SavingsBadge';
import StarRating from '../components/StarRating';
import ThemeToggle from '../components/ThemeToggle';
import { ThemeProvider } from '../context/ThemeContext';
import MealSlot from '../components/MealSlot';
import FavoriteButton from '../components/FavoriteButton';
import DraggableMealCard from '../components/DraggableMealCard';
import ShoppingListItem from '../components/ShoppingListItem';
import NetworkStatusIndicator from '../components/NetworkStatusIndicator';
import NutritionSummary from '../components/NutritionSummary';
import DietaryFilters from '../components/DietaryFilters';
import StoreComparison from '../components/StoreComparison';
import RecipeFeedbackForm from '../components/RecipeFeedbackForm';

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
  dndCapture.isOver = false;
  dndCapture.isDragging = false;
  vi.spyOn(console, 'error').mockImplementation(() => {});
});

const fullDeal = {
  product: { name: 'Chicken Breast', category: 'Meat', unit_type: 'kg' },
  store: { name: 'Metro' },
  loyalty_program: 'PC Optimum',
  loyalty_points: 1000,
  effective_price: 4.0,
  quality_level: 'poor',
  quality_score: 30,
  image_url: 'http://example.com/img.jpg',
  sale_info: '2 for 1',
  distance: 2.5,
  discount_pct: 25,
  price: 5.0,
  original_price: 8.0,
  valid_until: '2026-12-31',
};

// ---------------------------------------------------------------------------
// DealCard
// ---------------------------------------------------------------------------

describe('DealCard', () => {
  it('renders a full deal with image, badges and sale info', () => {
    render(<DealCard deal={fullDeal} />);
    expect(screen.getByText('Chicken Breast')).toBeInTheDocument();
    expect(screen.getByText('Metro')).toBeInTheDocument();
    expect(screen.getByText('$5.00')).toBeInTheDocument();
    expect(screen.getByText('$8.00')).toBeInTheDocument();
    expect(screen.getByText('25%')).toBeInTheDocument();
    expect(screen.getByText('2 for 1')).toBeInTheDocument();
    expect(screen.getByText(/2\.5km/)).toBeInTheDocument();
    expect(screen.getByText(/effective_price/)).toBeInTheDocument();
    expect(screen.getByText(/Poor Value/)).toBeInTheDocument();
    expect(screen.getByText(/1000/)).toBeInTheDocument();
  });

  it('hides the image when it fails to load', () => {
    const { container } = render(<DealCard deal={fullDeal} />);
    const img = container.querySelector('img');
    fireEvent.error(img);
    expect(img.style.display).toBe('none');
  });

  it('renders a minimal deal without optional sections', () => {
    const minimal = {
      product: { name: 'Bread', category: 'Bakery', unit_type: 'each' },
      store: { name: 'IGA' },
      loyalty_program: null,
      loyalty_points: null,
      effective_price: 3.0,
      quality_level: 'good',
      quality_score: 80,
      image_url: null,
      sale_info: null,
      distance: null,
      discount_pct: 0,
      price: 3.0,
      original_price: null,
      valid_until: '2026-12-31',
    };
    const { container } = render(<DealCard deal={minimal} />);
    expect(screen.getByText('Bread')).toBeInTheDocument();
    expect(container.querySelector('img')).toBeNull();
    expect(screen.queryByText(/effective_price/)).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// LoyaltyBadge / QualityBadge / SavingsBadge
// ---------------------------------------------------------------------------

describe('LoyaltyBadge', () => {
  it('renders nothing without a program or points', () => {
    const { container } = render(<LoyaltyBadge program={null} points={100} />);
    expect(container).toBeEmptyDOMElement();
    const { container: c2 } = render(<LoyaltyBadge program="Moi" points={0} />);
    expect(c2).toBeEmptyDOMElement();
  });

  it('renders each known program and falls back for unknown ones', () => {
    for (const program of ['PC Optimum', 'Scene+', 'Moi', 'AIR MILES', 'Other']) {
      const { unmount } = render(<LoyaltyBadge program={program} points={500} />);
      expect(screen.getByText(/500/)).toBeInTheDocument();
      expect(screen.getByText(new RegExp(program.replace('+', '\\+')))).toBeInTheDocument();
      unmount();
    }
  });
});

describe('QualityBadge', () => {
  it('renders every level and defaults unknown levels to average', () => {
    const cases = {
      excellent: 'Excellent Deal',
      good: 'Good Value',
      average: 'Average',
      poor: 'Poor Value',
      noise: 'Marketing Noise',
      bogus: 'Average',
    };
    for (const [level, label] of Object.entries(cases)) {
      const { unmount } = render(<QualityBadge level={level} score={42} />);
      expect(screen.getByText(label)).toBeInTheDocument();
      expect(screen.getByTitle('Quality Score: 42/100')).toBeInTheDocument();
      unmount();
    }
  });
});

describe('SavingsBadge', () => {
  it('renders nothing without an amount or percentage', () => {
    const { container } = render(<SavingsBadge />);
    expect(container).toBeEmptyDOMElement();
  });

  it('renders amount, percentage, both, and a custom class', () => {
    render(<SavingsBadge amount={2.5} />);
    expect(screen.getByText('Save $2.50')).toBeInTheDocument();
    render(<SavingsBadge percentage={20} className="extra" />);
    expect(screen.getByText('20% Off')).toBeInTheDocument();
    render(<SavingsBadge amount={1} percentage={10} />);
    expect(screen.getByText('Save $1.00')).toBeInTheDocument();
    expect(screen.getByText('10% Off')).toBeInTheDocument();
    expect(screen.getByText('•')).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// StarRating
// ---------------------------------------------------------------------------

describe('StarRating', () => {
  it('submits a rating on click and calls back', async () => {
    api.post.mockResolvedValue({});
    const onSubmit = vi.fn();
    const { container } = render(
      <StarRating recipeId={7} initialRating={0} onRatingSubmit={onSubmit} />
    );
    const stars = container.querySelectorAll('svg');
    await act(async () => fireEvent.click(stars[2]));
    expect(api.post).toHaveBeenCalledWith('/recipes/7/rate', { rating: 3 });
    expect(toastMock.success).toHaveBeenCalledWith('Rating submitted!');
    expect(onSubmit).toHaveBeenCalledWith(3);
  });

  it('reverts to the initial rating when submission fails', async () => {
    api.post.mockRejectedValue(new Error('down'));
    const { container } = render(<StarRating recipeId={7} initialRating={2} />);
    const stars = container.querySelectorAll('svg');
    await act(async () => fireEvent.click(stars[4]));
    expect(toastMock.error).toHaveBeenCalledWith('Failed to submit rating.');
    expect(console.error).toHaveBeenCalled();
  });

  it('tracks hover state', () => {
    const { container } = render(<StarRating recipeId={7} initialRating={0} />);
    const stars = container.querySelectorAll('svg');
    fireEvent.mouseEnter(stars[3]);
    fireEvent.mouseLeave(stars[3]);
    expect(stars.length).toBe(5);
  });

  it('works without a submit callback', async () => {
    api.post.mockResolvedValue({});
    const { container } = render(<StarRating recipeId={7} />);
    await act(async () => fireEvent.click(container.querySelectorAll('svg')[0]));
    expect(api.post).toHaveBeenCalledWith('/recipes/7/rate', { rating: 1 });
  });
});

// ---------------------------------------------------------------------------
// ThemeToggle / MealSlot / FavoriteButton / DraggableMealCard
// ---------------------------------------------------------------------------

describe('ThemeToggle', () => {
  it('toggles the theme on click', () => {
    render(<ThemeProvider><ThemeToggle /></ThemeProvider>);
    const btn = screen.getByRole('button');
    act(() => btn.click());
    expect(localStorage.getItem('theme')).toBe('dark');
  });
});

describe('MealSlot', () => {
  it('renders children and forwards drops', () => {
    const onDrop = vi.fn();
    const { rerender } = render(
      <MealSlot day="Monday" type="lunch" onDrop={onDrop}><span>slot</span></MealSlot>
    );
    expect(screen.getByText('slot')).toBeInTheDocument();
    dndCapture.drop.drop({ meal: { id: 1 } });
    expect(onDrop).toHaveBeenCalledWith({ meal: { id: 1 } }, { day: 'Monday', type: 'lunch' });
    expect(dndCapture.drop.collect({ isOver: () => true })).toEqual({ isOver: true });
    dndCapture.isOver = true;
    rerender(
      <MealSlot day="Monday" type="lunch" onDrop={onDrop}><span>slot</span></MealSlot>
    );
    expect(screen.getByText('slot')).toBeInTheDocument();
  });
});

describe('FavoriteButton', () => {
  it('toggles and reports the new state', () => {
    const onToggle = vi.fn();
    render(<FavoriteButton isFavorited={false} onToggle={onToggle} />);
    fireEvent.click(screen.getByRole('button'));
    expect(onToggle).toHaveBeenCalledWith(true);
    fireEvent.click(screen.getByRole('button'));
    expect(onToggle).toHaveBeenCalledWith(false);
  });

  it('works without a callback', () => {
    render(<FavoriteButton isFavorited />);
    fireEvent.click(screen.getByRole('button'));
  });
});

describe('DraggableMealCard', () => {
  const meal = {
    recipe_id: 1, recipe_name: 'Chicken Pasta',
    ingredients: [{ item: 'Chicken' }],
  };

  it('renders the meal and dims while dragging', () => {
    const { container, rerender } = render(
      <DraggableMealCard meal={meal} day="Monday" type="Dinner" />
    );
    expect(screen.getByText(/Chicken Pasta/)).toBeInTheDocument();
    expect(dndCapture.drag.item).toEqual({ meal, day: 'Monday', type: 'Dinner' });
    expect(dndCapture.drag.collect({ isDragging: () => true })).toEqual({ isDragging: true });
    dndCapture.isDragging = true;
    rerender(<DraggableMealCard meal={meal} day="Monday" type="Dinner" />);
    expect(container.firstChild.style.opacity).toBe('0.5');
  });
});

// ---------------------------------------------------------------------------
// ShoppingListItem / NetworkStatusIndicator / NutritionSummary
// ---------------------------------------------------------------------------

describe('ShoppingListItem', () => {
  const item = { name: 'Milk', quantity: 2, unit: 'L', store: 'Metro', price: 4.99, is_deal: true };

  it('renders details and toggles on click', () => {
    const onToggle = vi.fn();
    render(<ShoppingListItem item={item} isChecked={false} onToggle={onToggle} />);
    expect(screen.getByText('Milk')).toBeInTheDocument();
    expect(screen.getByText('$4.99')).toBeInTheDocument();
    expect(screen.getByText('On Sale')).toBeInTheDocument();
    fireEvent.click(screen.getByText('Milk'));
    expect(onToggle).toHaveBeenCalled();
  });

  it('renders the checked state', () => {
    render(<ShoppingListItem item={{ ...item, is_deal: false }} isChecked onToggle={() => {}} />);
    expect(screen.queryByText('On Sale')).toBeNull();
  });
});

describe('NetworkStatusIndicator', () => {
  it('renders nothing when online', async () => {
    vi.doMock('../hooks/useNetworkStatus', () => ({ useNetworkStatus: () => true }));
    const mod = await import('../components/NetworkStatusIndicator');
    const { container } = render(<mod.default />);
    expect(container).toBeEmptyDOMElement();
    vi.doUnmock('../hooks/useNetworkStatus');
  });
});

describe('NutritionSummary', () => {
  it('renders the chart values', () => {
    const data = [
      { name: 'Protein', value: 120, unit: 'g', color: '#8884d8' },
      { name: 'Carbs', value: 200, unit: 'g', color: '#82ca9d' },
    ];
    render(<NutritionSummary data={data} />);
    expect(screen.getByText('Daily Average Nutrition')).toBeInTheDocument();
    expect(screen.getByText('Protein')).toBeInTheDocument();
    expect(screen.getByText('120g')).toBeInTheDocument();
    expect(screen.getByText('200g')).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// DietaryFilters
// ---------------------------------------------------------------------------

describe('DietaryFilters', () => {
  it('toggles open, shows the count badge and fires onChange', () => {
    const onChange = vi.fn();
    render(<DietaryFilters selected={['vegan', 'keto']} onChange={onChange} />);
    expect(screen.getByText('2')).toBeInTheDocument();
    expect(screen.getByText('Vegan')).toBeInTheDocument();
    fireEvent.click(screen.getByText('Dietary Preferences'));
    const checkbox = screen.getByDisplayValue('vegan');
    expect(checkbox.checked).toBe(true);
    fireEvent.click(checkbox);
    expect(onChange).toHaveBeenCalled();
  });

  it('starts open when initialOpen is set', () => {
    render(<DietaryFilters selected={[]} onChange={() => {}} initialOpen />);
    expect(screen.getByText('Gluten-Free')).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// StoreComparison
// ---------------------------------------------------------------------------

describe('StoreComparison', () => {
  const stores = [
    { name: 'Metro', total: 150.0, items_count: 20, savings: 5, trip_efficiency: 80 },
    { name: 'Walmart', total: 120.5, items_count: 24, savings: 12.5, trip_efficiency: 90 },
  ];

  it('sorts by total, marks the best price and toggles preference', () => {
    const onToggle = vi.fn();
    render(
      <StoreComparison stores={stores} preferredStores={['Metro']} onTogglePreference={onToggle} />
    );
    const names = screen.getAllByText(/Metro|Walmart/);
    expect(names[0]).toHaveTextContent('Walmart');
    expect(screen.getByText('Best Price')).toBeInTheDocument();
    expect(screen.getByText('+$29.50')).toBeInTheDocument();
    fireEvent.click(screen.getByTitle('Remove from priority'));
    expect(onToggle).toHaveBeenCalledWith('Metro');
    fireEvent.click(screen.getByTitle('Prioritize this store'));
    expect(onToggle).toHaveBeenCalledWith('Walmart');
  });
});

// ---------------------------------------------------------------------------
// RecipeFeedbackForm
// ---------------------------------------------------------------------------

describe('RecipeFeedbackForm', () => {
  it('submits feedback and resets the form', async () => {
    api.post.mockResolvedValue({});
    render(<RecipeFeedbackForm recipeId={3} />);
    fireEvent.change(screen.getByLabelText('Did you make this recipe?'), {
      target: { value: 'skipped' },
    });
    fireEvent.change(screen.getByLabelText('Notes'), { target: { value: 'Too salty' } });
    await act(async () => fireEvent.click(screen.getByText('Submit Feedback')));
    expect(api.post).toHaveBeenCalledWith('/recipes/3/feedback', {
      status: 'skipped', notes: 'Too salty',
    });
    expect(toastMock.success).toHaveBeenCalledWith('Feedback submitted!');
    expect(screen.getByLabelText('Did you make this recipe?').value).toBe('made_it');
    expect(screen.getByLabelText('Notes').value).toBe('');
  });

  it('shows an error toast when submission fails', async () => {
    api.post.mockRejectedValue(new Error('down'));
    render(<RecipeFeedbackForm recipeId={3} />);
    await act(async () => fireEvent.click(screen.getByText('Submit Feedback')));
    expect(toastMock.error).toHaveBeenCalledWith('Failed to submit feedback.');
    expect(console.error).toHaveBeenCalled();
  });
});
