import os
from flask import Flask, render_template, jsonify, request, session, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
import uuid


class Base(DeclarativeBase):
    pass


db = SQLAlchemy(model_class=Base)

# create the app
app = Flask(__name__)
# setup a secret key, required by sessions
app.secret_key = os.environ.get("FLASK_SECRET_KEY") or "a secret key"
# configure the database, relative to the app instance folder
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}
# initialize the app with the extension, flask-sqlalchemy >= 3.0.x
db.init_app(app)

with app.app_context():
    # Initialize models with db instance  
    from models import init_models
    Product, ShoppingCart, UserBudget = init_models(db)
    # Store models in globals for use in routes
    globals()['Product'] = Product
    globals()['ShoppingCart'] = ShoppingCart  
    globals()['UserBudget'] = UserBudget
    # Create all tables
    db.create_all()


@app.route("/")
def index():
    """Main page with shopping interface and budget tracking"""
    # Ensure user has a session ID
    if 'session_id' not in session:
        session['session_id'] = str(uuid.uuid4())
    
    session_id = session['session_id']
    
    # Get user budget
    user_budget = UserBudget.query.filter_by(session_id=session_id).first()
    
    # Get cart total
    cart_items = ShoppingCart.query.filter_by(session_id=session_id).all()
    cart_total = sum(float(item.product.price_numeric or 0) * item.quantity for item in cart_items)
    cart_count = sum(item.quantity for item in cart_items)
    
    # Calculate budget status
    budget_warning = ""
    budget_status = ""
    if user_budget:
        budget_amount = float(user_budget.budget_amount)
        threshold = float(user_budget.warning_threshold)
        warning_amount = budget_amount * (threshold / 100)
        
        if cart_total >= warning_amount:
            budget_warning = f"""
            <div style="background-color: #fff3cd; border: 1px solid #ffeaa7; padding: 10px; margin: 10px 0; border-radius: 5px;">
                ⚠️ <strong>Budget Warning:</strong> You've reached {(cart_total/budget_amount)*100:.1f}% of your ${budget_amount:.2f} budget!
                <br>Current spending: ${cart_total:.2f} | Budget limit: ${budget_amount:.2f}
            </div>
            """
        
        budget_status = f"""
        <div style="background-color: #e3f2fd; padding: 10px; margin: 10px 0; border-radius: 5px;">
            <strong>Your Budget:</strong> ${budget_amount:.2f} | 
            <strong>Spent:</strong> ${cart_total:.2f} | 
            <strong>Remaining:</strong> ${budget_amount - cart_total:.2f}
            <div style="background-color: #ddd; height: 20px; border-radius: 10px; margin-top: 5px;">
                <div style="background-color: {'#ff4444' if cart_total >= warning_amount else '#4CAF50'}; 
                           width: {min(100, (cart_total/budget_amount)*100):.1f}%; 
                           height: 100%; border-radius: 10px;"></div>
            </div>
        </div>
        """
    
    # Get some products to display
    products = Product.query.limit(10).all()
    
    return f"""
    <html>
    <head>
        <title>Smart Grocery Shopping with Budget Tracking</title>
        <style>
            body {{ font-family: Arial, sans-serif; max-width: 1200px; margin: 0 auto; padding: 20px; }}
            .product {{ border: 1px solid #ddd; margin: 10px; padding: 15px; border-radius: 5px; }}
            .cart-btn {{ background-color: #4CAF50; color: white; padding: 8px 16px; border: none; border-radius: 4px; cursor: pointer; }}
            .cart-btn:hover {{ background-color: #45a049; }}
            .nav {{ background-color: #f8f9fa; padding: 10px; margin-bottom: 20px; border-radius: 5px; }}
            .nav a {{ margin-right: 15px; text-decoration: none; color: #007bff; }}
        </style>
    </head>
    <body>
        <div class="nav">
            <a href="/">🏠 Home</a>
            <a href="/cart">🛒 Cart ({cart_count} items)</a>
            <a href="/budget">💰 Set Budget</a>
            <a href="/import">📁 Import Data</a>
        </div>
        
        <h1>🛒 Smart Grocery Shopping</h1>
        
        {budget_warning}
        {budget_status}
        
        <h2>Featured Products</h2>
        {"".join([f'''
        <div class="product">
            <h3>{product.title}</h3>
            <p><strong>Price:</strong> {product.price_text} | <strong>Category:</strong> {product.sub_category}</p>
            <p><strong>Rating:</strong> {product.rating_text or "No rating"}</p>
            <form action="/add_to_cart" method="post" style="display: inline;">
                <input type="hidden" name="product_id" value="{product.id}">
                <input type="number" name="quantity" value="1" min="1" max="10" style="width: 60px;">
                <button type="submit" class="cart-btn">Add to Cart</button>
            </form>
        </div>
        ''' for product in products])}
        
        <p><a href="/products">View All Products</a></p>
    </body>
    </html>
    """


