"""
Create realistic demo scenarios that will generate actual recommendations.
Based on the successful screenshot: expensive items with cheaper alternatives.
"""

import json
from main import app, db, Product
from sqlalchemy import text

def find_expensive_items_with_alternatives():
    """Find expensive items that have many cheaper alternatives in same category."""
    with app.app_context():
        # Find categories with expensive items and many cheaper options
        query = text("""
            WITH category_stats AS (
                SELECT 
                    sub_category,
                    COUNT(*) as item_count,
                    MAX(price_numeric) as max_price,
                    MIN(price_numeric) as min_price,
                    AVG(price_numeric) as avg_price
                FROM products
                WHERE price_numeric IS NOT NULL AND price_numeric > 0
                GROUP BY sub_category
                HAVING COUNT(*) >= 10 AND MAX(price_numeric) > 50
            )
            SELECT 
                p.id,
                p.title,
                p.sub_category,
                p.price_numeric,
                cs.item_count,
                cs.avg_price
            FROM products p
            JOIN category_stats cs ON p.sub_category = cs.sub_category
            WHERE p.price_numeric > cs.avg_price * 2
            ORDER BY p.price_numeric DESC, cs.item_count DESC
            LIMIT 20
        """)
        
        results = db.session.execute(query).fetchall()
        
        expensive_items = []
        for row in results:
            expensive_items.append({
                'product_id': int(row[0]),
                'title': row[1],
                'subcategory': row[2],
                'price': float(row[3]),
                'category_size': int(row[4]),
                'category_avg_price': float(row[5])
            })
        
        return expensive_items

def create_demo_scenarios():
    """Create 3 realistic demo scenarios that will generate suggestions."""
    
    expensive_items = find_expensive_items_with_alternatives()
    
    if not expensive_items:
        print("ERROR: No expensive items found")
        return []
    
    print(f"\n✓ Found {len(expensive_items)} expensive items with alternatives")
    for item in expensive_items[:10]:
        print(f"  - {item['title'][:50]}: ${item['price']:.2f} ({item['category_size']} items in category)")
    
    # Scenario 1: Budget-Conscious Shopper
    # Pick 2-3 expensive items, set budget to 70% of total
    scenario1_items = expensive_items[:2]
    cart1 = []
    total1 = 0
    for item in scenario1_items:
        cart1.append({
            'id': str(item['product_id']),
            'title': item['title'],
            'subcat': item['subcategory'],
            'price': item['price'],
            'qty': 1
        })
        total1 += item['price']
    
    budget1 = round(total1 * 0.65, 2)
    
    # Scenario 2: Single Expensive Item
    # One very expensive item, tight budget
    scenario2_items = [expensive_items[0]]
    cart2 = [{
        'id': str(scenario2_items[0]['product_id']),
        'title': scenario2_items[0]['title'],
        'subcat': scenario2_items[0]['subcategory'],
        'price': scenario2_items[0]['price'],
        'qty': 1
    }]
    budget2 = round(scenario2_items[0]['price'] * 0.5, 2)
    
    # Scenario 3: Multiple Categories
    # 3 items from different categories
    scenario3_items = []
    seen_categories = set()
    for item in expensive_items:
        if item['subcategory'] not in seen_categories:
            scenario3_items.append(item)
            seen_categories.add(item['subcategory'])
        if len(scenario3_items) >= 3:
            break
    
    cart3 = []
    total3 = 0
    for item in scenario3_items:
        cart3.append({
            'id': str(item['product_id']),
            'title': item['title'],
            'subcat': item['subcategory'],
            'price': item['price'],
            'qty': 1
        })
        total3 += item['price']
    
    budget3 = round(total3 * 0.70, 2)
    
    scenarios = [
        {
            'name': 'budget_conscious_demo',
            'user_type': 'Budget-conscious shopper with expensive items',
            'session_id': 'demo_user_001',  # User with 8 orders
            'budget': budget1,
            'cart': cart1,
            'cart_total': total1,
            'over_budget': total1 - budget1
        },
        {
            'name': 'single_expensive_item',
            'user_type': 'Shopper with one expensive item',
            'session_id': 'demo_user_003',  # User with 8 orders
            'budget': budget2,
            'cart': cart2,
            'cart_total': cart2[0]['price'],
            'over_budget': cart2[0]['price'] - budget2
        },
        {
            'name': 'multi_category_shopper',
            'user_type': 'Shopper with items from multiple categories',
            'session_id': 'demo_user_009',  # User with 7 orders
            'budget': budget3,
            'cart': cart3,
            'cart_total': total3,
            'over_budget': total3 - budget3
        }
    ]
    
    return scenarios

if __name__ == '__main__':
    with app.app_context():
        print("🎯 Creating Demo Scenarios for LLM Evaluation")
        print("Based on: Expensive items with cheaper alternatives\n")
        
        scenarios = create_demo_scenarios()
        
        if scenarios:
            # Save scenarios
            with open('demo_evaluation_scenarios.json', 'w') as f:
                json.dump({'scenarios': scenarios}, f, indent=2)
            
            print(f"\n✅ Created {len(scenarios)} demo scenarios\n")
            
            for i, scenario in enumerate(scenarios, 1):
                print(f"Scenario {i}: {scenario['name']}")
                print(f"  User: {scenario['session_id']}")
                print(f"  Budget: ${scenario['budget']:.2f}")
                print(f"  Cart Total: ${scenario['cart_total']:.2f}")
                print(f"  Over Budget: ${scenario['over_budget']:.2f}")
                print(f"  Items: {len(scenario['cart'])}")
                for item in scenario['cart']:
                    print(f"    - {item['title'][:60]} (${item['price']:.2f})")
                print()
            
            print("✅ Saved to: demo_evaluation_scenarios.json")
        else:
            print("\n❌ Failed to create scenarios")
