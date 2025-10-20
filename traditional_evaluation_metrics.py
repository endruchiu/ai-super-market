"""
Traditional Recommendation System Evaluation Metrics
No LLM required - uses standard metrics from recommendation system research

Evaluation Categories:
1. Accuracy Metrics (how good are the recommendations?)
2. Business Metrics (does it drive value?)
3. Diversity & Coverage (variety of recommendations)
4. Cost Savings (specific to budget-saving use case)
5. User Engagement (click-through, acceptance rates)
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Any
from collections import defaultdict


class TraditionalEvaluator:
    """Evaluate recommendation systems using traditional metrics"""
    
    def __init__(self):
        self.results = []
    
    # =================================================================
    # 1. ACCURACY METRICS
    # =================================================================
    
    def precision_at_k(self, recommended: List[str], relevant: List[str], k: int = 5) -> float:
        """
        Precision@K: What fraction of recommended items are relevant?
        
        Example: If system recommends 5 items and 3 are good -> Precision = 3/5 = 0.60
        
        Higher is better (0-1 scale)
        """
        recommended_k = recommended[:k]
        relevant_set = set(relevant)
        
        if not recommended_k:
            return 0.0
        
        hits = sum(1 for item in recommended_k if item in relevant_set)
        return hits / len(recommended_k)
    
    def recall_at_k(self, recommended: List[str], relevant: List[str], k: int = 5) -> float:
        """
        Recall@K: What fraction of relevant items did we recommend?
        
        Example: If 10 items are relevant and we recommend 3 of them -> Recall = 3/10 = 0.30
        
        Higher is better (0-1 scale)
        """
        if not relevant:
            return 0.0
        
        recommended_k = recommended[:k]
        relevant_set = set(relevant)
        
        hits = sum(1 for item in recommended_k if item in relevant_set)
        return hits / len(relevant_set)
    
    def ndcg_at_k(self, recommended: List[str], relevance_scores: Dict[str, float], k: int = 5) -> float:
        """
        NDCG@K (Normalized Discounted Cumulative Gain): 
        Measures ranking quality - better items should be ranked higher
        
        Considers:
        - Relevance of each item (0-1 score)
        - Position in ranking (top positions count more)
        
        Higher is better (0-1 scale)
        """
        recommended_k = recommended[:k]
        
        # DCG: Discounted Cumulative Gain
        dcg = 0.0
        for i, item in enumerate(recommended_k, 1):
            relevance = relevance_scores.get(item, 0.0)
            dcg += relevance / np.log2(i + 1)
        
        # Ideal DCG: if we ranked perfectly
        ideal_items = sorted(relevance_scores.items(), key=lambda x: -x[1])[:k]
        idcg = 0.0
        for i, (_, relevance) in enumerate(ideal_items, 1):
            idcg += relevance / np.log2(i + 1)
        
        if idcg == 0:
            return 0.0
        
        return dcg / idcg
    
    def hit_rate_at_k(self, recommended: List[str], relevant: List[str], k: int = 5) -> float:
        """
        Hit Rate@K: Did we recommend at least one relevant item?
        
        Simple binary: 1 if at least one hit, 0 otherwise
        
        Higher is better (0-1 scale)
        """
        recommended_k = recommended[:k]
        relevant_set = set(relevant)
        
        return 1.0 if any(item in relevant_set for item in recommended_k) else 0.0
    
    # =================================================================
    # 2. BUSINESS METRICS
    # =================================================================
    
    def cost_savings_metric(self, original_cart: List[Dict], recommendations: List[Dict]) -> Dict[str, float]:
        """
        Calculate actual cost savings if user accepts recommendations
        
        Returns:
        - total_potential_savings: Total $ saved if all accepted
        - avg_savings_per_item: Average $ saved per recommendation
        - savings_percentage: % reduction in total cost
        """
        if not recommendations:
            return {
                'total_potential_savings': 0.0,
                'avg_savings_per_item': 0.0,
                'savings_percentage': 0.0
            }
        
        total_savings = sum(float(r.get('expected_saving', 0)) for r in recommendations)
        original_total = sum(item['price'] * item.get('qty', 1) for item in original_cart)
        
        return {
            'total_potential_savings': total_savings,
            'avg_savings_per_item': total_savings / len(recommendations) if recommendations else 0.0,
            'savings_percentage': (total_savings / original_total * 100) if original_total > 0 else 0.0
        }
    
    def acceptance_rate(self, recommendations_shown: int, recommendations_accepted: int) -> float:
        """
        Acceptance Rate: What % of recommendations do users actually use?
        
        Measured by tracking "Apply This Replacement" clicks
        
        Higher is better (0-100% scale)
        """
        if recommendations_shown == 0:
            return 0.0
        return (recommendations_accepted / recommendations_shown) * 100
    
    def click_through_rate(self, impressions: int, clicks: int) -> float:
        """
        CTR: What % of recommendation views lead to clicks/engagement?
        
        Higher is better (0-100% scale)
        """
        if impressions == 0:
            return 0.0
        return (clicks / impressions) * 100
    
    # =================================================================
    # 3. DIVERSITY & COVERAGE METRICS
    # =================================================================
    
    def diversity_score(self, recommendations: List[Dict]) -> float:
        """
        Diversity: How varied are the recommendations?
        
        Measures:
        - Number of unique categories
        - Distribution across categories
        
        Higher is better (0-1 scale)
        """
        if not recommendations:
            return 0.0
        
        categories = [r.get('replacement_product', {}).get('subcat', 'Unknown') 
                     for r in recommendations]
        unique_categories = len(set(categories))
        
        # Normalize by number of recommendations
        return min(unique_categories / len(recommendations), 1.0)
    
    def catalog_coverage(self, recommended_items: List[str], total_catalog_size: int) -> float:
        """
        Coverage: What % of catalog do we recommend?
        
        Too low = limited recommendations
        Too high = not personalized enough
        
        Good range: 5-20% (0.05-0.20)
        """
        if total_catalog_size == 0:
            return 0.0
        
        unique_recommended = len(set(recommended_items))
        return unique_recommended / total_catalog_size
    
    def gini_coefficient(self, item_frequencies: Dict[str, int]) -> float:
        """
        Gini Coefficient: Measure recommendation concentration
        
        0 = perfectly equal (all items recommended equally)
        1 = maximum inequality (only one item recommended)
        
        Lower is better for diversity (target: 0.3-0.6)
        """
        if not item_frequencies:
            return 0.0
        
        sorted_freq = sorted(item_frequencies.values())
        n = len(sorted_freq)
        
        if n == 0:
            return 0.0
        
        cumsum = np.cumsum(sorted_freq)
        return (2 * np.sum(cumsum) - (n + 1) * np.sum(sorted_freq)) / (n * np.sum(sorted_freq))
    
    # =================================================================
    # 4. RELEVANCE METRICS (NO GROUND TRUTH NEEDED)
    # =================================================================
    
    def category_match_score(self, original_item: Dict, recommended_items: List[Dict]) -> float:
        """
        Category Match: Do recommendations match original item's category?
        
        Good substitutes should be from same/similar category
        
        Higher is better (0-1 scale)
        """
        original_cat = original_item.get('subcat', '')
        
        if not recommended_items:
            return 0.0
        
        matches = sum(1 for rec in recommended_items 
                     if rec.get('replacement_product', {}).get('subcat') == original_cat)
        
        return matches / len(recommended_items)
    
    def price_appropriateness(self, original_item: Dict, recommended_items: List[Dict]) -> Dict[str, float]:
        """
        Price Appropriateness: Are recommendations reasonably priced?
        
        Measures:
        - avg_discount: Average % cheaper than original
        - too_cheap_rate: % that are suspiciously cheap (>80% off)
        - reasonable_rate: % within reasonable range (10-50% cheaper)
        """
        if not recommended_items:
            return {'avg_discount': 0.0, 'too_cheap_rate': 0.0, 'reasonable_rate': 0.0}
        
        original_price = original_item['price']
        discounts = []
        too_cheap = 0
        reasonable = 0
        
        for rec in recommended_items:
            rec_price = rec.get('replacement_product', {}).get('price', original_price)
            discount = (original_price - rec_price) / original_price * 100
            discounts.append(discount)
            
            if discount > 80:
                too_cheap += 1
            elif 10 <= discount <= 50:
                reasonable += 1
        
        return {
            'avg_discount': np.mean(discounts) if discounts else 0.0,
            'too_cheap_rate': (too_cheap / len(recommended_items)) * 100,
            'reasonable_rate': (reasonable / len(recommended_items)) * 100
        }


# =================================================================
# EVALUATION REPORT GENERATOR
# =================================================================

def compare_recommendation_systems(budget_recs: List[Dict], cf_recs: List[Dict], 
                                   hybrid_recs: List[Dict], cart: List[Dict]) -> pd.DataFrame:
    """
    Compare all three recommendation systems using traditional metrics
    
    Returns DataFrame with scores for each system
    """
    evaluator = TraditionalEvaluator()
    
    results = []
    
    for system_name, recs in [
        ('Budget-Saving', budget_recs),
        ('Personalized CF', cf_recs),
        ('Hybrid AI', hybrid_recs)
    ]:
        # Calculate metrics
        num_recs = len(recs)
        
        # Cost savings
        savings = evaluator.cost_savings_metric(cart, recs)
        
        # Diversity
        diversity = evaluator.diversity_score(recs)
        
        # Category matching (for first item in cart if exists)
        category_match = 0.0
        if cart and recs:
            category_match = evaluator.category_match_score(cart[0], recs)
        
        # Price appropriateness
        price_scores = {'avg_discount': 0.0, 'reasonable_rate': 0.0}
        if cart and recs:
            price_scores = evaluator.price_appropriateness(cart[0], recs)
        
        results.append({
            'System': system_name,
            'Recommendations': num_recs,
            'Total Savings ($)': f"${savings['total_potential_savings']:.2f}",
            'Avg Savings/Item ($)': f"${savings['avg_savings_per_item']:.2f}",
            'Savings %': f"{savings['savings_percentage']:.1f}%",
            'Diversity Score': f"{diversity:.2f}",
            'Category Match': f"{category_match:.2f}",
            'Avg Discount %': f"{price_scores['avg_discount']:.1f}%",
            'Reasonable Pricing %': f"{price_scores['reasonable_rate']:.1f}%"
        })
    
    return pd.DataFrame(results)


if __name__ == "__main__":
    print("\n" + "="*70)
    print("TRADITIONAL EVALUATION METRICS (NO LLM)")
    print("="*70)
    
    print("\n📊 Available Metric Categories:\n")
    
    print("1. ACCURACY METRICS")
    print("   - Precision@K: Fraction of recommended items that are relevant")
    print("   - Recall@K: Fraction of relevant items that were recommended")
    print("   - NDCG@K: Ranking quality (better items ranked higher)")
    print("   - Hit Rate@K: Did we recommend at least one good item?")
    
    print("\n2. BUSINESS METRICS")
    print("   - Cost Savings: Total $ saved if recommendations accepted")
    print("   - Acceptance Rate: % of recommendations users actually use")
    print("   - Click-Through Rate: % of views that lead to engagement")
    
    print("\n3. DIVERSITY & COVERAGE")
    print("   - Diversity Score: Variety across categories")
    print("   - Catalog Coverage: % of total products recommended")
    print("   - Gini Coefficient: Recommendation concentration")
    
    print("\n4. RELEVANCE METRICS")
    print("   - Category Match: Do substitutes match original category?")
    print("   - Price Appropriateness: Are discounts reasonable?")
    
    print("\n" + "="*70)
    print("Run: python evaluate_systems_traditional.py")
    print("="*70 + "\n")