@app.route("/api/products")
def api_products():
    """API endpoint to get all products"""
    products = Product.query.all()
    return jsonify([{
        'id': p.id,
        'title': p.title,
        'sub_category': p.sub_category,
        'price_text': p.price_text,
        'price_numeric': float(p.price_numeric) if p.price_numeric else None,
        'discount': p.discount,
        'rating_text': p.rating_text,
        'rating_numeric': float(p.rating_numeric) if p.rating_numeric else None,
        'currency': p.currency,
        'feature': p.feature,
        'description': p.description
    } for p in products])


@app.route("/add_to_cart", methods=["POST"])
def add_to_cart():
    """Add item to shopping cart with budget checking and alternatives"""
    if 'session_id' not in session:
        session['session_id'] = str(uuid.uuid4())
    
    session_id = session['session_id']
    product_id = request.form.get('product_id')
    quantity = int(request.form.get('quantity', 1))
    
    # Get the product being added
    product = Product.query.get(product_id)
    if not product:
        return redirect(url_for('index'))
    
    # Calculate current cart total
    cart_items = ShoppingCart.query.filter_by(session_id=session_id).all()
    current_total = sum(float(item.product.price_numeric or 0) * item.quantity for item in cart_items)
    
    # Calculate new total if this item is added
    item_cost = float(product.price_numeric or 0) * quantity
    new_total = current_total + item_cost
    
    # Check budget
    user_budget = UserBudget.query.filter_by(session_id=session_id).first()
    
    # Add item to cart regardless of budget (user might want to proceed)
    existing_item = ShoppingCart.query.filter_by(
        session_id=session_id, 
        product_id=product_id
    ).first()
    
    if existing_item:
        existing_item.quantity += quantity
    else:
        cart_item = ShoppingCart(
            session_id=session_id,
            product_id=product_id,
            quantity=quantity
        )
        db.session.add(cart_item)
    
    db.session.commit()
    
    # If budget is exceeded, show alternatives page
    if user_budget and new_total > float(user_budget.budget_amount):
        from flask import Response
        overage = new_total - float(user_budget.budget_amount)
        return Response(status=303, headers={'Location': url_for('budget_exceeded', product_id=product_id, quantity=quantity, overage=overage)})
    
    return Response(status=303, headers={'Location': url_for('index')})


@app.route("/cart")
def view_cart():
    """View shopping cart with budget tracking"""
    if 'session_id' not in session:
        session['session_id'] = str(uuid.uuid4())
    
    session_id = session['session_id']
    cart_items = ShoppingCart.query.filter_by(session_id=session_id).all()
    cart_total = sum(float(item.product.price_numeric or 0) * item.quantity for item in cart_items)
    
    # Get budget info
    user_budget = UserBudget.query.filter_by(session_id=session_id).first()
    budget_warning = ""
    
    if user_budget:
        budget_amount = float(user_budget.budget_amount)
        threshold = float(user_budget.warning_threshold)
        if cart_total >= budget_amount * (threshold / 100):
            budget_warning = f"<div style='background-color: #ffebee; padding: 10px; margin: 10px 0;'>⚠️ You've reached {threshold}% of your budget!</div>"
    
    cart_html = ""
    if cart_items:
        cart_html = "<h2>Your Cart</h2>" + "".join([
            f"""<div style="border: 1px solid #ddd; padding: 10px; margin: 5px 0;">
                <strong>{item.product.title}</strong><br>
                Price: {item.product.price_text} x {item.quantity} = ${float(item.product.price_numeric or 0) * item.quantity:.2f}<br>
                <form action="/remove_from_cart" method="post" style="display: inline;">
                    <input type="hidden" name="cart_id" value="{item.id}">
                    <button type="submit" style="background-color: #f44336; color: white; padding: 5px 10px; border: none; border-radius: 3px;">Remove</button>
                </form>
            </div>"""
            for item in cart_items
        ])
    else:
        cart_html = "<p>Your cart is empty. <a href='/'>Continue shopping</a></p>"
    
    return f"""
    <html>
    <head><title>Shopping Cart</title></head>
    <body style="font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px;">
        <h1>🛒 Shopping Cart</h1>
        <p><a href="/">← Back to Shopping</a> | <a href="/budget">💰 Set Budget</a></p>
        
        {budget_warning}
        
        {cart_html}
        
        <div style="background-color: #e3f2fd; padding: 15px; margin: 20px 0; border-radius: 5px;">
            <h3>Cart Total: ${cart_total:.2f}</h3>
            {f"Budget: ${user_budget.budget_amount} | Remaining: ${float(user_budget.budget_amount) - cart_total:.2f}" if user_budget else "<a href='/budget'>Set a budget</a>"}
        </div>
        
        <p><a href="/">Continue Shopping</a></p>
    </body>
    </html>
    """


