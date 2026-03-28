"""
Deal Quality Scoring Service

This service filters and scores deals to separate genuine savings from
marketing noise (e.g., "Watatow offre du siècle", promotional gimmicks).

Based on Reddit thread feedback:
- Users complained about marketing text cluttering LLM output
- Need to distinguish real discounts from "fake" promotions
- Quality scoring helps surface the best actual deals
"""

import re
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class DealQuality(Enum):
    """Deal quality classification."""

    EXCELLENT = "excellent"  # 30%+ real discount
    GOOD = "good"  # 20-30% discount
    AVERAGE = "average"  # 10-20% discount
    POOR = "poor"  # <10% or suspicious
    NOISE = "noise"  # Marketing/promotional noise


@dataclass
class QualityScore:
    """Detailed quality assessment for a deal."""

    overall_score: float  # 0-100
    quality: DealQuality
    confidence: float  # How confident we are in this assessment
    flags: List[str]  # Warning flags
    adjustments: Dict[str, float]  # Score adjustments applied


class DealQualityService:
    """
    Service for scoring and filtering deal quality.

    Scores deals based on:
    1. Actual discount percentage
    2. Price reasonableness (not suspiciously low)
    3. Marketing noise detection
    4. Loyalty point value
    5. Historical price patterns (if available)
    """

    # Marketing phrases to detect (bilingual Quebec market)
    MARKETING_NOISE_PATTERNS = [
        r"watatow",
        r"offre du siècle",
        r"super rabais",
        r"méga vente",
        r"prix fou",
        r"incroyable",
        r"wow",
        r"crazy deal",
        r"unbelievable",
        r"best ever",
        r"ne manquez pas",
        r"don\'t miss",
        r"quantités limitées",
        r"limited quantities",
        r"vente finale",
        r"final sale",
        r"solde monstre",
        r"monster sale",
        r"aubaine",
        r"prix imbattable",
        r"bas prix de tous les jours",
        r"everyday low price",
        r"economisez gros",
        r"rabais exceptionnel",
    ]

    # Suspicious price patterns (too good to be true) - Base prices per kg/unit
    # Ordered from most specific to least specific
    MIN_BELIEVABLE_PRICES = [
        ("beef", 8.00),  # per kg
        ("seafood", 7.00),
        ("meat", 4.00),  # per kg minimum (e.g., pork/chicken)
        ("dairy", 0.75),
        ("produce", 0.50),
        ("bakery", 1.00),
        ("beverages", 0.50),
        ("frozen", 1.50),
        ("pantry", 0.75),
    ]

    # Common "fake discount" products (often always on "sale")
    PERPETUAL_SALE_PRODUCTS = [
        "rotisserie chicken",
        "poulet rôti",
        "hot dog",
        "saucisse à hot dog",
        "pizza combo",
        "combo pizza",
        "dempster",
        "villaggio",
        "wonder bread",
        "pain wonder",
        "st-hubert",
    ]

    def __init__(self):
        self.noise_regex = re.compile(
            "|".join(self.MARKETING_NOISE_PATTERNS), re.IGNORECASE
        )

    def score_deal(
        self, deal: Dict[str, Any], historical_prices: Optional[List[float]] = None
    ) -> QualityScore:
        """
        Calculate a quality score for a single deal.

        Args:
            deal: Deal dictionary with price, original_price, name, etc.
            historical_prices: Optional list of past prices for this product

        Returns:
            QualityScore with detailed assessment
        """
        score = 50.0  # Start at neutral
        flags = []
        adjustments = {}

        name = deal.get("name", "").lower()
        price = deal.get("price", 0)
        original_price = deal.get("original_price", price)
        discount_pct = deal.get("discount_pct", 0)
        category = deal.get("category", "grocery").lower()
        sale_info = (deal.get("sale_info") or "").lower()
        loyalty_points = deal.get("loyalty_points") or 0
        loyalty_program = deal.get("loyalty_program") or ""

        # 1. Base discount scoring
        if discount_pct:
            if discount_pct >= 40:
                adjustments["high_discount"] = 30
                score += 30
            elif discount_pct >= 30:
                adjustments["good_discount"] = 20
                score += 20
            elif discount_pct >= 20:
                adjustments["moderate_discount"] = 10
                score += 10
            elif discount_pct >= 10:
                adjustments["small_discount"] = 5
                score += 5
            else:
                adjustments["minimal_discount"] = -5
                score -= 5
                flags.append("Minimal discount (<10%)")
        else:
            # Calculate discount from prices if not provided
            if original_price and original_price > price:
                calculated_discount = ((original_price - price) / original_price) * 100
                if calculated_discount >= 20:
                    adjustments["calculated_discount"] = 15
                    score += 15

        # 2. Marketing noise detection
        noise_in_name = self.noise_regex.search(name)
        noise_in_sale_info = self.noise_regex.search(sale_info)

        if noise_in_name:
            adjustments["marketing_noise_name"] = -20
            score -= 20
            flags.append(f"Marketing noise detected: '{noise_in_name.group()}'")

        if noise_in_sale_info:
            adjustments["marketing_noise_promo"] = -10
            score -= 10
            flags.append("Promotional marketing text in sale info")

        # 3. Price reasonableness check
        unit = deal.get("unit", "kg")
        min_price = self._get_minimum_believable_price(category, unit)
        if price < min_price:
            adjustments["suspicious_price"] = -25
            score -= 25
            flags.append(f"Price ${price:.2f} seems too low for {category}")

        # 4. Perpetual sale detection
        if any(p in name for p in self.PERPETUAL_SALE_PRODUCTS):
            adjustments["perpetual_sale"] = -15
            score -= 15
            flags.append("Product is frequently on perpetual 'sale'")

        # 5. Loyalty points bonus
        if loyalty_points > 0:
            # Calculate approximate dollar value
            point_values = {
                "PC Optimum": 0.001,
                "Scene+": 0.01,
                "Moi": 0.008,
                "AIR MILES": 0.105,
            }
            point_value = point_values.get(loyalty_program, 0.001)
            loyalty_dollar_value = loyalty_points * point_value

            if loyalty_dollar_value > 2.0:
                adjustments["high_loyalty_value"] = 15
                score += 15
            elif loyalty_dollar_value > 0.50:
                adjustments["moderate_loyalty_value"] = 5
                score += 5

        # 6. Historical price analysis (if available)
        if historical_prices and len(historical_prices) >= 3:
            avg_historical = sum(historical_prices) / len(historical_prices)
            if price < avg_historical * 0.8:  # 20%+ below average
                adjustments["below_historical_avg"] = 10
                score += 10
            elif price > avg_historical * 0.95:  # Near or above average
                adjustments["at_historical_avg"] = -10
                score -= 10
                flags.append("Price is near historical average (not a real sale)")

        # 7. Discount magnitude vs. original price sanity check
        if original_price and original_price > 0:
            if original_price > price * 3:  # "70% off" claims
                adjustments["inflated_original"] = -20
                score -= 20
                flags.append("Original price may be inflated")

        # Clamp score to 0-100
        score = max(0, min(100, score))

        # Determine quality classification
        if score >= 80:
            quality = DealQuality.EXCELLENT
        elif score >= 65:
            quality = DealQuality.GOOD
        elif score >= 45:
            quality = DealQuality.AVERAGE
        elif score >= 25:
            quality = DealQuality.POOR
        else:
            quality = DealQuality.NOISE

        # Calculate confidence
        confidence = self._calculate_confidence(deal, flags)

        return QualityScore(
            overall_score=round(score, 1),
            quality=quality,
            confidence=round(confidence, 2),
            flags=flags,
            adjustments=adjustments,
        )

    def _get_minimum_believable_price(self, category: str, unit: str = "kg") -> float:
        """
        Get minimum believable price for a category, adjusted for unit.
        """
        category_lower = category.lower()
        base_price = 0.50  # Default minimum

        for cat_key, min_p in self.MIN_BELIEVABLE_PRICES:
            if cat_key in category_lower:
                base_price = min_p
                break

        # Adjust for unit (reference is kg)
        if unit == "lb":
            return base_price * 0.453592
        elif unit == "100g":
            return base_price / 10.0
        elif unit == "g":
            return base_price / 1000.0

        return base_price

    def _calculate_confidence(self, deal: Dict[str, Any], flags: List[str]) -> float:
        """Calculate confidence in the quality assessment."""
        confidence = 0.8  # Base confidence

        # More data = higher confidence
        if deal.get("original_price"):
            confidence += 0.05
        if deal.get("discount_pct"):
            confidence += 0.05
        if deal.get("valid_until"):
            confidence += 0.03
        if deal.get("category"):
            confidence += 0.02

        # Flags reduce confidence
        confidence -= len(flags) * 0.05

        return max(0.3, min(1.0, confidence))

    def filter_deals(
        self,
        deals: List[Dict[str, Any]],
        min_quality: DealQuality = DealQuality.AVERAGE,
        min_score: float = 40.0,
    ) -> List[Dict[str, Any]]:
        """
        Filter deals by quality threshold.

        Args:
            deals: List of deal dictionaries
            min_quality: Minimum quality level to include
            min_score: Minimum score to include

        Returns:
            Filtered list of deals with quality scores attached
        """
        quality_order = [
            DealQuality.NOISE,
            DealQuality.POOR,
            DealQuality.AVERAGE,
            DealQuality.GOOD,
            DealQuality.EXCELLENT,
        ]
        min_quality_index = quality_order.index(min_quality)

        filtered = []
        for deal in deals:
            score = self.score_deal(deal)
            deal_quality_index = quality_order.index(score.quality)

            if (
                deal_quality_index >= min_quality_index
                and score.overall_score >= min_score
            ):
                # Attach quality info to deal
                deal["quality_score"] = score.overall_score
                deal["quality_level"] = score.quality.value
                deal["quality_flags"] = score.flags
                deal["quality_confidence"] = score.confidence
                filtered.append(deal)

        return filtered

    def rank_deals(
        self, deals: List[Dict[str, Any]], top_n: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Rank deals by quality score (best first).

        Args:
            deals: List of deal dictionaries
            top_n: Optional limit on number of deals to return

        Returns:
            Sorted list of deals with quality info
        """
        scored_deals = []
        for deal in deals:
            score = self.score_deal(deal)
            deal_copy = deal.copy()
            deal_copy["quality_score"] = score.overall_score
            deal_copy["quality_level"] = score.quality.value
            deal_copy["quality_flags"] = score.flags
            scored_deals.append(deal_copy)

        # Sort by score descending
        scored_deals.sort(key=lambda x: x["quality_score"], reverse=True)

        if top_n:
            scored_deals = scored_deals[:top_n]

        return scored_deals

    def remove_noise(self, deals: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Remove obvious marketing noise and low-quality deals.

        This is a convenience method for quick filtering.
        """
        return self.filter_deals(deals, min_quality=DealQuality.POOR, min_score=25.0)

    def get_quality_summary(self, deals: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Get a summary of deal quality distribution.
        """
        quality_counts = {q.value: 0 for q in DealQuality}
        total_score = 0
        flag_counts = {}

        for deal in deals:
            score = self.score_deal(deal)
            quality_counts[score.quality.value] += 1
            total_score += score.overall_score

            for flag in score.flags:
                flag_counts[flag] = flag_counts.get(flag, 0) + 1

        return {
            "total_deals": len(deals),
            "quality_distribution": quality_counts,
            "average_score": round(total_score / len(deals), 1) if deals else 0,
            "common_issues": dict(
                sorted(flag_counts.items(), key=lambda x: x[1], reverse=True)[:5]
            ),
            "excellent_deals": quality_counts[DealQuality.EXCELLENT.value],
            "noise_filtered": quality_counts[DealQuality.NOISE.value],
        }


# Singleton instance
deal_quality_service = DealQualityService()


def score_deal(deal: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convenience function to score a single deal.

    Returns the deal with quality info attached.
    """
    score = deal_quality_service.score_deal(deal)
    deal["quality_score"] = score.overall_score
    deal["quality_level"] = score.quality.value
    deal["quality_flags"] = score.flags
    deal["quality_confidence"] = score.confidence
    return deal


def filter_quality_deals(
    deals: List[Dict[str, Any]], min_quality: str = "average"
) -> List[Dict[str, Any]]:
    """
    Convenience function to filter deals by quality.

    Args:
        deals: List of deals
        min_quality: Minimum quality level ("excellent", "good", "average", "poor")
    """
    quality_map = {
        "excellent": DealQuality.EXCELLENT,
        "good": DealQuality.GOOD,
        "average": DealQuality.AVERAGE,
        "poor": DealQuality.POOR,
        "noise": DealQuality.NOISE,
    }
    min_q = quality_map.get(min_quality.lower(), DealQuality.AVERAGE)
    return deal_quality_service.filter_deals(deals, min_quality=min_q)
