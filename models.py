import re


def init_models(db):
    """Initialize models with the database instance"""
    
    class Product(db.Model):
        """Database model for grocery products"""
        __tablename__ = 'products'
        __table_args__ = {'extend_existing': True}
    
        id = db.Column(db.Integer, primary_key=True)
        sub_category = db.Column(db.String(100), nullable=False)
        price_text = db.Column(db.String(50), nullable=True)  # Original price string
        price_numeric = db.Column(db.Numeric(10, 2), nullable=True)  # Parsed numeric price
        discount = db.Column(db.String(100), nullable=True)
        rating_text = db.Column(db.String(200), nullable=True)  # Original rating string
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
        product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
        quantity = db.Column(db.Integer, default=1, nullable=False)
        added_at = db.Column(db.DateTime, default=db.func.current_timestamp())
        
        # Relationship to Product
        product = db.relationship('Product', backref='cart_items')
        
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
    
    return Product, ShoppingCart, UserBudget