@app.route("/remove_from_cart", methods=["POST"])
def remove_from_cart():
    """Remove item from cart"""
    cart_id = request.form.get('cart_id')
    item = ShoppingCart.query.get(cart_id)
    if item:
        db.session.delete(item)
        db.session.commit()
    return redirect(url_for('view_cart'))


@app.route("/budget", methods=["GET", "POST"])
def budget_settings():
    """Set or update budget"""
    if 'session_id' not in session:
        session['session_id'] = str(uuid.uuid4())
    
    session_id = session['session_id']
    
    if request.method == 'POST':
        budget_amount = float(request.form.get('budget_amount', 0))
        warning_threshold = float(request.form.get('warning_threshold', 80))
        
        # Update or create budget
        user_budget = UserBudget.query.filter_by(session_id=session_id).first()
        if user_budget:
            user_budget.budget_amount = budget_amount
            user_budget.warning_threshold = warning_threshold
        else:
            user_budget = UserBudget(
                session_id=session_id,
                budget_amount=budget_amount,
                warning_threshold=warning_threshold
            )
            db.session.add(user_budget)
        
        db.session.commit()
        return redirect(url_for('index'))
    
    # GET request - show form
    user_budget = UserBudget.query.filter_by(session_id=session_id).first()
    current_budget = user_budget.budget_amount if user_budget else 100
    current_threshold = user_budget.warning_threshold if user_budget else 80
    
    return f"""
    <html>
    <head><title>Budget Settings</title></head>
    <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
        <h1>💰 Budget Settings</h1>
        <p><a href="/">← Back to Shopping</a> | <a href="/cart">🛒 View Cart</a></p>
        
        <form method="post" style="background-color: #f8f9fa; padding: 20px; border-radius: 5px;">
            <div style="margin-bottom: 15px;">
                <label for="budget_amount"><strong>Shopping Budget ($):</strong></label><br>
                <input type="number" id="budget_amount" name="budget_amount" 
                       value="{current_budget}" step="0.01" min="1" 
                       style="width: 100px; padding: 5px; margin-top: 5px;" required>
            </div>
            
            <div style="margin-bottom: 15px;">
                <label for="warning_threshold"><strong>Warning Threshold (%):</strong></label><br>
                <input type="number" id="warning_threshold" name="warning_threshold" 
                       value="{current_threshold}" min="50" max="100" 
                       style="width: 100px; padding: 5px; margin-top: 5px;" required>
                <small style="color: #666;">You'll get a warning when you reach this percentage of your budget</small>
            </div>
            
            <button type="submit" style="background-color: #4CAF50; color: white; padding: 10px 20px; border: none; border-radius: 4px; cursor: pointer;">
                Save Budget Settings
            </button>
        </form>
        
        <div style="background-color: #e8f5e8; padding: 15px; margin-top: 20px; border-radius: 5px;">
            <h3>How it works:</h3>
            <ul>
                <li>Set your shopping budget (e.g., $100)</li>
                <li>Choose when to get warnings (e.g., at 80% = $80)</li>
                <li>Add items to your cart and track your spending</li>
                <li>Get alerts when you approach your limit!</li>
            </ul>
        </div>
    </body>
    </html>
    """


