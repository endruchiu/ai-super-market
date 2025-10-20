"""
Build realistic purchase history through the web app, then evaluate all systems
This will get all 3 recommendation systems working properly!
"""

import requests
import json
from llm_judge_evaluation import evaluate_all_systems, print_report
from traditional_evaluation_metrics import compare_recommendation_systems
import pandas as pd

BASE_URL = "http://localhost:5000"

def build_purchase_history(session):
    """Build purchase history by completing 3 purchases"""
    
    print("\n" + "="*70)
    print("STEP 1: Building Purchase History")
    print("="*70)
    
    # Purchase 1: Healthy/Organic items
    purchase_1 = [
        {"title": "Kirkland Signature Organic Chicken Stock", "price": 11.99, "qty": 2, "subcat": "Organic"},
        {"title": "Kirkland Signature Organic Almond Beverage", "price": 9.99, "qty": 2, "subcat": "Organic"},
        {"title": "Pure Organic Layered Fruit Bars", "price": 11.89, "qty": 1, "subcat": "Snacks"},
    ]
    
    # Purchase 2: Bakery & Desserts
    purchase_2 = [
        {"title": "David's Cookies Cheesecake", "price": 59.99, "qty": 1, "subcat": "Bakery & Desserts"},
        {"title": "Classic Cake Limoncello", "price": 89.99, "qty": 1, "subcat": "Bakery & Desserts"},
    ]
    
    # Purchase 3: Mixed groceries
    purchase_3 = [
        {"title": "Kirkland Signature Organic Pine Nuts", "price": 33.99, "qty": 1, "subcat": "Organic"},
        {"title": "Thai Kitchen Organic Coconut Milk", "price": 14.99, "qty": 2, "subcat": "Pantry & Dry Goods"},
        {"title": "Made In Nature Organic Calimyrna Figs", "price": 49.99, "qty": 1, "subcat": "Organic"},
        {"title": "Ruta Maya Organic Dark Roast Coffee", "price": 44.99, "qty": 1, "subcat": "Coffee"},
    ]
    
    purchases = [purchase_1, purchase_2, purchase_3]
    
    for i, purchase in enumerate(purchases, 1):
        total = sum(item['price'] * item['qty'] for item in purchase)
        print(f"\nPurchase {i}: ${total:.2f} ({len(purchase)} items)")
        for item in purchase:
            print(f"  - {item['title'][:40]}... ${item['price']:.2f} x{item['qty']}")
        
        # Complete purchase via API
        try:
            response = session.post(
                f"{BASE_URL}/api/checkout",
                json={"cart": purchase}
            )
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    print(f"  ✓ Purchase completed! Order #{data.get('order_id')}")
                else:
                    print(f"  ❌ Purchase failed: {data.get('error')}")
            else:
                print(f"  ❌ HTTP {response.status_code}")
        except Exception as e:
            print(f"  ❌ Error: {e}")
    
    print(f"\n✓ Completed 3 purchases with varied items!")
    print("  This gives the CF model real purchase patterns to learn from.")


def get_recommendations_over_budget(session):
    """Create a cart over budget and get recommendations from all 3 systems"""
    
    print("\n" + "="*70)
    print("STEP 2: Triggering Recommendations (Cart Over Budget)")
    print("="*70)
    
    # Create cart that exceeds budget
    cart = [
        {
            "id": "7875624813017570385",
            "title": "David's Cookies Mile High Peanut Butter Cake, 6.8 lbs",
            "subcat": "Bakery & Desserts",
            "price": 56.99,
            "qty": 1
        },
        {
            "id": "8602147923846103921",  
            "title": "Premium Organic Beef Ribeye Steak, 12 oz",
            "subcat": "Meat & Seafood",
            "price": 45.99,
            "qty": 1
        },
        {
            "id": "3575723596463500350",
            "title": "Kirkland Signature Organic Almond Beverage, Vanilla, 32 fl oz",
            "subcat": "Organic",
            "price": 9.99,
            "qty": 2
        }
    ]
    
    budget = 80.0
    cart_total = sum(item["price"] * item.get("qty", 1) for item in cart)
    
    print(f"\nTest Cart:")
    print(f"  Budget: ${budget:.2f}")
    print(f"  Cart Total: ${cart_total:.2f}")
    print(f"  Over Budget: ${cart_total - budget:.2f}")
    print(f"\n  Items in cart:")
    for item in cart:
        print(f"  - {item['title'][:50]} ${item['price']:.2f} x{item.get('qty', 1)}")
    
    print(f"\n🔄 Getting recommendations from all 3 systems...")
    
    results = {
        "budget_saving": [],
        "personalized_cf": [],
        "hybrid_ai": []
    }
    
    try:
        # Budget-Saving recommendations
        response = session.post(
            f"{BASE_URL}/api/budget/recommendations",
            json={"cart": cart, "budget": budget}
        )
        if response.status_code == 200:
            data = response.json()
            results["budget_saving"] = data.get("suggestions", [])
            print(f"  ✓ Budget-Saving: {len(results['budget_saving'])} recommendations")
            if results["budget_saving"]:
                for i, rec in enumerate(results["budget_saving"][:2], 1):
                    print(f"    {i}. {rec.get('with', 'N/A')[:40]}... (save ${rec.get('expected_saving', 0)})")
        
        # Personalized CF recommendations  
        response = session.post(
            f"{BASE_URL}/api/cf/recommendations",
            json={"cart": cart, "budget": budget}
        )
        if response.status_code == 200:
            data = response.json()
            results["personalized_cf"] = data.get("suggestions", [])
            print(f"  ✓ Personalized CF: {len(results['personalized_cf'])} recommendations")
            if results["personalized_cf"]:
                for i, rec in enumerate(results["personalized_cf"][:2], 1):
                    print(f"    {i}. {rec.get('with', 'N/A')[:40]}... (save ${rec.get('expected_saving', 0)})")
        
        # Hybrid AI recommendations
        response = session.post(
            f"{BASE_URL}/api/blended/recommendations",
            json={"cart": cart, "budget": budget}
        )
        if response.status_code == 200:
            data = response.json()
            results["hybrid_ai"] = data.get("suggestions", [])
            print(f"  ✓ Hybrid AI: {len(results['hybrid_ai'])} recommendations")
            if results["hybrid_ai"]:
                for i, rec in enumerate(results["hybrid_ai"][:2], 1):
                    print(f"    {i}. {rec.get('with', 'N/A')[:40]}... (save ${rec.get('expected_saving', 0)})")
    
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return None, None, None
    
    return results, cart, budget


