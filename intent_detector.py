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
    
    def detect_intent(self, user_id: str, current_cart: List[Dict] = None, db_session=None) -> float:
        """
        Analyze recent user actions to detect current intent.
        
        Args:
            user_id: User session ID
            current_cart: Current cart items (optional, for context)
            db_session: Database session (required for querying events)
            
        Returns:
            Intent score [0, 1] where 0=economy, 1=quality
        """
        # Get recent user events
        recent_actions = self._get_recent_actions(user_id, db_session)
        
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
    
    def _get_recent_actions(self, user_id: str, db_session=None) -> List[Dict]:
        """Get recent user events from database"""
        if db_session is None:
            return []  # No database session provided
        
        # Import UserEvent dynamically to avoid circular import
        try:
            from models import UserEvent
        except ImportError:
            return []
        
        cutoff_time = datetime.utcnow() - timedelta(minutes=self.lookback_minutes)
        
        events = db_session.query(UserEvent).filter(
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
        Count quality-focused signals using RELATIVE PRICE POSITION:
        - View/add products in top price tier within their category
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
            subcat = str(product.get('Sub Category', ''))
            title = str(product.get('Title', '')).lower()
            
            # Calculate RELATIVE price position within subcategory
            price_percentile = self._get_price_percentile(price, subcat, PRODUCTS_DF)
            
            # Check for premium keywords
            is_premium_keyword = any(keyword in title for keyword in [
                'premium', 'grass-fed', 'free-range',
                'artisan', 'imported', 'gourmet', 'specialty', 'wagyu', 'truffle'
            ])
            
            # Relative price tiers (within same category)
            is_top_tier = price_percentile >= 75  # Top 25% most expensive in category
            is_upper_tier = price_percentile >= 60  # Top 40%
            
            if action['event_type'] == 'view':
                if is_top_tier:
                    signals += 2.0  # Viewing expensive items in category
                elif is_upper_tier:
                    signals += 1.0
                elif is_premium_keyword:
                    signals += 0.5
            
            elif action['event_type'] == 'cart_add':
                if is_top_tier:
                    signals += 3.0  # Adding expensive items = strong signal
                elif is_upper_tier:
                    signals += 2.0
                elif is_premium_keyword:
                    signals += 1.0
            
            elif action['event_type'] == 'cart_remove':
                # Removing cheap items = quality signal (upgrading)
                is_bottom_tier = price_percentile <= 25
                if is_bottom_tier:
                    signals += 1.5
        
        return signals
    
    def _calculate_economy_signals(self, actions: List[Dict], cart: List[Dict] = None) -> float:
        """
        Count economy-focused signals using RELATIVE PRICE POSITION:
        - View/add products in bottom price tier within their category
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
            subcat = str(product.get('Sub Category', ''))
            title = str(product.get('Title', '')).lower()
            
            # Calculate RELATIVE price position within subcategory
            price_percentile = self._get_price_percentile(price, subcat, PRODUCTS_DF)
            
            # Check for value keywords
            is_value_keyword = any(keyword in title for keyword in [
                'value', 'budget', 'saver', 'basic', 'everyday', 'kirkland'
            ])
            
            # Relative price tiers (within same category)
            is_bottom_tier = price_percentile <= 25  # Bottom 25% cheapest in category
            is_lower_tier = price_percentile <= 40   # Bottom 40%
            
            if action['event_type'] == 'view':
                if is_bottom_tier:
                    signals += 2.0  # Viewing cheap items in category
                elif is_lower_tier:
                    signals += 1.0
                elif is_value_keyword:
                    signals += 0.5
            
            elif action['event_type'] == 'cart_add':
                if is_bottom_tier:
                    signals += 3.0  # Adding cheap items = strong signal
                elif is_lower_tier:
                    signals += 2.0
                elif is_value_keyword:
                    signals += 1.0
            
            elif action['event_type'] == 'cart_remove':
                # Removing expensive items = economy signal (downgrading)
                is_top_tier = price_percentile >= 75
                if is_top_tier:
                    signals += 2.0
        
        return signals
    
    def _get_price_percentile(self, price: float, subcategory: str, products_df) -> float:
        """
        Calculate price percentile within the same subcategory.
        
        Returns:
            Percentile (0-100) where 100 = most expensive in category
        """
        try:
            # Get all products in same subcategory
            same_category = products_df[products_df['Sub Category'] == subcategory]
            
            if len(same_category) < 2:
                # Not enough data, fall back to global percentile
                all_prices = products_df['_price_final'].dropna()
                if len(all_prices) == 0:
                    return 50  # Default to middle
                percentile = (all_prices <= price).sum() / len(all_prices) * 100
                return percentile
            
            # Calculate percentile within category
            category_prices = same_category['_price_final'].dropna()
            percentile = (category_prices <= price).sum() / len(category_prices) * 100
            
            return percentile
            
        except Exception:
            return 50  # Default to middle if calculation fails
    
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
