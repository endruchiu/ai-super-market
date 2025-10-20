"""
Multi-Armed Bandits for Exploration-Exploitation in Recommendations
Uses epsilon-greedy strategy to balance showing known good items vs discovering new ones.
"""

import numpy as np
import pickle
import os
from typing import List, Dict, Optional
from datetime import datetime


class EpsilonGreedyBandit:
    """
    Epsilon-Greedy Multi-Armed Bandit for product recommendations.
    
    Maintains:
    - Impressions: How many times each product was shown
    - Clicks: How many times each product was clicked/added to cart
    - CTR: Click-through rate (clicks / impressions)
    
    Strategy:
    - With probability epsilon: EXPLORE (show random products)
    - With probability (1-epsilon): EXPLOIT (show high-CTR products)
    """
    
    def __init__(self, epsilon=0.1, decay_rate=0.999, min_epsilon=0.01):
        """
        Args:
            epsilon: Exploration rate (default 10%)
            decay_rate: Epsilon decay per call (default 0.999)
            min_epsilon: Minimum epsilon (default 1%)
        """
        self.epsilon = epsilon
        self.initial_epsilon = epsilon
        self.decay_rate = decay_rate
        self.min_epsilon = min_epsilon
        
        # Product statistics
        self.impressions = {}  # product_id -> count
        self.clicks = {}  # product_id -> count
        self.ctr = {}  # product_id -> click-through rate
        
        self.total_calls = 0
        self.total_explorations = 0
        self.total_exploitations = 0
    
    def get_ctr(self, product_id: int) -> float:
        """Get CTR for a product (with Laplace smoothing)."""
        impressions = self.impressions.get(product_id, 0)
        clicks = self.clicks.get(product_id, 0)
        
        # Laplace smoothing: assume 1 impression, 0.1 clicks initially
        return (clicks + 0.1) / (impressions + 1.0)
    
    def apply_exploration(self, recommendations: List[Dict], explore_pool: List[int] = None) -> List[Dict]:
        """
        Apply epsilon-greedy exploration to recommendations.
        
        Args:
            recommendations: List of recommended products from base system
            explore_pool: Optional list of product IDs to sample from for exploration
            
        Returns:
            Modified recommendations with exploration mixed in
        """
        if len(recommendations) == 0:
            return recommendations
        
        self.total_calls += 1
        
        # Decide: explore or exploit?
        if np.random.random() < self.epsilon:
            # EXPLORE: Replace some recommendations with random products
            self.total_explorations += 1
            
            if explore_pool and len(explore_pool) > 0:
                # Sample random products from pool
                num_explore = max(1, len(recommendations) // 3)  # Replace 33%
                explore_products = np.random.choice(
                    explore_pool,
                    size=min(num_explore, len(explore_pool)),
                    replace=False
                ).tolist()
                
                # Replace bottom recommendations with exploration
                recommendations = recommendations[:len(recommendations) - num_explore]
                
                for prod_id in explore_products:
                    recommendations.append({
                        'product_id': prod_id,
                        'score': 0.5,  # Neutral score
                        'source': 'exploration'
                    })
            
            # Decay epsilon
            self.epsilon = max(self.min_epsilon, self.epsilon * self.decay_rate)
        else:
            # EXPLOIT: Use recommendations as-is
            self.total_exploitations += 1
        
        return recommendations
    
    def record_impression(self, product_id: int):
        """Record that a product was shown to user."""
        product_id = int(product_id)
        self.impressions[product_id] = self.impressions.get(product_id, 0) + 1
        self.ctr[product_id] = self.get_ctr(product_id)
    
    def record_click(self, product_id: int):
        """Record that a product was clicked/added to cart."""
        product_id = int(product_id)
        self.clicks[product_id] = self.clicks.get(product_id, 0) + 1
        self.ctr[product_id] = self.get_ctr(product_id)
    
    def get_stats(self) -> Dict:
        """Get bandit statistics."""
        return {
            'epsilon': self.epsilon,
            'total_calls': self.total_calls,
            'total_explorations': self.total_explorations,
            'total_exploitations': self.total_exploitations,
            'exploration_rate': self.total_explorations / max(1, self.total_calls),
            'num_products_tracked': len(self.impressions),
            'top_ctr_products': sorted(
                [(pid, ctr) for pid, ctr in self.ctr.items()],
                key=lambda x: x[1],
                reverse=True
            )[:10]
        }
    
    def save(self, filepath='ml_data/bandit_state.pkl'):
        """Save bandit state to disk."""
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        state = {
            'epsilon': self.epsilon,
            'initial_epsilon': self.initial_epsilon,
            'decay_rate': self.decay_rate,
            'min_epsilon': self.min_epsilon,
            'impressions': self.impressions,
            'clicks': self.clicks,
            'ctr': self.ctr,
            'total_calls': self.total_calls,
            'total_explorations': self.total_explorations,
            'total_exploitations': self.total_exploitations,
            'saved_at': datetime.now().isoformat()
        }
        with open(filepath, 'wb') as f:
            pickle.dump(state, f)
    
    @classmethod
    def load(cls, filepath='ml_data/bandit_state.pkl'):
        """Load bandit state from disk."""
        if not os.path.exists(filepath):
            return cls()  # Return new instance
        
        with open(filepath, 'rb') as f:
            state = pickle.load(f)
        
        bandit = cls(
            epsilon=state.get('initial_epsilon', 0.1),
            decay_rate=state.get('decay_rate', 0.999),
            min_epsilon=state.get('min_epsilon', 0.01)
        )
        bandit.epsilon = state.get('epsilon', 0.1)
        bandit.impressions = state.get('impressions', {})
        bandit.clicks = state.get('clicks', {})
        bandit.ctr = state.get('ctr', {})
        bandit.total_calls = state.get('total_calls', 0)
        bandit.total_explorations = state.get('total_explorations', 0)
        bandit.total_exploitations = state.get('total_exploitations', 0)
        
        return bandit


# Global bandit instance
_GLOBAL_BANDIT = None

def get_bandit() -> EpsilonGreedyBandit:
    """Get or create global bandit instance."""
    global _GLOBAL_BANDIT
    if _GLOBAL_BANDIT is None:
        _GLOBAL_BANDIT = EpsilonGreedyBandit.load()
    return _GLOBAL_BANDIT


def save_bandit():
    """Save global bandit state."""
    if _GLOBAL_BANDIT is not None:
        _GLOBAL_BANDIT.save()


if __name__ == '__main__':
    # Test bandit
    print("Testing Epsilon-Greedy Bandit...")
    
    bandit = EpsilonGreedyBandit(epsilon=0.2)
    
    # Simulate some interactions
    products = list(range(100, 200))
    
    for i in range(100):
        # Get recommendations
        recs = [{'product_id': p, 'score': 0.8} for p in np.random.choice(products, 10, replace=False)]
        
        # Apply exploration
        explored_recs = bandit.apply_exploration(recs, explore_pool=products)
        
        # Record impressions
        for rec in explored_recs[:5]:
            bandit.record_impression(rec['product_id'])
        
        # Simulate clicks (higher CTR for lower product IDs)
        for rec in explored_recs[:5]:
            if np.random.random() < (1.0 - rec['product_id'] / 200):
                bandit.record_click(rec['product_id'])
    
    # Print stats
    stats = bandit.get_stats()
    print(f"\nBandit Statistics:")
    print(f"  Epsilon: {stats['epsilon']:.3f}")
    print(f"  Total calls: {stats['total_calls']}")
    print(f"  Explorations: {stats['total_explorations']} ({stats['exploration_rate']:.1%})")
    print(f"  Exploitations: {stats['total_exploitations']}")
    print(f"  Products tracked: {stats['num_products_tracked']}")
    print(f"\nTop 10 CTR Products:")
    for prod_id, ctr in stats['top_ctr_products']:
        print(f"    Product {prod_id}: CTR = {ctr:.3f}")
    
    # Save and reload
    bandit.save('ml_data/test_bandit.pkl')
    bandit2 = EpsilonGreedyBandit.load('ml_data/test_bandit.pkl')
    print(f"\n✓ Saved and reloaded bandit (epsilon={bandit2.epsilon:.3f})")