def run_both_evaluations(results, cart, budget):
    """Run both LLM and traditional evaluations"""
    
    cart_total = sum(item["price"] * item.get("qty", 1) for item in cart)
    
    # ==================================================================
    # TRADITIONAL EVALUATION
    # ==================================================================
    print("\n" + "="*70)
    print("STEP 3: Traditional Evaluation (No LLM)")
    print("="*70)
    
    comparison_df = compare_recommendation_systems(
        results["budget_saving"],
        results["personalized_cf"],
        results["hybrid_ai"],
        cart
    )
    
    print("\n" + comparison_df.to_string(index=False))
    
    # Save traditional results
    comparison_df.to_csv('evaluation_with_history_traditional.csv', index=False)
    print(f"\n✓ Traditional results saved to: evaluation_with_history_traditional.csv")
    
    # ==================================================================
    # LLM EVALUATION
    # ==================================================================
    print("\n" + "="*70)
    print("STEP 4: LLM-as-a-Judge Evaluation (GPT-5)")
    print("="*70)
    
    user_context = {
        "user_type": "Active shopper with purchase history (3 recent orders: organic items, desserts, groceries)",
        "budget": budget,
        "cart_total": cart_total,
        "over_budget": cart_total - budget,
        "cart_items": cart
    }
    
    try:
        evaluation_results = evaluate_all_systems(
            user_context,
            results["budget_saving"],
            results["personalized_cf"],
            results["hybrid_ai"]
        )
        
        print_report(evaluation_results)
        
        # Save LLM results
        with open('evaluation_with_history_llm.json', 'w') as f:
            json.dump(evaluation_results, f, indent=2)
        
        print(f"\n✓ LLM results saved to: evaluation_with_history_llm.json")
        
        # Print score comparison
        print("\n" + "="*70)
        print("FINAL SCORES COMPARISON")
        print("="*70)
        
        print(f"\n📊 LLM Scores (0-10):")
        criteria = evaluation_results.get("criteria_scores", {})
        
        print(f"\n{'System':<20} {'Relevance':<12} {'Savings':<12} {'Diversity':<12} {'Overall':<12}")
        print("-"*70)
        
        for system in ["budget_saving", "personalized_cf", "hybrid_ai"]:
            scores = criteria.get(system, {})
            sys_name = system.replace('_', ' ').title()
            print(f"{sys_name:<20} {scores.get('relevance', 0):>4}/10      {scores.get('savings', 0):>4}/10      {scores.get('diversity', 0):>4}/10      {scores.get('overall_score', 0):>4}/10")
        
        print(f"\n🏆 LLM Winner: {evaluation_results['summary'].get('overall_winner', 'N/A').replace('_', ' ').title()}")
        
    except Exception as e:
        print(f"\n❌ LLM Evaluation failed: {e}")
        print("(Skipping LLM evaluation - traditional metrics still available)")


def main():
    """Main execution"""
    
    print("\n" + "="*70)
    print("🎯 COMPLETE EVALUATION WITH REAL PURCHASE HISTORY")
    print("="*70)
    print("\nThis will:")
    print("  1. Build realistic purchase history (3 purchases)")
    print("  2. Trigger all 3 recommendation systems")
    print("  3. Evaluate with BOTH traditional metrics AND GPT-5")
    print("="*70)
    
    # Create persistent session
    session = requests.Session()
    
    # Step 1: Build purchase history
    build_purchase_history(session)
    
    # Step 2: Get recommendations
    results, cart, budget = get_recommendations_over_budget(session)
    
    if results is None:
        print("\n❌ Failed to get recommendations. Exiting.")
        return
    
    # Step 3 & 4: Run both evaluations
    run_both_evaluations(results, cart, budget)
    
    print("\n" + "="*70)
    print("✅ EVALUATION COMPLETE!")
    print("="*70)
    print("\nResults saved:")
    print("  - evaluation_with_history_traditional.csv (Traditional metrics)")
    print("  - evaluation_with_history_llm.json (GPT-5 scores)")
    print("="*70 + "\n")


if __name__ == "__main__":
    main()