@app.route("/products")
def all_products():
    """Show all products with search"""
    search = request.args.get('search', '')
    category = request.args.get('category', '')
    
    query = Product.query
    if search:
        query = query.filter(Product.title.ilike(f'%{search}%'))
    if category:
        query = query.filter(Product.sub_category == category)
    
    products = query.all()
    categories = db.session.query(Product.sub_category).distinct().all()
    
    return f"""
    <html>
    <head><title>All Products</title></head>
    <body style="font-family: Arial, sans-serif; max-width: 1200px; margin: 0 auto; padding: 20px;">
        <h1>All Products</h1>
        <p><a href="/">← Back to Home</a></p>
        
        <form method="get" style="margin: 20px 0;">
            <input type="text" name="search" value="{search}" placeholder="Search products..." style="padding: 5px; width: 200px;">
            <select name="category" style="padding: 5px;">
                <option value="">All Categories</option>
                {''.join([f'<option value="{cat[0]}" {"selected" if cat[0] == category else ""}>{cat[0]}</option>' for cat in categories])}
            </select>
            <button type="submit" style="padding: 5px 10px;">Search</button>
        </form>
        
        <div>
            {''.join([f'''<div style="border: 1px solid #ddd; margin: 10px; padding: 15px; border-radius: 5px;">
                <h3>{product.title}</h3>
                <p><strong>Price:</strong> {product.price_text} | <strong>Category:</strong> {product.sub_category}</p>
                <form action="/add_to_cart" method="post" style="display: inline;">
                    <input type="hidden" name="product_id" value="{product.id}">
                    <input type="number" name="quantity" value="1" min="1" max="10" style="width: 60px;">
                    <button type="submit" style="background-color: #4CAF50; color: white; padding: 8px 16px; border: none; border-radius: 4px;">Add to Cart</button>
                </form>
            </div>''' for product in products])}
        </div>
    </body>
    </html>
    """


@app.route("/import")
def import_data():
    """Import CSV data into the database"""
    from import_csv import import_grocery_data
    try:
        count = import_grocery_data()
        return f"<h1>Import Complete</h1><p>Imported {count} products successfully!</p><p><a href='/'>Back to Home</a></p>"
    except Exception as e:
        return f"<h1>Import Error</h1><p>Error: {str(e)}</p><p><a href='/'>Back to Home</a></p>"


def find_cheaper_alternatives(product, max_price, limit=5):
    """Find cheaper alternatives for a product"""
    alternatives = []
    
    # First, try same category with lower price
    same_category = Product.query.filter(
        Product.sub_category == product.sub_category,
        Product.price_numeric < max_price,
        Product.price_numeric.isnot(None),
        Product.id != product.id
    ).order_by(Product.price_numeric.asc()).limit(limit).all()
    
    alternatives.extend(same_category)
    
    # If not enough alternatives, search by keywords from title
    if len(alternatives) < limit:
        # Extract keywords from product title (remove common words)
        import re
        common_words = {'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'from', 'up', 'about', 'into', 'through', 'during', 'before', 'after', 'above', 'below', 'between', 'among', 'throughout', 'beside', 'underneath', 'within', 'without', 'toward', 'towards', 'until', 'upon', 'a', 'an', 'as', 'are', 'was', 'were', 'been', 'be', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should', 'may', 'might', 'must', 'can', 'oz', 'lb', 'lbs', 'pack', 'count', 'inch', 'pieces'}
        
        words = re.findall(r'\b[a-zA-Z]{3,}\b', product.title.lower())
        keywords = [word for word in words if word not in common_words][:3]  # Take first 3 meaningful words
        
        for keyword in keywords:
            keyword_matches = Product.query.filter(
                Product.title.ilike(f'%{keyword}%'),
                Product.price_numeric < max_price,
                Product.price_numeric.isnot(None),
                Product.id != product.id,
                ~Product.id.in_([alt.id for alt in alternatives])  # Exclude already found alternatives
            ).order_by(Product.price_numeric.asc()).limit(limit - len(alternatives)).all()
            
            alternatives.extend(keyword_matches)
            if len(alternatives) >= limit:
                break
    
    return alternatives[:limit]


