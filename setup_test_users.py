"""
Create test users with realistic purchase histories for LLM evaluation
This will enable the Personalized CF and Hybrid AI systems to work properly
"""

from main import app, db, PRODUCTS_DF
from models import init_models
import random

# Initialize models
Product, ShoppingCart, UserBudget, User, Order, OrderItem, UserEvent = init_models(db)

def create_test_user_with_history(session_id, shopping_pattern, num_purchases=12):
    """Create a test user with purchase history matching a shopping pattern."""
    
    with app.app_context():
        # Check if user exists
        user = User.query.filter_by(session_id=session_id).first()
        if user:
            print(f"User {session_id} already exists, clearing old data...")
            # Clear old purchases
            for order in user.orders:
                OrderItem.query.filter_by(order_id=order.id).delete()
                db.session.delete(order)
            UserEvent.query.filter_by(user_id=user.id).delete()
            db.session.commit()
        else:
            user = User(session_id=session_id)
            db.session.add(user)
            db.session.flush()
        
        print(f"\n{'='*60}")
        print(f"Creating purchase history for: {session_id}")
        print(f"Pattern: {shopping_pattern}")
        print(f"{'='*60}")
        
        purchases = []
        
        if shopping_pattern == "budget_conscious":
            # Prefer cheaper items, store brands, value packs
            products = PRODUCTS_DF.nsmallest(50, 'price')
            # Add some Kirkland Signature items
            kirkland = PRODUCTS_DF[PRODUCTS_DF['title'].str.contains('Kirkland', case=False, na=False)]
            products = products._append(kirkland.sample(min(20, len(kirkland))))
            
        elif shopping_pattern == "health_focused":
            # Prefer organic, healthy, low-sugar items
            organic = PRODUCTS_DF[PRODUCTS_DF['subcat'].str.contains('Organic', case=False, na=False)]
            healthy_keywords = ['organic', 'natural', 'sugar free', 'low fat', 'healthy', 'whole grain']
            healthy = PRODUCTS_DF[PRODUCTS_DF['title'].str.lower().str.contains('|'.join(healthy_keywords), na=False)]
            products = organic._append(healthy).drop_duplicates()
            
        elif shopping_pattern == "dessert_lover":
            # Prefer bakery, desserts, sweets
            dessert_cats = ['Bakery & Desserts', 'Candy']
            products = PRODUCTS_DF[PRODUCTS_DF['subcat'].isin(dessert_cats)]
            
        else:
            # Mixed shopping
            products = PRODUCTS_DF.sample(100)
        
        # Select products for purchase history
        selected_products = products.sample(min(num_purchases, len(products)))
        
        for idx, (_, product) in enumerate(selected_products.iterrows(), 1):
            # Create order
            order = Order(
                user_id=user.id,
                total_amount=float(product['price']),
                item_count=1
            )
            db.session.add(order)
            db.session.flush()
            
            # Create order item
            order_item = OrderItem(
                order_id=order.id,
                product_id=int(product['product_id']),
                product_title=product['title'],
                quantity=1,
                price=float(product['price'])
            )
            db.session.add(order_item)
            
            # Create purchase event
            event = UserEvent(
                user_id=user.id,
                product_id=int(product['product_id']),
                event_type='purchase',
                event_value=1.0
            )
            db.session.add(event)
            
            purchases.append({
                'title': product['title'][:60],
                'price': float(product['price']),
                'category': product['subcat']
            })
            
            print(f"  {idx}. {product['title'][:50]}... - ${product['price']:.2f} ({product['subcat']})")
        
        db.session.commit()
        
        print(f"\n✓ Created {len(purchases)} purchases for user {session_id}")
        print(f"  Total spent: ${sum(p['price'] for p in purchases):.2f}")
        print(f"  User ID: {user.id}")
        
        return user, purchases


if __name__ == "__main__":
    print("\n🎯 Setting up test users with purchase histories")
    print("This will enable proper evaluation of all three recommendation systems\n")
    
    # Create three test users with different shopping patterns
    users_created = []
    
    # User 1: Budget-conscious shopper
    user1, purchases1 = create_test_user_with_history(
        session_id="eval_test_budget_user",
        shopping_pattern="budget_conscious",
        num_purchases=15
    )
    users_created.append(("Budget-Conscious", user1, len(purchases1)))
    
    # User 2: Health-focused shopper
    user2, purchases2 = create_test_user_with_history(
        session_id="eval_test_health_user",
        shopping_pattern="health_focused",
        num_purchases=12
    )
    users_created.append(("Health-Focused", user2, len(purchases2)))
    
    # User 3: Dessert lover
    user3, purchases3 = create_test_user_with_history(
        session_id="eval_test_dessert_user",
        shopping_pattern="dessert_lover",
        num_purchases=10
    )
    users_created.append(("Dessert Lover", user3, len(purchases3)))
    
    print("\n" + "="*60)
    print("✅ TEST USERS CREATED SUCCESSFULLY")
    print("="*60)
    
    for pattern, user, count in users_created:
        print(f"\n  {pattern}:")
        print(f"    Session ID: {user.session_id}")
        print(f"    User ID: {user.id}")
        print(f"    Purchases: {count}")
    
    print("\n🚀 Now the Personalized CF and Hybrid AI systems will work properly!")
    print("   Run: python test_llm_evaluation.py")
    print("="*60 + "\n")
