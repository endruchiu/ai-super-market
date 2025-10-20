"""
Evaluate recommendation systems using traditional metrics (NO LLM)
Run this to get objective scores without AI judgment
"""

import requests
import pandas as pd
from traditional_evaluation_metrics import compare_recommendation_systems, TraditionalEvaluator

BASE_URL = "http://localhost:5000"

def run_traditional_evaluation():
    """Run complete traditional evaluation"""
    
    print("\n" + "="*70)
    print("TRADITIONAL EVALUATION (NO LLM REQUIRED)")
    print("Using Standard Recommendation System Metrics")
    print("="*70)
    
    # Test cart
    cart = [
        {
            "title": "David's Cookies Mile High Peanut Butter Cake, 6.8 lbs",
            "subcat": "Bakery & Desserts",
            "price": 56.99,
            "qty": 1
        },
        {
            "title": "Premium Organic Beef Ribeye Steak, 12 oz",
            "subcat": "Meat & Seafood",
            "price": 45.99,
            "qty": 1
        }
    ]
    
    budget = 50.0
    cart_total = sum(item["price"] * item.get("qty", 1) for item in cart)
    
    print(f"\nTest Scenario:")
    print(f"  Budget: ${budget:.2f}")
    print(f"  Cart Total: ${cart_total:.2f}")
    print(f"  Over Budget: ${cart_total - budget:.2f}")
    print(f"  Items: {len(cart)}")
    
    print(f"\n🔄 Getting recommendations from all 3 systems...")
    
    # Get recommendations
    results = {
        "budget_saving": [],
        "personalized_cf": [],
        "hybrid_ai": []
    }
    
    try:
        # Budget-Saving
        response = requests.post(
            f"{BASE_URL}/api/budget/recommendations",
            json={"cart": cart, "budget": budget}
        )
        if response.status_code == 200:
            data = response.json()
            results["budget_saving"] = data.get("suggestions", [])
            print(f"  ✓ Budget-Saving: {len(results['budget_saving'])} recommendations")
        
        # Personalized CF
        response = requests.post(
            f"{BASE_URL}/api/cf/recommendations",
            json={"cart": cart, "budget": budget}
        )
        if response.status_code == 200:
            data = response.json()
            results["personalized_cf"] = data.get("suggestions", [])
            print(f"  ✓ Personalized CF: {len(results['personalized_cf'])} recommendations")
        
        # Hybrid AI
        response = requests.post(
            f"{BASE_URL}/api/blended/recommendations",
            json={"cart": cart, "budget": budget}
        )
        if response.status_code == 200:
            data = response.json()
            results["hybrid_ai"] = data.get("suggestions", [])
            print(f"  ✓ Hybrid AI: {len(results['hybrid_ai'])} recommendations")
    
    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("Make sure Flask is running: python main.py")
        return
    
    # Generate comparison table
    print(f"\n📊 EVALUATION RESULTS")
    print("="*70)
    
    comparison_df = compare_recommendation_systems(
        results["budget_saving"],
        results["personalized_cf"],
        results["hybrid_ai"],
        cart
    )
    
    print("\n" + comparison_df.to_string(index=False))
    
    # Detailed metrics for each system
    evaluator = TraditionalEvaluator()
    
    print(f"\n\n📈 DETAILED METRICS")
    print("="*70)
    
    for system_name, recs in [
        ('Budget-Saving', results['budget_saving']),
        ('Personalized CF', results['personalized_cf']),
        ('Hybrid AI', results['hybrid_ai'])
    ]:
        print(f"\n{system_name}:")
        print(f"  Recommendations: {len(recs)}")
        
        if recs:
            # Cost savings
            savings = evaluator.cost_savings_metric(cart, recs)
            print(f"  Total Potential Savings: ${savings['total_potential_savings']:.2f}")
            print(f"  Average Savings per Item: ${savings['avg_savings_per_item']:.2f}")
            print(f"  Savings Percentage: {savings['savings_percentage']:.1f}%")
            
            # Diversity
            diversity = evaluator.diversity_score(recs)
            print(f"  Diversity Score: {diversity:.2f} (higher = more varied)")
            
            # Category matching
            if cart:
                category_match = evaluator.category_match_score(cart[0], recs)
                print(f"  Category Match: {category_match:.2f} (1.0 = perfect match)")
                
                # Price appropriateness
                price_scores = evaluator.price_appropriateness(cart[0], recs)
                print(f"  Average Discount: {price_scores['avg_discount']:.1f}%")
                print(f"  Reasonable Pricing Rate: {price_scores['reasonable_rate']:.1f}%")
        else:
            print(f"  No recommendations to evaluate")
    
    # Winner determination
    print(f"\n\n🏆 WINNER DETERMINATION")
    print("="*70)
    
    # Calculate overall scores
    scores = {}
    for system_name, recs in [
        ('Budget-Saving', results['budget_saving']),
        ('Personalized CF', results['personalized_cf']),
        ('Hybrid AI', results['hybrid_ai'])
    ]:
        if not recs:
            scores[system_name] = 0.0
            continue
        
        savings = evaluator.cost_savings_metric(cart, recs)
        diversity = evaluator.diversity_score(recs)
        category_match = evaluator.category_match_score(cart[0], recs) if cart else 0.0
        
        # Composite score (weighted average)
        score = (
            savings['savings_percentage'] * 0.4 +  # 40% weight on savings
            diversity * 30 +  # 30% weight on diversity (normalized to %)
            category_match * 30  # 30% weight on relevance (normalized to %)
        )
        scores[system_name] = score
    
    # Print rankings
    ranked = sorted(scores.items(), key=lambda x: -x[1])
    
    print(f"\nRanking by Composite Score:")
    for rank, (system, score) in enumerate(ranked, 1):
        print(f"  {rank}. {system}: {score:.2f} points")
    
    print(f"\n🥇 Winner: {ranked[0][0]}")
    
    # Export results
    comparison_df.to_csv('traditional_evaluation_results.csv', index=False)
    print(f"\n✓ Results saved to: traditional_evaluation_results.csv")
    print("="*70 + "\n")


if __name__ == "__main__":
    run_traditional_evaluation()
