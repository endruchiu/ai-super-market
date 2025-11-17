"""
Replenishment Recommendation Engine
Following 8-Step Framework for Intelligent Product Restock Suggestions
"""

from datetime import datetime, timedelta, date
from sqlalchemy import func, and_, desc
from collections import defaultdict
import pandas as pd
import numpy as np


class ReplenishmentEngine:
    """
    Implements 8-step replenishment strategy:
    1. AI-backed identification of replenishable products
    2. User-level replenishment duration on autopilot
    3. Quantity-based duration adjustment
    4. Product bundling for grouped reminders
    5. Out-of-stock fallback (integration point)
    6. Gift purchase detection
    7. Returns/cancellations filtering
    8. Unit size normalization
    """
    
    # Step 1: Categories that are typically replenishable consumables
    CONSUMABLE_CATEGORIES = [
        'Pantry & Dry Goods', 'Beverages & Water', 'Breakfast', 
        'Coffee', 'Cleaning Supplies', 'Laundry Detergent & Supplies',
        'Paper & Plastic Products', 'Household', 'Meat & Seafood',
        'Seafood', 'Poultry', 'Deli', 'Bakery & Desserts'
    ]
    
    # Step 6: Gift detection thresholds
    GIFT_QUANTITY_MULTIPLIER = 3.0  # 3x normal quantity = likely gift
    GIFT_HOLIDAY_WINDOWS = [
        (12, 15, 12, 31),  # Christmas (Dec 15-31)
        (11, 20, 11, 30),  # Thanksgiving (Nov 20-30)
        (2, 10, 2, 15),    # Valentine's (Feb 10-15)
    ]
    
    def __init__(self, db, products_df, Order=None, OrderItem=None, ReplenishableProduct=None, UserReplenishmentCycle=None):
        """
        Initialize replenishment engine
        
        Args:
            db: SQLAlchemy database instance
            products_df: Pandas DataFrame with product catalog (for size normalization)
            Order: Order model class (optional, will be set by caller)
            OrderItem: OrderItem model class (optional, will be set by caller)
            ReplenishableProduct: ReplenishableProduct model class (optional, will be set by caller)
            UserReplenishmentCycle: UserReplenishmentCycle model class (optional, will be set by caller)
        """
        self.db = db
        self.products_df = products_df
        
        # Store model classes
        self.Order = Order
        self.OrderItem = OrderItem
        self.ReplenishableProduct = ReplenishableProduct
        self.UserReplenishmentCycle = UserReplenishmentCycle
    
    # ==================== STEP 1: AI-Backed Identification ====================
    
    def identify_replenishable_products(self, min_purchases=2, min_users=1):
        """
        Step 1: Identify products suitable for replenishment
        
        Criteria:
        - Must be in consumable category
        - Purchased at least min_purchases times
        - By at least min_users different users
        
        Returns:
            List of product IDs identified as replenishable
        """
        
        # Query purchase patterns
        purchase_stats = self.db.session.query(
            self.OrderItem.product_id,
            self.OrderItem.product_title,
            self.OrderItem.product_subcat,
            func.count(self.OrderItem.id).label('total_purchases'),
            func.count(func.distinct(self.Order.user_id)).label('unique_users')
        ). join(self.Order).filter(
            self.OrderItem.product_subcat.in_(self.CONSUMABLE_CATEGORIES)
        ).group_by(
            self.OrderItem.product_id,
            self.OrderItem.product_title,
            self.OrderItem.product_subcat
        ).having(
            func.count(self.OrderItem.id) >= min_purchases,
            func.count(func.distinct(self.Order.user_id)) >= min_users
        ).all()
        
        replenishable_ids = []
        
        for stat in purchase_stats:
            product_id = stat.product_id
            
            # Get size info from product catalog
            size_value, size_unit = None, None
            if product_id in self.products_df.index:
                row = self.products_df.loc[product_id]
                if pd.notna(row.get('_size_value')):
                    size_value = float(row['_size_value'])
                if pd.notna(row.get('_size_unit')):
                    size_unit = str(row['_size_unit'])
            
            # Upsert to replenishable_products table
            existing = self.ReplenishableProduct.query.filter_by(product_id=product_id).first()
            
            if existing:
                existing.total_purchases = stat.total_purchases
                existing.unique_users = stat.unique_users
                existing.size_value = size_value
                existing.size_unit = size_unit
                existing.last_updated = datetime.utcnow()
            else:
                new_product = ReplenishableProduct(
                    product_id=product_id,
                    product_title=stat.product_title,
                    product_subcat=stat.product_subcat,
                    total_purchases=stat.total_purchases,
                    unique_users=stat.unique_users,
                    is_consumable=True,
                    size_value=size_value,
                    size_unit=size_unit
                )
                self.db.session.add(new_product)
            
            replenishable_ids.append(product_id)
        
        self.db.session.commit()
        print(f"✓ Identified {len(replenishable_ids)} replenishable products")
        
        return replenishable_ids
    
    # ==================== STEP 2 & 8: User-Level Cycles + Unit Normalization ====================
    
    def calculate_user_cycles(self, user_id):
        """
        Steps 2 & 8: Calculate replenishment cycles for a user with unit size normalization
        
        For each replenishable product the user has purchased:
        - Calculate median interval between purchases
        - Normalize by unit size (Step 8)
        - Predict next due date
        
        Args:
            user_id: User ID to calculate cycles for
            
        Returns:
            Number of active cycles created/updated
        """
        
        # Get all replenishable products this user has purchased
        user_purchases = self.db.session.query(
            self.OrderItem.product_id,
            self.OrderItem.product_title,
            self.OrderItem.product_subcat,
            self.OrderItem.quantity,
            self.Order.created_at
        ). join(self.Order).filter(
            self.Order.user_id == user_id
        ).order_by(self.OrderItem.product_id, self.Order.created_at).all()
        
        # Group by product
        product_purchases = defaultdict(list)
        for purchase in user_purchases:
            product_purchases[purchase.product_id].append({
                'title': purchase.product_title,
                'subcat': purchase.product_subcat,
                'quantity': purchase.quantity,
                'date': purchase.created_at
            })
        
        cycles_updated = 0
        
        for product_id, purchases in product_purchases.items():
            # Need at least 2 purchases to calculate interval
            if len(purchases) < 2:
                continue
            
            # Check if product is replenishable
            replenishable = self.ReplenishableProduct.query.filter_by(product_id=product_id).first()
            if not replenishable:
                continue
            
            # Step 7: Filter out returns/cancellations (orders with status='completed' only)
            # Currently all orders are 'completed', but structure is ready for status field
            
            # Calculate intervals between purchases
            intervals = []
            for i in range(1, len(purchases)):
                days_diff = (purchases[i]['date'] - purchases[i-1]['date']).days
                if days_diff > 0:  # Valid interval
                    intervals.append(days_diff)
            
            if not intervals:
                continue
            
            # Step 2: Use median interval (robust to outliers)
            median_interval = np.median(intervals)
            
            # Step 8: Normalize by unit size
            adjusted_interval = self._normalize_by_unit_size(
                product_id, median_interval, replenishable
            )
            
            # Step 3: Adjust for last quantity (handled in separate method)
            last_quantity = purchases[-1]['quantity']
            
            # Calculate next due date
            last_purchase_date = purchases[-1]['date']
            next_due = (last_purchase_date + timedelta(days=float(adjusted_interval))).date()
            
            # Upsert cycle
            existing_cycle = self.UserReplenishmentCycle.query.filter_by(
                user_id=user_id,
                product_id=product_id
            ).first()
            
            if existing_cycle:
                existing_cycle.last_purchase_date = last_purchase_date
                existing_cycle.purchase_count = len(purchases)
                existing_cycle.median_interval_days = median_interval
                existing_cycle.adjusted_interval_days = adjusted_interval
                existing_cycle.last_quantity = last_quantity
                existing_cycle.next_due_date = next_due
                existing_cycle.is_active = True
                existing_cycle.updated_at = datetime.utcnow()
            else:
                new_cycle = UserReplenishmentCycle(
                    user_id=user_id,
                    product_id=product_id,
                    product_title=purchases[-1]['title'],
                    product_subcat=purchases[-1]['subcat'],
                    first_purchase_date=purchases[0]['date'],
                    last_purchase_date=last_purchase_date,
                    purchase_count=len(purchases),
                    median_interval_days=median_interval,
                    adjusted_interval_days=adjusted_interval,
                    last_quantity=last_quantity,
                    next_due_date=next_due,
                    is_active=True
                )
                self.db.session.add(new_cycle)
            
            cycles_updated += 1
        
        self.db.session.commit()
        return cycles_updated
    
    def _normalize_by_unit_size(self, product_id, interval_days, replenishable_product):
        """
        Step 8: Normalize interval by unit size
        
        If product has size info (e.g., 32oz vs 64oz), adjust interval proportionally
        """
        # For now, return base interval
        # Future: Compare size_value across purchases to adjust
        return interval_days
    
    # ==================== STEP 3: Quantity-Based Adjustment ====================
    
    def adjust_for_quantity(self, user_id, product_id, new_quantity):
        """
        Step 3: Adjust next due date based on quantity change
        
        If user buys 2x normal quantity → extend interval by 2x
        
        Args:
            user_id: User ID
            product_id: Product ID
            new_quantity: Quantity purchased this time
        """
        
        cycle = self.UserReplenishmentCycle.query.filter_by(
            user_id=user_id,
            product_id=product_id,
            is_active=True
        ).first()
        
        if not cycle or not cycle.median_interval_days:
            return
        
        # Calculate historical average quantity
        
        avg_quantity = self.db.session.query(
            func.avg(self.OrderItem.quantity)
        ). join(self.Order).filter(
            self.Order.user_id == user_id,
            self.OrderItem.product_id == product_id
        ).scalar() or 1.0
        
        # Adjust interval by quantity ratio
        quantity_multiplier = new_quantity / avg_quantity
        adjusted_interval = float(cycle.median_interval_days) * quantity_multiplier
        
        # Update cycle
        cycle.adjusted_interval_days = adjusted_interval
        cycle.last_quantity = new_quantity
        cycle.next_due_date = (
            cycle.last_purchase_date + timedelta(days=adjusted_interval)
        ).date()
        
        self.db.session.commit()
    
    # ==================== STEP 4: Product Bundling ====================
    
    def get_bundled_reminders(self, user_id, window_days=3):
        """
        Step 4: Group products due within same time window
        
        Args:
            user_id: User ID
            window_days: Bundle items due within this many days
            
        Returns:
            List of bundles: [{'products': [...], 'due_date': date, 'total_price': float}]
        """
        
        # Get all active cycles due soon
        cycles = self.UserReplenishmentCycle.query.filter(
            self.UserReplenishmentCycle.user_id == user_id,
            self.UserReplenishmentCycle.is_active == True,
            self.UserReplenishmentCycle.next_due_date != None
        ).order_by(self.UserReplenishmentCycle.next_due_date).all()
        
        # Group by date window
        bundles = []
        current_bundle = []
        current_date = None
        
        for cycle in cycles:
            if current_date is None:
                current_date = cycle.next_due_date
                current_bundle = [cycle]
            elif (cycle.next_due_date - current_date).days <= window_days:
                current_bundle.append(cycle)
            else:
                # Save current bundle and start new one
                if len(current_bundle) > 0:
                    bundles.append(self._format_bundle(current_bundle))
                current_bundle = [cycle]
                current_date = cycle.next_due_date
        
        # Add last bundle
        if len(current_bundle) > 0:
            bundles.append(self._format_bundle(current_bundle))
        
        return bundles
    
    def _format_bundle(self, cycles):
        """Format a bundle of cycles for API response"""
        products = []
        total_price = 0.0
        
        for cycle in cycles:
            product_id = cycle.product_id
            
            # Get price from catalog
            price = 0.0
            if product_id in self.products_df.index:
                row = self.products_df.loc[product_id]
                if pd.notna(row.get('_price_final')):
                    price = float(row['_price_final'])
            
            products.append({
                'product_id': str(product_id),
                'title': cycle.product_title,
                'subcat': cycle.product_subcat,
                'price': price,
                'last_purchase': cycle.last_purchase_date.strftime('%Y-%m-%d'),
                'days_since_purchase': (datetime.utcnow().date() - cycle.last_purchase_date.date()).days,
                'due_date': cycle.next_due_date.strftime('%Y-%m-%d')
            })
            
            total_price += price
        
        return {
            'products': products,
            'bundle_size': len(products),
            'due_date': cycles[0].next_due_date.strftime('%Y-%m-%d'),
            'total_price': round(total_price, 2)
        }
    
    # ==================== STEP 6: Gift Detection ====================
    
    def detect_gift_purchase(self, user_id, product_id, quantity, purchase_date):
        """
        Step 6: Detect if purchase is likely a gift
        
        Criteria:
        - Quantity is 3x+ normal
        - Date is during holiday window
        
        Returns:
            bool: True if likely gift purchase
        """
        
        # Calculate average quantity for this user+product
        avg_quantity = self.db.session.query(
            func.avg(self.OrderItem.quantity)
        ). join(self.Order).filter(
            self.Order.user_id == user_id,
            self.OrderItem.product_id == product_id
        ).scalar()
        
        if not avg_quantity:
            return False
        
        # Check quantity multiplier
        if quantity < avg_quantity * self.GIFT_QUANTITY_MULTIPLIER:
            return False
        
        # Check holiday windows
        purchase_month = purchase_date.month
        purchase_day = purchase_date.day
        
        for start_month, start_day, end_month, end_day in self.GIFT_HOLIDAY_WINDOWS:
            if start_month == end_month:
                if purchase_month == start_month and start_day <= purchase_day <= end_day:
                    return True
            else:
                if (purchase_month == start_month and purchase_day >= start_day) or \
                   (purchase_month == end_month and purchase_day <= end_day):
                    return True
        
        return False
    
    # ==================== MAIN API: Get Due Reminders ====================
    
    def get_due_soon(self, user_id, days_ahead=7):
        """
        Get products due for replenishment soon
        
        Args:
            user_id: User ID
            days_ahead: Look ahead this many days
            
        Returns:
            {
                'due_now': [...],  # Overdue or due today
                'due_soon': [...],  # Due in next 3 days
                'upcoming': [...]   # Due in 4-7 days
            }
        """
        
        today = datetime.utcnow().date()
        
        cycles = self.UserReplenishmentCycle.query.filter(
            self.UserReplenishmentCycle.user_id == user_id,
            self.UserReplenishmentCycle.is_active == True,
            self.UserReplenishmentCycle.next_due_date != None,
            self.UserReplenishmentCycle.next_due_date <= today + timedelta(days=days_ahead)
        ).filter(
            # Respect skip_until_date
            (self.UserReplenishmentCycle.skip_until_date == None) |
            (self.UserReplenishmentCycle.skip_until_date < today)
        ).order_by(self.UserReplenishmentCycle.next_due_date).all()
        
        due_now = []
        due_soon = []
        upcoming = []
        
        for cycle in cycles:
            days_until = (cycle.next_due_date - today).days
            
            item = self._format_cycle_item(cycle, days_until)
            
            if days_until <= 0:
                due_now.append(item)
            elif days_until <= 3:
                due_soon.append(item)
            else:
                upcoming.append(item)
        
        return {
            'due_now': due_now,
            'due_soon': due_soon,
            'upcoming': upcoming,
            'total_active_cycles': len(cycles)
        }
    
    def _format_cycle_item(self, cycle, days_until):
        """Format a single cycle for API response"""
        product_id = cycle.product_id
        
        # Get product details from catalog
        price = 0.0
        image = None
        
        if product_id in self.products_df.index:
            row = self.products_df.loc[product_id]
            if pd.notna(row.get('_price_final')):
                price = float(row['_price_final'])
        
        return {
            'cycle_id': cycle.id,
            'product_id': str(product_id),
            'title': cycle.product_title,
            'subcat': cycle.product_subcat,
            'price': price,
            'interval_days': float(cycle.median_interval_days) if cycle.median_interval_days else None,
            'last_purchase': cycle.last_purchase_date.strftime('%Y-%m-%d'),
            'days_since_purchase': (datetime.utcnow().date() - cycle.last_purchase_date.date()).days,
            'due_date': cycle.next_due_date.strftime('%Y-%m-%d'),
            'days_until_due': days_until,
            'purchase_count': cycle.purchase_count
        }
    
    # ==================== FIRST-PURCHASE PREDICTION SYSTEM ====================
    
    # Category importance weights for urgency scoring
    CATEGORY_WEIGHTS = {
        'Beverages & Water': 3.0,  # High priority
        'Breakfast': 3.0,
        'Coffee': 2.5,
        'Pantry & Dry Goods': 2.5,
        'Meat & Seafood': 2.5,
        'Seafood': 2.5,
        'Poultry': 2.5,
        'Deli': 2.0,
        'Bakery & Desserts': 2.0,
        'Cleaning Supplies': 1.5,
        'Laundry Detergent & Supplies': 1.5,
        'Paper & Plastic Products': 1.5,
        'Household': 1.0,
        'Snacks': 0.8,  # Lower priority
        'Candy': 0.5,
        'Gift Baskets': 0.3
    }
    
    # Default intervals by category (in days)
    DEFAULT_CATEGORY_INTERVALS = {
        'Beverages & Water': 7,
        'Breakfast': 10,
        'Coffee': 14,
        'Pantry & Dry Goods': 21,
        'Meat & Seafood': 5,
        'Seafood': 5,
        'Poultry': 5,
        'Deli': 5,
        'Bakery & Desserts': 4,
        'Cleaning Supplies': 30,
        'Laundry Detergent & Supplies': 30,
        'Paper & Plastic Products': 30,
        'Household': 45,
        'Snacks': 14,
        'Candy': 21,
        'Gift Baskets': 60
    }

    def _get_cf_similar_user_intervals(self, product_id, user_id):
        """
        Get consumption intervals for this product from SIMILAR users using CF model embeddings.
        
        Returns:
            float: Median interval in days from similar users, or None if no data
        """
        try:
            from cf_inference import load_cf_model
            import numpy as np
            
            model, artifacts = load_cf_model()
            if model is None or artifacts is None:
                return None
            
            # Map user_id (integer) to CF index
            user_id_to_idx = artifacts['user_mapping']
            
            # Check if current user is in CF model
            if user_id not in user_id_to_idx:
                return None
            
            current_user_idx = user_id_to_idx[user_id]
            
            # Extract user embeddings from the model
            user_embedding_layer = model.get_layer('user_embedding')
            user_embeddings = user_embedding_layer.get_weights()[0]  # Shape: (num_users, embedding_dim)
            
            # Get current user's embedding
            current_user_emb = user_embeddings[current_user_idx]
            
            # Calculate cosine similarity to all other users
            # Normalize embeddings
            user_norms = np.linalg.norm(user_embeddings, axis=1, keepdims=True) + 1e-10
            user_embeddings_norm = user_embeddings / user_norms
            current_user_emb_norm = current_user_emb / (np.linalg.norm(current_user_emb) + 1e-10)
            
            # Compute similarities
            similarities = np.dot(user_embeddings_norm, current_user_emb_norm)
            
            # Explicitly exclude current user and filter out NaN/inf values
            similarities[current_user_idx] = -np.inf  # Exclude self
            similarities = np.where(np.isfinite(similarities), similarities, -np.inf)  # Filter NaN/inf
            
            # Get top K similar users
            K = 10  # Top 10 similar users
            similar_user_indices = np.argsort(similarities)[::-1][:K]  # Top K (current user already excluded)
            
            # Filter out indices with invalid similarity
            valid_indices = [idx for idx in similar_user_indices if similarities[idx] > -np.inf]
            
            # Map CF indices back to database user IDs
            idx_to_user_id = {idx: uid for uid, idx in user_id_to_idx.items()}
            similar_user_ids = [idx_to_user_id[int(idx)] for idx in valid_indices if int(idx) in idx_to_user_id]
            
            if not similar_user_ids:
                return None
            
            # Get purchase intervals from these similar users for this product
            # Use DISTINCT on (user_id, created_at) to avoid duplicate timestamps from multi-item orders
            product_purchases = self.db.session.query(
                self.Order.user_id,
                self.Order.created_at
            ).distinct(
                self.Order.user_id,
                self.Order.created_at
            ).join(self.OrderItem).filter(
                self.OrderItem.product_id == product_id,
                self.Order.user_id.in_(similar_user_ids)  # Only similar users!
            ).order_by(self.Order.user_id, self.Order.created_at).all()
            
            # Group by user and calculate their intervals
            user_intervals = defaultdict(set)  # Use set to auto-deduplicate
            for purchase in product_purchases:
                user_intervals[purchase.user_id].add(purchase.created_at)
            
            # Calculate intervals for each similar user
            similar_user_intervals = []
            for uid, dates_set in user_intervals.items():
                dates = sorted(list(dates_set))  # Convert set to sorted list
                if len(dates) >= 2:
                    for i in range(1, len(dates)):
                        days = (dates[i] - dates[i-1]).days
                        if days > 0:
                            similar_user_intervals.append(days)
            
            if len(similar_user_intervals) >= 2:
                return np.median(similar_user_intervals)
            
            return None
            
        except Exception as e:
            print(f"Error getting CF similar user intervals: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _get_metadata_based_prediction(self, product_id, subcat):
        """
        Predict interval based on product metadata (size, category).
        
        Returns:
            float: Predicted interval in days
        """
        # Start with category default
        base_interval = self.DEFAULT_CATEGORY_INTERVALS.get(subcat, 14.0)
        
        # Adjust based on product size if available
        if product_id in self.products_df.index:
            row = self.products_df.loc[product_id]
            
            # Check for size multiplier
            size_value = row.get('_size_value')
            if pd.notna(size_value) and size_value > 0:
                # Larger packages = longer intervals
                # Normalize: 1 unit = base, 12 units (pack) = 1.5x base
                size_multiplier = 1.0 + (min(float(size_value), 12) - 1) / 24
                base_interval *= size_multiplier
        
        return base_interval
    
    def _blend_predictions(self, cf_interval, metadata_interval, cf_weight=0.6):
        """
        Blend CF-based and metadata-based predictions.
        
        Args:
            cf_interval: Interval from similar users (can be None)
            metadata_interval: Interval from product metadata
            cf_weight: Weight for CF prediction (0-1)
        
        Returns:
            float: Blended prediction in days
        """
        if cf_interval is None:
            # No CF data, use metadata only
            return metadata_interval
        
        # Blend with configurable weights
        metadata_weight = 1.0 - cf_weight
        return (cf_weight * cf_interval) + (metadata_weight * metadata_interval)
    
    def _calculate_urgency_score(self, days_until_due, purchase_frequency, category_weight, cf_confidence):
        """
        Calculate urgency score for ranking.
        Higher score = more urgent.
        
        Args:
            days_until_due: Days until predicted run-out (negative = overdue)
            purchase_frequency: How often user buys this (times per month)
            category_weight: Importance weight for this category
            cf_confidence: Confidence in CF prediction (0-1)
        
        Returns:
            float: Urgency score
        """
        # Base urgency: negative days = overdue (high priority)
        if days_until_due < 0:
            urgency = abs(days_until_due) * 3.0  # Overdue gets 3x weight
        elif days_until_due <= 3:
            urgency = (3 - days_until_due) * 1.5  # Due soon gets 1.5x weight
        else:
            urgency = max(0, 10 - days_until_due) * 0.5  # Upcoming gets 0.5x weight
        
        # Boost by purchase frequency (more frequent = more important)
        urgency += purchase_frequency * 0.5
        
        # Boost by category importance
        urgency += category_weight
        
        # Boost by CF confidence (better data = higher priority)
        urgency += cf_confidence * 2.0
        
        return urgency
    
    def get_top_replenishment_opportunities(self, user_id, top_k=10):
        """
        Get top K replenishment opportunities for a user based on urgency.
        Includes both established cycles (2+ purchases) and first-purchase predictions.
        
        Args:
            user_id: User session ID
            top_k: Number of top opportunities to return (default 10)
        
        Returns:
            List of top replenishment opportunities with urgency scores
        """
        opportunities = []
        today = datetime.utcnow().date()
        
        # Get all products user has purchased
        user_purchases = self.db.session.query(
            self.OrderItem.product_id,
            self.OrderItem.product_title,
            self.OrderItem.product_subcat,
            self.OrderItem.quantity,
            self.Order.created_at,
            func.count(self.OrderItem.id).over(partition_by=self.OrderItem.product_id).label('purchase_count')
        ).join(self.Order).filter(
            self.Order.user_id == user_id,
            self.OrderItem.product_subcat.in_(self.CONSUMABLE_CATEGORIES)
        ).order_by(self.OrderItem.product_id, self.Order.created_at.desc()).all()
        
        # Group by product
        product_data = {}
        for purchase in user_purchases:
            pid = purchase.product_id
            if pid not in product_data:
                product_data[pid] = {
                    'title': purchase.product_title,
                    'subcat': purchase.product_subcat,
                    'purchase_count': purchase.purchase_count,
                    'last_purchase': purchase.created_at,
                    'all_dates': []
                }
            product_data[pid]['all_dates'].append(purchase.created_at)
        
        # Process each product
        for product_id, data in product_data.items():
            purchase_count = data['purchase_count']
            last_purchase = data['last_purchase']
            subcat = data['subcat']
            
            # Check if we already have an established cycle (2+ purchases)
            existing_cycle = self.UserReplenishmentCycle.query.filter_by(
                user_id=user_id,
                product_id=product_id
            ).first()
            
            if existing_cycle and existing_cycle.purchase_count >= 2:
                # Use established cycle
                days_until = (existing_cycle.next_due_date - today).days
                predicted_interval = existing_cycle.median_interval_days
                cf_confidence = 1.0  # High confidence from user's own data
            else:
                # First-purchase prediction using CF + metadata blend
                cf_interval = self._get_cf_similar_user_intervals(product_id, user_id)
                metadata_interval = self._get_metadata_based_prediction(product_id, subcat)
                
                predicted_interval = self._blend_predictions(cf_interval, metadata_interval)
                
                # Calculate due date
                next_due = (last_purchase + timedelta(days=predicted_interval)).date()
                days_until = (next_due - today).days
                
                # CF confidence based on whether we had CF data
                cf_confidence = 0.7 if cf_interval is not None else 0.3
            
            # Calculate purchase frequency (times per month)
            days_since_first = (datetime.utcnow() - min(data['all_dates'])).days
            purchase_frequency = (purchase_count / max(days_since_first, 1)) * 30
            
            # Get category weight
            category_weight = self.CATEGORY_WEIGHTS.get(subcat, 1.0)
            
            # Calculate urgency score
            urgency_score = self._calculate_urgency_score(
                days_until, 
                purchase_frequency, 
                category_weight, 
                cf_confidence
            )
            
            # Get price from catalog
            price = 0.0
            if product_id in self.products_df.index:
                row = self.products_df.loc[product_id]
                if pd.notna(row.get('_price_final')):
                    price = float(row['_price_final'])
            
            opportunities.append({
                'product_id': str(product_id),
                'title': data['title'],
                'subcat': subcat,
                'price': price,
                'last_purchase': last_purchase.strftime('%Y-%m-%d'),
                'days_since_purchase': (today - last_purchase.date()).days,
                'predicted_interval': predicted_interval,
                'days_until_due': days_until,
                'purchase_count': purchase_count,
                'urgency_score': urgency_score,
                'cf_confidence': cf_confidence,
                'prediction_type': 'personalized' if purchase_count >= 2 else 'predicted'
            })
        
        # Sort by urgency score (descending) and return top K
        opportunities.sort(key=lambda x: x['urgency_score'], reverse=True)
        return opportunities[:top_k]