@app.route("/budget_exceeded")
def budget_exceeded():
    """Show budget exceeded page with cheaper alternatives"""
    if 'session_id' not in session:
        return redirect(url_for('index'))
    
    session_id = session['session_id']
    product_id = int(request.args.get('product_id'))
    quantity = int(request.args.get('quantity', 1))
    overage = float(request.args.get('overage', 0))
    
    if not product_id:
        return redirect(url_for('index'))
    
    # Get the product that caused the overage
    product = Product.query.get(product_id)
    if not product:
        return redirect(url_for('index'))
    
    # Get user budget
    user_budget = UserBudget.query.filter_by(session_id=session_id).first()
    if not user_budget:
        return redirect(url_for('index'))
    
    # Find cheaper alternatives - calculate per-unit savings needed
    overage_per_unit = overage / quantity
    max_price = float(product.price_numeric or 0) - overage_per_unit - 0.01
    alternatives = find_cheaper_alternatives(product, max_price)
    
    # Get current cart info
    cart_items = ShoppingCart.query.filter_by(session_id=session_id).all()
    cart_total = sum(float(item.product.price_numeric or 0) * item.quantity for item in cart_items)
    
    return f"""
    <html>
    <head><title>Budget Exceeded - Alternatives Available</title></head>
    <body style="font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px;">
        <div style="background-color: #ffebee; border: 1px solid #f44336; padding: 15px; margin-bottom: 20px; border-radius: 5px;">
            <h2 style="color: #d32f2f; margin-top: 0;">🚫 Budget Exceeded!</h2>
            <p><strong>Your budget:</strong> ${user_budget.budget_amount}</p>
            <p><strong>Current cart total:</strong> ${cart_total:.2f}</p>
            <p><strong>Amount over budget:</strong> ${overage:.2f}</p>
        </div>
        
        <div style="background-color: #e8f5e8; padding: 15px; margin-bottom: 20px; border-radius: 5px;">
            <h3>💡 We found cheaper alternatives for: <em>{product.title}</em></h3>
            <p><strong>Original price:</strong> {product.price_text}</p>
        </div>
        
        {"".join([f'''
        <div style="border: 1px solid #4CAF50; margin: 10px 0; padding: 15px; border-radius: 5px; background-color: #f1f8e9;">
            <h4 style="margin-top: 0; color: #2e7d32;">{alt.title}</h4>
            <p><strong>Price:</strong> {alt.price_text} | <strong>Category:</strong> {alt.sub_category}</p>
            <p><strong>You save:</strong> ${float(product.price_numeric or 0) - float(alt.price_numeric or 0):.2f}</p>
            <div style="display: flex; gap: 10px;">
                <form action="/replace_item" method="post" style="display: inline;">
                    <input type="hidden" name="old_product_id" value="{product.id}">
                    <input type="hidden" name="new_product_id" value="{alt.id}">
                    <button type="submit" style="background-color: #4CAF50; color: white; padding: 8px 16px; border: none; border-radius: 4px; cursor: pointer;">
                        Replace with this item
                    </button>
                </form>
                <form action="/add_alternative" method="post" style="display: inline;">
                    <input type="hidden" name="product_id" value="{alt.id}">
                    <input type="number" name="quantity" value="1" min="1" max="10" style="width: 60px; padding: 4px;">
                    <button type="submit" style="background-color: #2196F3; color: white; padding: 8px 16px; border: none; border-radius: 4px; cursor: pointer;">
                        Add this too
                    </button>
                </form>
            </div>
        </div>
        ''' for alt in alternatives]) if alternatives else "<p>Sorry, no cheaper alternatives found. Consider removing some items from your cart.</p>"}
        
        <div style="margin-top: 30px; padding: 15px; background-color: #f5f5f5; border-radius: 5px;">
            <h3>What would you like to do?</h3>
            <p>
                <a href="/cart" style="background-color: #ff9800; color: white; padding: 10px 20px; text-decoration: none; border-radius: 4px; margin-right: 10px;">
                    📝 Edit Cart
                </a>
                <a href="/" style="background-color: #9e9e9e; color: white; padding: 10px 20px; text-decoration: none; border-radius: 4px; margin-right: 10px;">
                    🛒 Continue Shopping
                </a>
                <a href="/budget" style="background-color: #673ab7; color: white; padding: 10px 20px; text-decoration: none; border-radius: 4px;">
                    💰 Increase Budget
                </a>
            </p>
        </div>
    </body>
    </html>
    """


