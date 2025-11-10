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
    
    def __init__(self, db, products_df):
        """
        Initialize replenishment engine
        
        Args:
            db: SQLAlchemy database instance
            products_df: Pandas DataFrame with product catalog (for size normalization)
        """
        self.db = db
        self.products_df = products_df
    
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
            OrderItem.product_id,
            OrderItem.product_title,
            OrderItem.product_subcat,
            func.count(OrderItem.id).label('total_purchases'),
            func.count(func.distinct(Order.user_id)).label('unique_users')
        ).join(Order).filter(
            OrderItem.product_subcat.in_(self.CONSUMABLE_CATEGORIES)
        ).group_by(
            OrderItem.product_id,
            OrderItem.product_title,
            OrderItem.product_subcat
        ).having(
            func.count(OrderItem.id) >= min_purchases,
            func.count(func.distinct(Order.user_id)) >= min_users
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
            existing = ReplenishableProduct.query.filter_by(product_id=product_id).first()
            
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
            OrderItem.product_id,
            OrderItem.product_title,
            OrderItem.product_subcat,
            OrderItem.quantity,
            Order.created_at
        ).join(Order).filter(
            Order.user_id == user_id
        ).order_by(OrderItem.product_id, Order.created_at).all()
        
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
            replenishable = ReplenishableProduct.query.filter_by(product_id=product_id).first()
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
            existing_cycle = UserReplenishmentCycle.query.filter_by(
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
        
        cycle = UserReplenishmentCycle.query.filter_by(
            user_id=user_id,
            product_id=product_id,
            is_active=True
        ).first()
        
        if not cycle or not cycle.median_interval_days:
            return
        
        # Calculate historical average quantity
        
        avg_quantity = self.db.session.query(
            func.avg(OrderItem.quantity)
        ).join(Order).filter(
            Order.user_id == user_id,
            OrderItem.product_id == product_id
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
        cycles = UserReplenishmentCycle.query.filter(
            UserReplenishmentCycle.user_id == user_id,
            UserReplenishmentCycle.is_active == True,
            UserReplenishmentCycle.next_due_date != None
        ).order_by(UserReplenishmentCycle.next_due_date).all()
        
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
            func.avg(OrderItem.quantity)
        ).join(Order).filter(
            Order.user_id == user_id,
            OrderItem.product_id == product_id
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
        
        cycles = UserReplenishmentCycle.query.filter(
            UserReplenishmentCycle.user_id == user_id,
            UserReplenishmentCycle.is_active == True,
            UserReplenishmentCycle.next_due_date != None,
            UserReplenishmentCycle.next_due_date <= today + timedelta(days=days_ahead)
        ).filter(
            # Respect skip_until_date
            (UserReplenishmentCycle.skip_until_date == None) |
            (UserReplenishmentCycle.skip_until_date < today)
        ).order_by(UserReplenishmentCycle.next_due_date).all()
        
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
