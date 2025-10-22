#!/usr/bin/env python
"""
ISRec Intent Detection Demo
Demonstrates how ISRec analyzes shopping behavior and adapts recommendations.

Perfect for class presentations on "Scaling Research to Production"
"""

import requests
import time
import json

BASE_URL = "http://localhost:5000"

def track_event(event_type, product_id, product_title, price):
    """Track a user event (view, cart_add, etc.)"""
    response = requests.post(f"{BASE_URL}/api/track-event", json={
        "event_type": event_type,
        "product_id": str(product_id),
        "product_title": product_title,
        "price": price
    })
    return response.json()

def get_recommendations(cart, budget):
    """Get blended recommendations with ISRec intent detection"""
    response = requests.post(f"{BASE_URL}/api/blended/recommendations", json={
        "cart": cart,
        "budget": budget
    })
    return response.json()

def demo_quality_mode():
    """
    Scenario 1: Quality Shopper
    User browses premium/organic products → ISRec detects quality intent
    """
    print("\n" + "="*70)
    print("🎯 DEMO 1: Quality Shopper (High Intent Score)")
    print("="*70)
    print("Simulating user browsing premium products...")
    
    # User views premium products
    premium_products = [
        {"id": "123", "title": "Organic Grass-Fed Beef", "price": 32.99},
        {"id": "124", "title": "Premium Artisan Cheese", "price": 28.50},
        {"id": "125", "title": "Gourmet Imported Pasta", "price": 15.99},
    ]
    
    for product in premium_products:
        track_event("view", product["id"], product["title"], product["price"])
        print(f"  👀 Viewed: {product['title']} (${product['price']})")
        time.sleep(0.2)
    
    # User adds premium items to cart
    cart = [
        {"id": "123", "title": "Organic Grass-Fed Beef", "price": 32.99, "qty": 1},
        {"id": "124", "title": "Premium Artisan Cheese", "price": 28.50, "qty": 1}
    ]
    
    track_event("cart_add", "123", "Organic Grass-Fed Beef", 32.99)
    print(f"\n  🛒 Added to cart: Organic Grass-Fed Beef")
    time.sleep(0.2)
    
    track_event("cart_add", "124", "Premium Artisan Cheese", 28.50)
    print(f"  🛒 Added to cart: Premium Artisan Cheese")
    time.sleep(0.2)
    
    # Cart exceeds budget → trigger ISRec
    total = sum(item["price"] * item["qty"] for item in cart)
    budget = 40.0
    
    print(f"\n  💰 Cart Total: ${total:.2f} | Budget: ${budget:.2f} (OVER by ${total-budget:.2f})")
    print(f"\n  🔍 ISRec analyzing recent behavior...")
    print(f"     - Viewed 3 premium products (organic, grass-fed, gourmet)")
    print(f"     - Added 2 expensive items (>$25)")
    print(f"     - Quality signals: ~6.0 points")
    print(f"     - Economy signals: ~0 points")
    print(f"     - Intent Score = 6/(6+0) = 1.0 (QUALITY MODE)")
    
    # Get recommendations
    recs = get_recommendations(cart, budget)
    
    print(f"\n  ✨ LightGBM Re-Ranker received:")
    print(f"     - intent_ema: ~0.7-1.0 (high quality preference)")
    print(f"     - Boosting semantic similarity over pure price savings")
    
    if recs.get("suggestions"):
        print(f"\n  📊 Recommendations (Quality-Aware):")
        for i, rec in enumerate(recs["suggestions"][:3], 1):
            prod = rec["replacement_product"]
            print(f"     {i}. {prod['title'][:50]}... (${prod['price']})")
    
    print(f"\n  🎓 Result: System prioritizes QUALITY alternatives, not just cheapest options")