@app.route("/replace_item", methods=["POST"])
def replace_item():
    """Replace an item in cart with a cheaper alternative"""
    if 'session_id' not in session:
        return redirect(url_for('index'))
    
    session_id = session['session_id']
    old_product_id = request.form.get('old_product_id')
    new_product_id = request.form.get('new_product_id')
    
    # Remove old item
    old_item = ShoppingCart.query.filter_by(
        session_id=session_id, 
        product_id=old_product_id
    ).first()
    
    if old_item:
        quantity = old_item.quantity
        db.session.delete(old_item)
        
        # Add new item with same quantity
        new_item = ShoppingCart(
            session_id=session_id,
            product_id=new_product_id,
            quantity=quantity
        )
        db.session.add(new_item)
        db.session.commit()
    
    from flask import Response
    return Response(status=303, headers={'Location': url_for('view_cart')})


@app.route("/add_alternative", methods=["POST"])
def add_alternative():
    """Add an alternative item to cart"""
    if 'session_id' not in session:
        session['session_id'] = str(uuid.uuid4())
    
    session_id = session['session_id']
    product_id = request.form.get('product_id')
    quantity = int(request.form.get('quantity', 1))
    
    # Check if item already in cart
    existing_item = ShoppingCart.query.filter_by(
        session_id=session_id, 
        product_id=product_id
    ).first()
    
    if existing_item:
        existing_item.quantity += quantity
    else:
        cart_item = ShoppingCart(
            session_id=session_id,
            product_id=product_id,
            quantity=quantity
        )
        db.session.add(cart_item)
    
    db.session.commit()
    from flask import Response
    return Response(status=303, headers={'Location': url_for('view_cart')})


@app.route("/import_nutrition_data")
def import_nutrition_data():
    """Import the new nutrition dataset - temporary route"""
    import pandas as pd
    
    try:
        # Clear existing data
        Product.query.delete()
        db.session.commit()
        
        # Read CSV file
        df = pd.read_csv('attached_assets/GroceryDataset_with_Nutrition_1758836546999.csv')
        
        imported_count = 0
        
        for _, row in df.iterrows():
            # Parse price and rating - ensure they're strings first
            price_text = str(row.get('Price', '')) if pd.notna(row.get('Price')) else ''
            rating_text = str(row.get('Rating', '')) if pd.notna(row.get('Rating')) else ''
            
            price_numeric = Product.parse_price(price_text)
            rating_numeric, review_count = Product.parse_rating(rating_text)
            
            # Parse nutritional information
            def safe_int(value):
                if pd.isna(value) or value == '' or value is None:
                    return None
                try:
                    return int(float(value))
                except (ValueError, TypeError):
                    return None
            
            def safe_float(value):
                if pd.isna(value) or value == '' or value is None:
                    return None
                try:
                    return float(value)
                except (ValueError, TypeError):
                    return None
            
            # Create product instance - ensure all text fields are strings
            def safe_str(value):
                if pd.isna(value) or value is None:
                    return ''
                return str(value)
            
            product = Product(
                sub_category=safe_str(row.get('Sub Category')),
                price_text=price_text,
                price_numeric=price_numeric,
                discount=safe_str(row.get('Discount')),
                rating_text=rating_text,
                rating_numeric=rating_numeric,
                review_count=review_count,
                title=safe_str(row.get('Title')),
                currency=safe_str(row.get('Currency')),
                feature=safe_str(row.get('Feature')),
                description=safe_str(row.get('Product Description')),
                # Nutritional information
                calories=safe_int(row.get('Calories')),
                fat_g=safe_float(row.get('Fat_g')),
                carbs_g=safe_float(row.get('Carbs_g')),
                sugar_g=safe_float(row.get('Sugar_g')),
                protein_g=safe_float(row.get('Protein_g')),
                sodium_mg=safe_int(row.get('Sodium_mg'))
            )
            
            db.session.add(product)
            imported_count += 1
            
            # Commit in batches for better performance
            if imported_count % 100 == 0:
                db.session.commit()
        
        # Final commit
        db.session.commit()
        
        return f"Successfully imported {imported_count} products with nutrition data!"
    
    except Exception as e:
        return f"Error importing data: {str(e)}", 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)