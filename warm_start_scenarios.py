"""
Warm-Start Scenario Generator
Generates realistic test scenarios from actual user purchase history
for fair evaluation of CF-based recommendation systems.
"""

import json
from typing import List, Dict, Any
from datetime import datetime
from main import app, db, User, Order, OrderItem, Product

def get_warm_start_candidates(min_orders: int = 3, min_products: int = 5) -> List[Dict[str, Any]]:
    """
    Query database to find users with sufficient purchase history.
    
    Args:
        min_orders: Minimum number of distinct orders
        min_products: Minimum number of unique products purchased
        
    Returns:
        List of candidate users with their stats
    """
    from sqlalchemy import func
    
    query = db.session.query(
        User.session_id,
        User.id.label('user_db_id'),
        func.count(func.distinct(Order.id)).label('order_count'),
        func.count(func.distinct(OrderItem.product_id)).label('unique_products'),
        func.sum(OrderItem.line_total).label('total_spent')
    ).join(
        Order, User.id == Order.user_id
    ).join(
        OrderItem, Order.id == OrderItem.order_id
    ).group_by(
        User.session_id, User.id
    ).having(
        func.count(func.distinct(Order.id)) >= min_orders,
        func.count(func.distinct(OrderItem.product_id)) >= min_products
    ).order_by(
        func.count(func.distinct(Order.id)).desc(),
        func.count(func.distinct(OrderItem.product_id)).desc()
    ).limit(15)
    
    results = query.all()
    
    candidates = []
    for row in results:
        candidates.append({
            'session_id': row.session_id,
            'user_db_id': row.user_db_id,
            'order_count': row.order_count,
            'unique_products': row.unique_products,
            'total_spent': float(row.total_spent) if row.total_spent else 0.0
        })
    
    return candidates


def get_user_recent_purchases(session_id: str, limit: int = 20) -> List[Dict[str, Any]]:
    """
    Get a user's recent purchases to build realistic cart scenarios.
    
    Args:
        session_id: User's session identifier
        limit: Maximum number of items to retrieve
        
    Returns:
        List of purchased items with details
    """
    user = User.query.filter_by(session_id=session_id).first()
    if not user:
        return []
    
    items = db.session.query(
        OrderItem.product_id,
        OrderItem.product_title,
        OrderItem.product_subcat,
        OrderItem.unit_price,
        OrderItem.quantity,
        Order.created_at
    ).join(
        Order, OrderItem.order_id == Order.id
    ).filter(
        Order.user_id == user.id
    ).order_by(
        Order.created_at.desc()
    ).limit(limit).all()
    
    purchases = []
    for item in items:
        purchases.append({
            'product_id': item.product_id,
            'title': item.product_title,
            'subcategory': item.product_subcat,
            'price': float(item.unit_price),
            'quantity': item.quantity,
            'purchased_at': item.created_at.isoformat() if item.created_at else None
        })
    
    return purchases


def create_budget_squeeze_scenario(session_id: str, squeeze_factor: float = 0.85) -> Dict[str, Any]:
    """
    Create a scenario where user's typical cart exceeds a squeezed budget.
    This triggers recommendations to stay within budget.
    
    Args:
        session_id: User's session identifier
        squeeze_factor: Budget as fraction of cart total (0.85 = 85% of cart value)
        
    Returns:
        Scenario dict with session_id, cart, budget, and context
    """
    purchases = get_user_recent_purchases(session_id, limit=10)
    
    if not purchases:
        return None
    
    # Build cart from 3-5 recent items (create realistic over-budget situation)
    cart_size = min(5, max(3, len(purchases)))
    cart_items = []
    cart_total = 0.0
    
    seen_products = set()
    for purchase in purchases:
        if purchase['product_id'] in seen_products:
            continue
        if len(cart_items) >= cart_size:
            break
            
        cart_items.append({
            'product_id': purchase['product_id'],
            'title': purchase['title'],
            'subcategory': purchase['subcategory'],
            'price': purchase['price'],
            'quantity': 1  # Simplify to 1 for testing
        })
        cart_total += purchase['price']
        seen_products.add(purchase['product_id'])
    
    # Set budget to squeeze_factor of cart total (creates budget pressure)
    budget = round(cart_total * squeeze_factor, 2)
    
    # Get user's favorite categories
    subcats = [p['subcategory'] for p in purchases if p['subcategory']]
    favorite_categories = list(set(subcats))[:3]
    
    scenario = {
        'type': 'warm_start',
        'strategy': 'budget_squeeze',
        'session_id': session_id,
        'cart': cart_items,
        'budget': budget,
        'cart_total': cart_total,
        'over_budget': cart_total - budget,
        'context': {
            'favorite_categories': favorite_categories,
            'purchase_history_count': len(purchases),
            'squeeze_factor': squeeze_factor
        }
    }
    
    return scenario