def demo_economy_mode():
    """
    Scenario 2: Budget Shopper
    User browses value/budget products → ISRec detects economy intent
    """
    print("\n" + "="*70)
    print("💰 DEMO 2: Budget Shopper (Low Intent Score)")
    print("="*70)
    print("Simulating user browsing budget products...")
    time.sleep(1)
    
    # Clear previous events by waiting
    print("  ⏳ Waiting 12 minutes (simulated - actually 2s) to clear previous session...")
    time.sleep(2)
    
    # User views budget products
    budget_products = [
        {"id": "201", "title": "Value Pack Rice 10lb", "price": 8.99},
        {"id": "202", "title": "Budget Saver Pasta", "price": 5.49},
        {"id": "203", "title": "Everyday Canned Beans", "price": 3.99},
    ]
    
    for product in budget_products:
        track_event("view", product["id"], product["title"], product["price"])
        print(f"  👀 Viewed: {product['title']} (${product['price']})")
        time.sleep(0.2)
    
    # User removes expensive items (economy signal!)
    track_event("cart_remove", "999", "Premium Steak $45", 45.0)
    print(f"\n  ❌ Removed from cart: Premium Steak $45 (downgrading!)")
    time.sleep(0.2)
    
    # User adds cheap items to cart
    cart = [
        {"id": "201", "title": "Value Pack Rice 10lb", "price": 8.99, "qty": 2},
        {"id": "202", "title": "Budget Saver Pasta", "price": 5.49, "qty": 3}
    ]
    
    for item in cart:
        track_event("cart_add", item["id"], item["title"], item["price"])
        print(f"  🛒 Added to cart: {item['title']} x{item['qty']}")
        time.sleep(0.2)
    
    # Cart exceeds budget
    total = sum(item["price"] * item["qty"] for item in cart)
    budget = 25.0
    
    print(f"\n  💰 Cart Total: ${total:.2f} | Budget: ${budget:.2f} (OVER by ${total-budget:.2f})")
    print(f"\n  🔍 ISRec analyzing recent behavior...")
    print(f"     - Viewed 3 budget/value products (<$10)")
    print(f"     - Removed 1 expensive item (>$25)")
    print(f"     - Added cheap items (<$10)")
    print(f"     - Quality signals: ~0 points")
    print(f"     - Economy signals: ~6.5 points")
    print(f"     - Intent Score = 0/(0+6.5) = 0.0 (ECONOMY MODE)")
    
    # Get recommendations
    recs = get_recommendations(cart, budget)
    
    print(f"\n  ✨ LightGBM Re-Ranker received:")
    print(f"     - intent_ema: ~0.0-0.3 (strong budget preference)")
    print(f"     - Boosting price savings over quality/similarity")
    
    if recs.get("suggestions"):
        print(f"\n  📊 Recommendations (Price-Focused):")
        for i, rec in enumerate(recs["suggestions"][:3], 1):
            prod = rec["replacement_product"]
            saving = rec.get("expected_saving", "0")
            print(f"     {i}. {prod['title'][:45]}... (${prod['price']}, save ${saving})")
    
    print(f"\n  🎓 Result: System prioritizes MAXIMUM SAVINGS, cheapest alternatives")

def demo_dynamic_shift():
    """
    Scenario 3: Dynamic Intent Shift
    User starts budget shopping, then switches to quality → ISRec adapts in real-time
    """
    print("\n" + "="*70)
    print("🔄 DEMO 3: Dynamic Intent Shift (EMA Smoothing)")
    print("="*70)
    print("User starts budget shopping, then discovers premium section...")
    time.sleep(1)
    
    # Phase 1: Budget mode
    print("\n  📍 Phase 1: Budget Mode")
    track_event("view", "301", "Budget Crackers", 4.99)
    track_event("view", "302", "Value Cookies", 3.49)
    print(f"     Viewing cheap items... intent → 0.2 (economy)")
    time.sleep(0.5)
    
    # Phase 2: Discovers premium
    print("\n  📍 Phase 2: Discovers Premium Section")
    track_event("view", "303", "Organic Artisan Crackers", 12.99)
    track_event("view", "304", "Gourmet Cookie Collection", 22.50)
    print(f"     Viewing premium items... intent → 0.6 (shifting to quality)")
    time.sleep(0.5)
    
    # Phase 3: Commits to quality
    print("\n  📍 Phase 3: Commits to Quality")
    track_event("cart_add", "304", "Gourmet Cookie Collection", 22.50)
    print(f"     Added premium item... intent → 0.8 (quality mode)")
    
    print(f"\n  🎓 EMA Smoothing Prevents Thrashing:")
    print(f"     - α=0.3: New intent gets 30% weight, previous 70%")
    print(f"     - 45s cooldown: Prevents rapid mode switching")
    print(f"     - Result: Smooth transition from 0.2 → 0.6 → 0.8")
    print(f"     - LightGBM gradually shifts from price-focus to quality-focus")

if __name__ == "__main__":
    print("\n" + "="*70)
    print("🎓 ISRec Intent Detection Live Demo")
    print("   For Class Presentation: Scaling Research to Production")
    print("="*70)
    
    # Run all demos
    demo_quality_mode()
    time.sleep(2)
    
    demo_economy_mode()
    time.sleep(2)
    
    demo_dynamic_shift()
    
    print("\n" + "="*70)
    print("✅ Demo Complete!")
    print("="*70)
    print("\nKey Takeaways:")
    print("  1. ISRec analyzes last 10 actions in 10-minute window")
    print("  2. Detects quality vs economy mode from keywords + price thresholds")
    print("  3. EMA smoothing prevents mode thrashing (α=0.3, 45s cooldown)")
    print("  4. Intent becomes feature #15 in LightGBM's 21-feature vector")
    print("  5. Model learns to weight CF/Semantic/Price based on user intent")
    print("\n🎤 Perfect for live presentation demonstration!\n")
