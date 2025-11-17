import re


def init_models(db):
    """Initialize models with the database instance"""
    
    class Product(db.Model):
        """Database model for grocery products"""
        __tablename__ = 'products'
        __table_args__ = {'extend_existing': True}
    
        id = db.Column(db.Integer, primary_key=True)
        sub_category = db.Column(db.String(200), nullable=False)
        price_text = db.Column(db.String(100), nullable=True)  # Original price string
        price_numeric = db.Column(db.Numeric(10, 2), nullable=True)  # Parsed numeric price
        discount = db.Column(db.String(200), nullable=True)
        rating_text = db.Column(db.String(500), nullable=True)  # Original rating string
        rating_numeric = db.Column(db.Numeric(3, 2), nullable=True)  # Parsed numeric rating (0-5)
        review_count = db.Column(db.Integer, nullable=True)  # Number of reviews
        title = db.Column(db.Text, nullable=False)
        currency = db.Column(db.String(10), nullable=True)
        feature = db.Column(db.Text, nullable=True)
        description = db.Column(db.Text, nullable=True)
        
        # Nutritional information
        calories = db.Column(db.Integer, nullable=True)
        fat_g = db.Column(db.Numeric(5, 1), nullable=True)
        carbs_g = db.Column(db.Numeric(5, 1), nullable=True)
        sugar_g = db.Column(db.Numeric(5, 1), nullable=True)
        protein_g = db.Column(db.Numeric(5, 1), nullable=True)
        sodium_mg = db.Column(db.Integer, nullable=True)
        
        def __repr__(self):
            return f'<Product {self.id}: {self.title[:50]}...>'
        
        @staticmethod
        def parse_price(price_text):
            """Extract numeric price from price text like '$56.99'"""
            if not price_text:
                return None
            # Remove currency symbols and spaces, extract decimal number
            price_match = re.search(r'[\d,]+\.?\d*', price_text.replace('$', '').replace(',', ''))
            if price_match:
                try:
                    return float(price_match.group())
                except ValueError:
                    return None
            return None
        
        @staticmethod
        def parse_rating(rating_text):
            """Extract numeric rating and review count from rating text"""
            if not rating_text:
                return None, None
            
            # Extract rating like "Rated 4.3 out of 5 stars based on 265 reviews"
            rating_match = re.search(r'Rated (\d+\.?\d*) out of', rating_text)
            review_match = re.search(r'based on (\d+) review', rating_text)
            
            rating = None
            reviews = None
            
            if rating_match:
                try:
                    rating = float(rating_match.group(1))
                except ValueError:
                    pass
                    
            if review_match:
                try:
                    reviews = int(review_match.group(1))
                except ValueError:
                    pass
            
            return rating, reviews

    # Add shopping cart and budget models
    class ShoppingCart(db.Model):
        """Shopping cart to track items for budget calculations"""
        __tablename__ = 'shopping_cart'
        __table_args__ = {'extend_existing': True}
        
        id = db.Column(db.Integer, primary_key=True)
        session_id = db.Column(db.String(255), nullable=False)  # Track by session
        product_id = db.Column(db.BigInteger, nullable=False, index=True)  # BigInteger for 63-bit IDs, no FK since products in memory
        quantity = db.Column(db.Integer, default=1, nullable=False)
        added_at = db.Column(db.DateTime, default=db.func.current_timestamp())
        
        def __repr__(self):
            return f'<CartItem {self.id}: {self.quantity}x Product {self.product_id}>'

    class UserBudget(db.Model):
        """User budget settings"""
        __tablename__ = 'user_budget'
        __table_args__ = {'extend_existing': True}
        
        id = db.Column(db.Integer, primary_key=True)
        session_id = db.Column(db.String(255), nullable=False, unique=True)
        budget_amount = db.Column(db.Numeric(10, 2), nullable=False)
        warning_threshold = db.Column(db.Numeric(5, 2), default=80.0)  # 80% default
        created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
        
        def __repr__(self):
            return f'<Budget {self.id}: ${self.budget_amount} ({self.warning_threshold}%)>'

    class User(db.Model):
        """User model for tracking customer identity and preferences"""
        __tablename__ = 'users'
        __table_args__ = {'extend_existing': True}
        
        id = db.Column(db.Integer, primary_key=True)
        session_id = db.Column(db.String(255), nullable=False, unique=True, index=True)
        name = db.Column(db.String(255), nullable=True)  # User's display name
        password_hash = db.Column(db.String(255), nullable=True)  # Hashed password for email/password login
        created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
        last_active = db.Column(db.DateTime, default=db.func.current_timestamp(), onupdate=db.func.current_timestamp())
        
        # ISRec intent tracking with EMA smoothing
        intent_ema = db.Column(db.Numeric(5, 4), default=0.5, nullable=False)  # Smoothed intent score [0, 1]
        
        # Relationships
        orders = db.relationship('Order', backref='user', lazy='dynamic', cascade='all, delete-orphan')
        events = db.relationship('UserEvent', backref='user', lazy='dynamic', cascade='all, delete-orphan')
        
        def __repr__(self):
            return f'<User {self.id}: session {self.session_id[:8]}...>'

    class Order(db.Model):
        """Order model for completed purchases"""
        __tablename__ = 'orders'
        __table_args__ = {'extend_existing': True}
        
        id = db.Column(db.Integer, primary_key=True)
        user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
        total_amount = db.Column(db.Numeric(10, 2), nullable=False)
        item_count = db.Column(db.Integer, nullable=False)
        created_at = db.Column(db.DateTime, default=db.func.current_timestamp(), index=True)
        
        # Relationships
        order_items = db.relationship('OrderItem', backref='order', lazy='dynamic', cascade='all, delete-orphan')
        
        def __repr__(self):
            return f'<Order {self.id}: ${self.total_amount} ({self.item_count} items)>'

    class OrderItem(db.Model):
        """Individual items within an order"""
        __tablename__ = 'order_items'
        __table_args__ = {'extend_existing': True}
        
        id = db.Column(db.Integer, primary_key=True)
        order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False, index=True)
        product_id = db.Column(db.BigInteger, nullable=False, index=True)  # BigInteger for 63-bit IDs, no FK since products in memory
        product_title = db.Column(db.Text, nullable=False)
        product_subcat = db.Column(db.String(200), nullable=False, index=True)
        quantity = db.Column(db.Integer, nullable=False)
        unit_price = db.Column(db.Numeric(10, 2), nullable=False)
        line_total = db.Column(db.Numeric(10, 2), nullable=False)
        
        def __repr__(self):
            return f'<OrderItem {self.id}: {self.quantity}x {self.product_title[:30]}...>'

    class UserEvent(db.Model):
        """User browsing and interaction events for behavior tracking"""
        __tablename__ = 'user_events'
        __table_args__ = {'extend_existing': True}
        
        id = db.Column(db.Integer, primary_key=True)
        user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
        event_type = db.Column(db.String(50), nullable=False, index=True)
        product_id = db.Column(db.BigInteger, nullable=True, index=True)  # BigInteger for 63-bit IDs, no FK since products in memory
        product_title = db.Column(db.Text, nullable=True)
        product_subcat = db.Column(db.String(200), nullable=True, index=True)
        event_data = db.Column(db.JSON, nullable=True)
        created_at = db.Column(db.DateTime, default=db.func.current_timestamp(), index=True)
        
        def __repr__(self):
            return f'<UserEvent {self.id}: {self.event_type} by User {self.user_id}>'

    class ReplenishableProduct(db.Model):
        """Tracks products identified as replenishable consumables"""
        __tablename__ = 'replenishable_products'
        __table_args__ = {'extend_existing': True}
        
        id = db.Column(db.Integer, primary_key=True)
        product_id = db.Column(db.BigInteger, nullable=False, unique=True, index=True)
        product_title = db.Column(db.Text, nullable=False)
        product_subcat = db.Column(db.String(200), nullable=False, index=True)
        avg_interval_days = db.Column(db.Numeric(10, 2), nullable=True)
        total_purchases = db.Column(db.Integer, default=0)
        unique_users = db.Column(db.Integer, default=0)
        is_consumable = db.Column(db.Boolean, default=True)
        size_value = db.Column(db.Numeric(10, 2), nullable=True)
        size_unit = db.Column(db.String(50), nullable=True)
        last_updated = db.Column(db.DateTime, default=db.func.current_timestamp(), onupdate=db.func.current_timestamp())
        
        def __repr__(self):
            return f'<ReplenishableProduct {self.product_id}: {self.product_title[:30]}... (~{self.avg_interval_days} days)>'

    class UserReplenishmentCycle(db.Model):
        """Tracks user-specific replenishment patterns for products"""
        __tablename__ = 'user_replenishment_cycles'
        __table_args__ = {'extend_existing': True}
        
        id = db.Column(db.Integer, primary_key=True)
        user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
        product_id = db.Column(db.BigInteger, nullable=False, index=True)
        product_title = db.Column(db.Text, nullable=False)
        product_subcat = db.Column(db.String(200), nullable=False)
        
        # Purchase pattern tracking
        first_purchase_date = db.Column(db.DateTime, nullable=False)
        last_purchase_date = db.Column(db.DateTime, nullable=False, index=True)
        purchase_count = db.Column(db.Integer, default=1)
        
        # Interval calculation
        median_interval_days = db.Column(db.Numeric(10, 2), nullable=True)
        last_quantity = db.Column(db.Integer, default=1)
        
        # Prediction
        next_due_date = db.Column(db.Date, nullable=True, index=True)
        adjusted_interval_days = db.Column(db.Numeric(10, 2), nullable=True)
        
        # Status
        is_active = db.Column(db.Boolean, default=True, index=True)
        is_gift_flagged = db.Column(db.Boolean, default=False)
        skip_until_date = db.Column(db.Date, nullable=True)
        
        created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
        updated_at = db.Column(db.DateTime, default=db.func.current_timestamp(), onupdate=db.func.current_timestamp())
        
        def __repr__(self):
            return f'<ReplenishmentCycle User {self.user_id}: {self.product_title[:30]}... (next: {self.next_due_date})>'

    class RecommendationInteraction(db.Model):
        """Tracks user interactions with AI recommendations for behavioral analytics"""
        __tablename__ = 'recommendation_interactions'
        __table_args__ = {'extend_existing': True}
        
        id = db.Column(db.Integer, primary_key=True)
        user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
        
        # Recommendation details
        recommendation_id = db.Column(db.String(100), nullable=False, index=True)
        original_product_id = db.Column(db.BigInteger, nullable=False, index=True)
        recommended_product_id = db.Column(db.BigInteger, nullable=False, index=True)
        original_product_title = db.Column(db.Text, nullable=False)
        recommended_product_title = db.Column(db.Text, nullable=False)
        expected_saving = db.Column(db.Numeric(10, 2), nullable=True)
        recommendation_reason = db.Column(db.Text, nullable=True)
        has_explanation = db.Column(db.Boolean, default=True)
        
        # Interaction tracking
        action_type = db.Column(db.String(50), nullable=False, index=True)
        shown_at = db.Column(db.DateTime, default=db.func.current_timestamp(), index=True)
        action_at = db.Column(db.DateTime, nullable=True)
        time_to_action_seconds = db.Column(db.Integer, nullable=True)
        scroll_depth_percent = db.Column(db.Integer, nullable=True)
        
        # Product attributes at time of recommendation (for drift detection)
        original_price = db.Column(db.Numeric(10, 2), nullable=True)
        recommended_price = db.Column(db.Numeric(10, 2), nullable=True)
        original_protein = db.Column(db.Numeric(5, 1), nullable=True)
        recommended_protein = db.Column(db.Numeric(5, 1), nullable=True)
        original_sugar = db.Column(db.Numeric(5, 1), nullable=True)
        recommended_sugar = db.Column(db.Numeric(5, 1), nullable=True)
        original_calories = db.Column(db.Integer, nullable=True)
        recommended_calories = db.Column(db.Integer, nullable=True)
        
        # Removal tracking (for BCR)
        removed_from_cart_at = db.Column(db.DateTime, nullable=True)
        was_removed = db.Column(db.Boolean, default=False)
        
        created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
        
        def __repr__(self):
            return f'<RecommendationInteraction {self.id}: {self.action_type} by User {self.user_id}>'

    class UserGoal(db.Model):
        """User health and nutrition goals for goal alignment tracking"""
        __tablename__ = 'user_goals'
        __table_args__ = {'extend_existing': True}
        
        id = db.Column(db.Integer, primary_key=True)
        user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
        
        # Goal configuration
        goal_type = db.Column(db.String(50), nullable=False, index=True)
        goal_direction = db.Column(db.String(20), nullable=False)
        target_value = db.Column(db.Numeric(10, 2), nullable=True)
        
        # Status
        is_active = db.Column(db.Boolean, default=True, index=True)
        priority = db.Column(db.Integer, default=1)
        
        created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
        updated_at = db.Column(db.DateTime, default=db.func.current_timestamp(), onupdate=db.func.current_timestamp())
        
        def __repr__(self):
            return f'<UserGoal {self.id}: User {self.user_id} - {self.goal_direction} {self.goal_type}>'
    
    return Product, ShoppingCart, UserBudget, User, Order, OrderItem, UserEvent, ReplenishableProduct, UserReplenishmentCycle, RecommendationInteraction, UserGoal