def create_repeat_purchase_scenario(session_id: str) -> Dict[str, Any]:
    """
    Create a scenario where user is repeating a previous purchase but needs cheaper alternatives.
    
    Args:
        session_id: User's session identifier
        
    Returns:
        Scenario dict with session_id, cart, budget, and context
    """
    purchases = get_user_recent_purchases(session_id, limit=15)
    
    if len(purchases) < 5:
        return None
    
    # Find user's most purchased subcategory
    subcat_counts = {}
    for p in purchases:
        sc = p['subcategory']
        if sc:
            subcat_counts[sc] = subcat_counts.get(sc, 0) + 1
    
    if not subcat_counts:
        return None
        
    favorite_subcat = max(subcat_counts.items(), key=lambda x: x[1])[0]
    
    # Build cart from favorite category
    cart_items = []
    cart_total = 0.0
    
    seen_products = set()
    for purchase in purchases:
        if purchase['subcategory'] == favorite_subcat and purchase['product_id'] not in seen_products:
            cart_items.append({
                'product_id': purchase['product_id'],
                'title': purchase['title'],
                'subcategory': purchase['subcategory'],
                'price': purchase['price'],
                'quantity': 1
            })
            cart_total += purchase['price']
            seen_products.add(purchase['product_id'])
            
            if len(cart_items) >= 3:
                break
    
    if not cart_items:
        return None
    
    # Set budget lower than current cart (e.g., 70% to force cheaper alternatives)
    budget = round(cart_total * 0.70, 2)
    
    scenario = {
        'type': 'warm_start',
        'strategy': 'repeat_purchase',
        'session_id': session_id,
        'cart': cart_items,
        'budget': budget,
        'cart_total': cart_total,
        'over_budget': cart_total - budget,
        'context': {
            'favorite_category': favorite_subcat,
            'purchase_history_count': len(purchases),
            'scenario_type': 'repeat_buyer_needs_savings'
        }
    }
    
    return scenario


def generate_warm_start_scenarios(count: int = 10) -> List[Dict[str, Any]]:
    """
    Generate multiple warm-start test scenarios from real purchase data.
    
    Args:
        count: Number of scenarios to generate
        
    Returns:
        List of warm-start scenario dicts
    """
    candidates = get_warm_start_candidates()
    
    scenarios = []
    strategies = ['budget_squeeze', 'repeat_purchase']
    
    for i, candidate in enumerate(candidates[:count]):
        session_id = candidate['session_id']
        
        # Alternate between strategies
        strategy = strategies[i % len(strategies)]
        
        if strategy == 'budget_squeeze':
            scenario = create_budget_squeeze_scenario(session_id, squeeze_factor=0.85)
        else:
            scenario = create_repeat_purchase_scenario(session_id)
        
        if scenario:
            # Add candidate stats to context
            scenario['context']['user_stats'] = {
                'total_orders': candidate['order_count'],
                'unique_products': candidate['unique_products'],
                'lifetime_spent': candidate['total_spent']
            }
            scenarios.append(scenario)
    
    return scenarios


def save_scenarios_to_file(scenarios: List[Dict[str, Any]], filename: str = 'warm_start_test_scenarios.json'):
    """
    Save generated scenarios to JSON file for reproducible testing.
    
    Args:
        scenarios: List of scenario dicts
        filename: Output filename
    """
    with open(filename, 'w') as f:
        json.dump({
            'generated_at': datetime.now().isoformat(),
            'scenario_count': len(scenarios),
            'scenarios': scenarios
        }, f, indent=2)
    
    print(f"✅ Saved {len(scenarios)} warm-start scenarios to {filename}")


def load_scenarios_from_file(filename: str = 'warm_start_test_scenarios.json') -> List[Dict[str, Any]]:
    """
    Load scenarios from JSON file.
    
    Args:
        filename: Input filename
        
    Returns:
        List of scenario dicts
    """
    with open(filename, 'r') as f:
        data = json.load(f)
    
    return data.get('scenarios', [])


if __name__ == '__main__':
    # Test scenario generation
    with app.app_context():
        print("🔍 Finding users with purchase history...")
        candidates = get_warm_start_candidates()
        print(f"✅ Found {len(candidates)} candidates")
        
        for c in candidates[:5]:
            print(f"  - {c['session_id']}: {c['order_count']} orders, {c['unique_products']} products, ${c['total_spent']:.2f} spent")
        
        print("\n📦 Generating warm-start scenarios...")
        scenarios = generate_warm_start_scenarios(count=10)
        print(f"✅ Generated {len(scenarios)} scenarios")
        
        for i, s in enumerate(scenarios, 1):
            print(f"\n  Scenario {i}: {s['strategy']}")
            print(f"    User: {s['session_id']}")
            print(f"    Cart: {len(s['cart'])} items, ${s['cart_total']:.2f}")
            print(f"    Budget: ${s['budget']:.2f} (over by ${s['over_budget']:.2f})")
            print(f"    Context: {s['context']}")
        
        print("\n💾 Saving scenarios to file...")
        save_scenarios_to_file(scenarios)
        print("\n✅ Done!")
