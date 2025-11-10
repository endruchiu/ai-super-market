import os
import sys
from datetime import datetime, timedelta
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
import pandas as pd

DATABASE_URL = os.environ.get('DATABASE_URL')
if not DATABASE_URL:
    print("ERROR: DATABASE_URL not found")
    sys.exit(1)

engine = create_engine(DATABASE_URL)

PRODUCTS_CSV = 'attached_assets/GroceryDataset_with_Nutrition_1758836546999.csv'
df = pd.read_csv(PRODUCTS_CSV)

def get_product_hash(title):
    from hashlib import blake2b
    return int.from_bytes(blake2b(title.encode('utf-8'), digest_size=8).digest(), 'big', signed=True)

consumable_items = [
    ('Milk', 7, 3.99),
    ('Coffee', 14, 12.99),
    ('Bread', 5, 2.49),
    ('Eggs', 10, 4.99),
]

print("🔍 Finding consumable products...")
demo_products = []
for keyword, interval, target_price in consumable_items:
    matches = df[df['Title'].str.contains(keyword, case=False, na=False)]
    if len(matches) > 0:
        product = matches.iloc[0]
        product_id = get_product_hash(product['Title'])
        demo_products.append({
            'keyword': keyword,
            'product_id': product_id,
            'title': product['Title'],
            'price': float(product['Price'].replace('$', '')) if isinstance(product['Price'], str) else float(product['Price']),
            'subcat': product.get('Sub Category', 'Grocery'),
            'interval_days': interval,
        })
        print(f"  ✓ Found: {product['Title'][:50]} (${demo_products[-1]['price']:.2f})")

print(f"\n📦 Creating demo purchase history for {len(demo_products)} products...")

with Session(engine) as session:
    user_result = session.execute(text("SELECT id FROM users LIMIT 1")).fetchone()
    
    if user_result:
        user_id = user_result[0]
        print(f"✓ Using existing user: {user_id}")
    else:
        import uuid
        user_id = str(uuid.uuid4())
        session.execute(text(
            "INSERT INTO users (id, created_at) VALUES (:id, :created_at)"
        ), {"id": user_id, "created_at": datetime.utcnow()})
        session.commit()
        print(f"✓ Created new user: {user_id}")
    
    order_count = 0
    for product in demo_products:
        interval = product['interval_days']
        
        purchase_dates = [
            datetime.utcnow() - timedelta(days=interval * 3),
            datetime.utcnow() - timedelta(days=interval * 2),
            datetime.utcnow() - timedelta(days=interval * 1 + 2),
        ]
        
        for purchase_date in purchase_dates:
            order_id_result = session.execute(text(
                """INSERT INTO orders (user_id, total_amount, item_count, created_at) 
                   VALUES (:user_id, :total_amount, :item_count, :created_at) 
                   RETURNING id"""
            ), {
                "user_id": user_id,
                "total_amount": product['price'],
                "item_count": 1,
                "created_at": purchase_date
            }).fetchone()
            
            order_id = order_id_result[0]
            
            session.execute(text(
                """INSERT INTO order_items 
                   (order_id, product_id, unit_price, line_total, quantity, product_title, product_subcat)
                   VALUES (:order_id, :product_id, :unit_price, :line_total, :quantity, :product_title, :product_subcat)"""
            ), {
                "order_id": order_id,
                "product_id": product['product_id'],
                "unit_price": product['price'],
                "line_total": product['price'],
                "quantity": 1,
                "product_title": product['title'],
                "product_subcat": product['subcat']
            })
            
            session.execute(text(
                """INSERT INTO user_events 
                   (user_id, event_type, product_id, product_title, product_subcat, created_at)
                   VALUES (:user_id, 'purchase', :product_id, :product_title, :product_subcat, :created_at)"""
            ), {
                "user_id": user_id,
                "event_type": "purchase",
                "product_id": product['product_id'],
                "product_title": product['title'],
                "product_subcat": product['subcat'],
                "created_at": purchase_date
            })
            
            order_count += 1
    
    session.commit()
    print(f"✓ Created {order_count} orders across {len(demo_products)} products")

print("\n🔄 Triggering replenishment cycle calculation...")
import requests
try:
    response = requests.post('http://127.0.0.1:5000/api/replenishment/refresh-cycles')
    if response.status_code == 200:
        result = response.json()
        print(f"✓ Calculated {result.get('cycles_updated', 0)} replenishment cycles")
        print(f"✓ Identified {result.get('replenishable_count', 0)} replenishable products")
    else:
        print(f"⚠ Warning: Refresh returned {response.status_code}")
except Exception as e:
    print(f"⚠ Could not trigger refresh: {e}")

print("\n✅ Demo data seeded successfully!")
print("💡 Refresh your browser to see the Restock Reminders panel populate!")
