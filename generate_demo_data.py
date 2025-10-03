import os
import random
from datetime import datetime, timedelta
import pandas as pd

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from models import init_models

DATABASE_URL = os.getenv('DATABASE_URL')
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL environment variable is required")

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

with app.app_context():
    Product, ShoppingCart, UserBudget, User, Order, OrderItem, UserEvent = init_models(db)
    db.create_all()

    df = pd.read_csv('attached_assets/GroceryDataset_with_Nutrition_1758836546999.csv')
    
    print(f"Loaded {len(df)} products from CSV")

    demo_users = [
    {'session_id': f'demo_user_{i:03d}', 'preferences': prefs}
    for i, prefs in enumerate([
        {'categories': ['Bakery & Desserts', 'Snacks'], 'budget': 'high'},
        {'categories': ['Fruits & Vegetables'], 'budget': 'medium'},
        {'categories': ['Meat & Seafood', 'Dairy & Eggs'], 'budget': 'high'},
        {'categories': ['Beverages'], 'budget': 'low'},
        {'categories': ['Bakery & Desserts', 'Beverages'], 'budget': 'medium'},
        {'categories': ['Snacks', 'Candy & Chocolate'], 'budget': 'medium'},
        {'categories': ['Fruits & Vegetables', 'Grains & Pasta'], 'budget': 'low'},
        {'categories': ['Meat & Seafood'], 'budget': 'high'},
        {'categories': ['Dairy & Eggs', 'Bakery & Desserts'], 'budget': 'medium'},
        {'categories': ['Beverages', 'Snacks'], 'budget': 'medium'},
        {'categories': ['Candy & Chocolate'], 'budget': 'low'},
        {'categories': ['Fruits & Vegetables', 'Meat & Seafood'], 'budget': 'high'},
        {'categories': ['Grains & Pasta', 'Canned Goods'], 'budget': 'low'},
        {'categories': ['Bakery & Desserts'], 'budget': 'high'},
        {'categories': ['Snacks', 'Beverages', 'Candy & Chocolate'], 'budget': 'medium'},
    ])
    ]
    
    def get_product_id(row):
        import hashlib
        key = f"{row['Title']}|{row['Sub Category']}"
        hash_obj = hashlib.blake2b(key.encode('utf-8'), digest_size=8)
        return int.from_bytes(hash_obj.digest(), byteorder='big', signed=True)
    
    def parse_price(price_str):
        if pd.isna(price_str):
            return 0.0
        import re
        match = re.search(r'\d+\.?\d*', str(price_str))
        if match:
            return float(match.group())
        return 0.0
    
    print("Creating demo users and orders...")
    
    orders_created = 0
    start_date = datetime.now() - timedelta(days=90)
    
    for user_info in demo_users:
        user = User.query.filter_by(session_id=user_info['session_id']).first()
        if not user:
            user = User(session_id=user_info['session_id'])
            db.session.add(user)
            db.session.flush()
        
        num_orders = random.randint(3, 8)
        
        for order_num in range(num_orders):
            order_date = start_date + timedelta(days=random.randint(0, 90))
            
            preferred_cats = user_info['preferences']['categories']
            budget_level = user_info['preferences']['budget']
            
            available_products = df[df['Sub Category'].isin(preferred_cats)]
            
            if budget_level == 'low':
                available_products = available_products[
                    available_products['Price'].apply(parse_price) < 30
                ]
            elif budget_level == 'high':
                popular_expensive = available_products[
                    available_products['Price'].apply(parse_price) > 20
                ]
                if len(popular_expensive) > 0:
                    available_products = popular_expensive
            
            if len(available_products) == 0:
                available_products = df.sample(n=min(20, len(df)))
            
            num_items = random.randint(2, 6)
            selected_products = available_products.sample(n=min(num_items, len(available_products)))
            
            order_items = []
            total_amount = 0.0
            
            for _, prod in selected_products.iterrows():
                product_id = get_product_id(prod)
                price = parse_price(prod['Price'])
                quantity = random.randint(1, 3)
                
                order_items.append({
                    'product_id': product_id,
                    'title': prod['Title'],
                    'subcategory': prod['Sub Category'],
                    'price': price,
                    'quantity': quantity
                })
                total_amount += price * quantity
            
            order = Order(
                user_id=user.id,
                total_amount=total_amount,
                item_count=len(order_items),
                created_at=order_date
            )
            db.session.add(order)
            db.session.flush()
            
            for item_data in order_items:
                order_item = OrderItem(
                    order_id=order.id,
                    product_id=item_data['product_id'],
                    product_title=item_data['title'],
                    product_subcat=item_data['subcategory'],
                    unit_price=item_data['price'],
                    quantity=item_data['quantity']
                )
                db.session.add(order_item)
                
                user_event = UserEvent(
                    user_id=user.id,
                    event_type='purchase',
                    product_id=item_data['product_id'],
                    created_at=order_date
                )
                db.session.add(user_event)
            
            orders_created += 1
    
    db.session.commit()
    print(f"✓ Created {orders_created} demo orders for {len(demo_users)} users")
    
    total_orders = Order.query.count()
    total_items = OrderItem.query.count()
    total_events = UserEvent.query.count()
    
    print(f"\nDatabase Summary:")
    print(f"  Users: {len(demo_users)}")
    print(f"  Orders: {total_orders}")
    print(f"  Order Items: {total_items}")
    print(f"  User Events: {total_events}")
    
    print("\n✓ Demo purchase history generated successfully!")
