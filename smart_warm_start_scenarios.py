"""
Smart Warm-Start Scenario Generator
Uses user_product_behavior.csv to create realistic test scenarios
that showcase CF recommendations at their best.
"""

import json
import pandas as pd
from typing import List, Dict, Any
from datetime import datetime
from main import app, db, User, Product
from sqlalchemy import text

def load_user_behavior() -> pd.DataFrame:
    """Load user behavior data from CSV."""
    try:
        df = pd.read_csv('ml_data/user_product_behavior.csv')
        print(f"✓ Loaded {len(df)} user-product interactions")
        return df
    except FileNotFoundError:
        print("ERROR: ml_data/user_product_behavior.csv not found")
        return pd.DataFrame()

def find_users_with_expensive_purchases(behavior_df: pd.DataFrame, min_purchases: int = 3) -> List[Dict[str, Any]]:
    """
    Find users who purchased expensive items (good for testing cheaper alternatives).
    
    Args:
        behavior_df: User behavior dataframe
        min_purchases: Minimum number of distinct products purchased
        
    Returns:
        List of users with their expensive purchase info
    """
    with app.app_context():
        # Get users with sufficient purchase history
        users_with_purchases = behavior_df[behavior_df['purchase_count'] > 0].groupby('user_id').agg({
            'product_id': 'count',
            'purchase_count': 'sum'
        }).reset_index()
        
        users_with_purchases.columns = ['user_id', 'distinct_products', 'total_purchases']
        qualified_users = users_with_purchases[users_with_purchases['distinct_products'] >= min_purchases]
        
        print(f"\n✓ Found {len(qualified_users)} users with {min_purchases}+ distinct purchases")
        
        # For each qualified user, find their expensive purchases
        results = []
        for _, row in qualified_users.iterrows():
            user_db_id = int(row['user_id'])
            
            # Get session_id from database (SQLAlchemy 2.0 syntax)
            user = db.session.get(User, user_db_id)
            if not user:
                print(f"  ⚠️  User {user_db_id} not found in database")
                continue
            
            # Get user's purchased products
            user_products = behavior_df[
                (behavior_df['user_id'] == user_db_id) & 
                (behavior_df['purchase_count'] > 0)
            ]['product_id'].tolist()
            
            if not user_products:
                print(f"  ⚠️  User {user_db_id} ({user.session_id}) has no purchases in behavior CSV")
                continue
            
            print(f"  → User {user.session_id}: {len(user_products)} purchased products")
            
            # Get product details from database
            product_ids_str = ','.join(str(int(pid)) for pid in user_products)
            query = text(f"""
                SELECT id, title, sub_category, price_numeric
                FROM products
                WHERE id IN ({product_ids_str}) AND price_numeric IS NOT NULL
                ORDER BY price_numeric DESC
                LIMIT 5
            """)
            
            expensive_products = db.session.execute(query).fetchall()
            
            print(f"     Found {len(expensive_products)} products with prices")
            
            if expensive_products:
                results.append({
                    'user_db_id': user_db_id,
                    'session_id': user.session_id,
                    'distinct_products': int(row['distinct_products']),
                    'total_purchases': int(row['total_purchases']),
                    'expensive_products': [
                        {
                            'product_id': int(p[0]),
                            'title': p[1],
                            'subcategory': p[2],
                            'price': float(p[3])
                        }
                        for p in expensive_products
                    ]
                })
        
        return results

def create_realistic_scenario(user_info: Dict[str, Any], budget_factor: float = 0.7) -> Dict[str, Any]:
    """
    Create a realistic over-budget scenario using user's actual expensive purchases.
    
    Args:
        user_info: User info with expensive products
        budget_factor: Budget as fraction of cart total (0.7 = 70%)
        
    Returns:
        Scenario dict ready for LLM evaluation
    """
    # Pick 2-3 expensive items from user's history
    expensive_items = user_info['expensive_products'][:3]
    
    cart = []
    cart_total = 0.0
    
    for item in expensive_items:
        cart.append({
            'product_id': item['product_id'],
            'title': item['title'],
            'subcategory': item['subcategory'],
            'price': item['price'],
            'quantity': 1
        })
        cart_total += item['price']
    
    # Set budget to create pressure (e.g., 70% of cart total)
    budget = round(cart_total * budget_factor, 2)
    over_budget = cart_total - budget
    
    scenario = {
        'type': 'warm_start_realistic',
        'strategy': 'expensive_purchases',
        'session_id': user_info['session_id'],
        'cart': cart,
        'budget': budget,
        'cart_total': cart_total,
        'over_budget': over_budget,
        'context': {
            'user_stats': {
                'user_db_id': user_info['user_db_id'],
                'distinct_products': user_info['distinct_products'],
                'total_purchases': user_info['total_purchases']
            },
            'test_purpose': 'Showcase CF with expensive items that have cheaper alternatives'
        }
    }
    
    return scenario

def generate_smart_scenarios(count: int = 5) -> List[Dict[str, Any]]:
    """
    Generate smart warm-start scenarios using actual user behavior data.
    
    Args:
        count: Number of scenarios to generate
        
    Returns:
        List of scenario dicts
    """
    behavior_df = load_user_behavior()
    
    if behavior_df.empty:
        print("ERROR: No behavior data available")
        return []
    
    print("\n🔍 Finding users with expensive purchases...")
    users = find_users_with_expensive_purchases(behavior_df, min_purchases=3)
    
    if not users:
        print("ERROR: No qualified users found")
        return []
    
    print(f"✓ Found {len(users)} users with expensive purchase history")
    
    scenarios = []
    for i, user_info in enumerate(users[:count]):
        scenario = create_realistic_scenario(user_info, budget_factor=0.75)
        scenarios.append(scenario)
        
        print(f"\n  Scenario {i+1}:")
        print(f"    User: {scenario['session_id']}")
        print(f"    Cart: {len(scenario['cart'])} items, ${scenario['cart_total']:.2f}")
        print(f"    Budget: ${scenario['budget']:.2f} (over by ${scenario['over_budget']:.2f})")
        print(f"    Items: {', '.join([item['title'][:40] + '...' for item in scenario['cart']])}")
    
    return scenarios

def save_smart_scenarios(scenarios: List[Dict[str, Any]], filename: str = 'smart_warm_start_scenarios.json'):
    """Save scenarios to JSON file."""
    with open(filename, 'w') as f:
        json.dump({
            'generated_at': datetime.now().isoformat(),
            'scenario_count': len(scenarios),
            'data_source': 'ml_data/user_product_behavior.csv',
            'scenarios': scenarios
        }, f, indent=2)
    
    print(f"\n✅ Saved {len(scenarios)} smart scenarios to {filename}")

if __name__ == '__main__':
    with app.app_context():
        print("🎯 Smart Warm-Start Scenario Generator")
        print("Using actual user behavior data from user_product_behavior.csv\n")
        
        scenarios = generate_smart_scenarios(count=5)
        
        if scenarios:
            save_smart_scenarios(scenarios)
            print("\n✅ Done! These scenarios use expensive items users actually bought")
            print("   → CF should find cheaper alternatives in the same categories")
        else:
            print("\n❌ Failed to generate scenarios")
