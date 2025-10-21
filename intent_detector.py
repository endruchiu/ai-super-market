"""
Intent Detection Module (ISRec-inspired)

Analyzes user session behavior to detect intent:
- Quality mode (1.0): User browsing premium/organic products
- Economy mode (0.0): User seeking budget-friendly alternatives
- Balanced mode (0.5): Mixed behavior

This simplified ISRec implementation uses rule-based heuristics instead of
transformers for real-time performance.
"""

from datetime import datetime, timedelta
from typing import List, Dict, Optional
from models import UserEvent, db
import pandas as pd


class IntentDetector:
    """
    Detects user shopping intent from recent session actions.
    
    Intent Score:
    - 0.0 - 0.3: Strong economy mode (price-focused)
    - 0.3 - 0.7: Balanced mode
    - 0.7 - 1.0: Strong quality mode (premium-focused)
    """
    
    def __init__(self, lookback_minutes=10, max_actions=10):
        """
        Args:
            lookback_minutes: How far back to analyze actions (default: 10 min)
            max_actions: Maximum number of recent actions to consider
        """
        self.lookback_minutes = lookback_minutes
        self.max_actions = max_actions
    
    def detect_intent(self, user_id: str, current_cart: List[Dict] = None) -> float:
        """
        Analyze recent user actions to detect current intent.
        
        Args:
            user_id: User session ID
            current_cart: Current cart items (optional, for context)
            
        Returns:
            Intent score [0, 1] where 0=economy, 1=quality
        """
        # Get recent user events
        recent_actions = self._get_recent_actions(user_id)
        
        if len(recent_actions) == 0:
            return 0.5  # Default: balanced mode
        
        # Calculate signals
        quality_signals = self._calculate_quality_signals(recent_actions, current_cart)
        economy_signals = self._calculate_economy_signals(recent_actions, current_cart)
        
        total_signals = quality_signals + economy_signals
        
        if total_signals == 0:
            return 0.5  # No strong signals, balanced
        
        # Convert to intent score [0, 1]
        quality_ratio = quality_signals / total_signals
        
        return quality_ratio
    
    def _get_recent_actions(self, user_id: str) -> List[Dict]:
        """Get recent user events from database"""
        cutoff_time = datetime.utcnow() - timedelta(minutes=self.lookback_minutes)
        
        events = UserEvent.query.filter(
            UserEvent.user_id == user_id,
            UserEvent.created_at >= cutoff_time
        ).order_by(UserEvent.created_at.desc()).limit(self.max_actions).all()
        
        actions = []
        for event in events:
            actions.append({
                'event_type': event.event_type,
                'product_id': event.product_id,
                'timestamp': event.created_at
            })
        
        return actions
    
    def _calculate_quality_signals(self, actions: List[Dict], cart: List[Dict] = None) -> float:
        """
        Count quality-focused signals:
        - View premium/organic products
        - Add expensive items to cart
        - Remove cheap items (upgrading)
        """
        from main import PRODUCTS_DF  # Import global product catalog
        
        signals = 0.0
        
        for action in actions:
            product_id = action['product_id']
            
            # Get product info
            if product_id not in PRODUCTS_DF.index:
                continue
            
            product = PRODUCTS_DF.loc[product_id]
            price = float(product.get('_price_final', 0))
            title = str(product.get('Title', '')).lower()
            
            # Check for quality indicators
            is_premium = any(keyword in title for keyword in [
                'organic', 'premium', 'grass-fed', 'free-range',
                'artisan', 'imported', 'gourmet', 'specialty'
            ])
            
            is_expensive = price > 25  # Above average grocery price
            
            if action['event_type'] == 'view':
                if is_premium:
                    signals += 1.0
                elif is_expensive:
                    signals += 0.5
            
            elif action['event_type'] == 'cart_add':
                if is_premium:
                    signals += 2.0  # Cart adds weighted higher
                elif is_expensive:
                    signals += 1.0
            
            elif action['event_type'] == 'cart_remove':
                # Removing cheap items = quality signal (upgrading)
                if not is_premium and price < 15:
                    signals += 1.5
        
        return signals
    
    def _calculate_economy_signals(self, actions: List[Dict], cart: List[Dict] = None) -> float:
        """
        Count economy-focused signals:
        - View budget products
        - Add cheap items to cart
        - Remove expensive items (downgrading)
        """
        from main import PRODUCTS_DF
        
        signals = 0.0
        
        for action in actions:
            product_id = action['product_id']
            
            if product_id not in PRODUCTS_DF.index:
                continue
            
            product = PRODUCTS_DF.loc[product_id]
            price = float(product.get('_price_final', 0))
            title = str(product.get('Title', '')).lower()
            
            # Check for budget indicators
            is_value = any(keyword in title for keyword in [
                'value', 'budget', 'saver', 'basic', 'everyday'
            ])
            
            is_cheap = price < 10
            
            if action['event_type'] == 'view':
                if is_value or is_cheap:
                    signals += 1.0
            
            elif action['event_type'] == 'cart_add':
                if is_value:
                    signals += 2.0
                elif is_cheap:
                    signals += 1.5
            
            elif action['event_type'] == 'cart_remove':
                # Removing expensive items = economy signal (downgrading)
                if price > 20:
                    signals += 2.0
        
        return signals
    
    def get_intent_description(self, intent_score: float) -> str:
        """Convert intent score to human-readable description"""
        if intent_score >= 0.7:
            return "quality"
        elif intent_score <= 0.3:
            return "economy"
        else:
            return "balanced"


# Global instance
intent_detector = IntentDetector()
