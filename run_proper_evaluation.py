"""
Run proper LLM evaluation using existing users with purchase history
This will showcase the Personalized and Hybrid AI systems properly
"""

import json
import requests
from llm_judge_evaluation import evaluate_all_systems, print_report

BASE_URL = "http://localhost:5000"

# Use existing user with 8 purchases (rich history)
USER_SESSION_ID = "demo_user_001"

print("\n🎯 Running LLM Evaluation with Real User Purchase History")
print("="*70)
print(f"Using user: {USER_SESSION_ID} (8 purchases, $4,187.83 total)")
print("="*70)

# Create a realistic cart that will trigger recommendations
cart = [
    {
        "id": "7875624813017570385",
        "title": "David's Cookies Mile High Peanut Butter Cake, 6.8 lbs (14 Servings)",
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

budget = 80.0  # Set budget below cart total to trigger recommendations
cart_total = sum(item["price"] * item.get("qty", 1) for item in cart)
over_budget = cart_total - budget

print(f"\nCart Setup:")
print(f"  Budget: ${budget:.2f}")
print(f"  Cart Total: ${cart_total:.2f}")
print(f"  Over Budget: ${over_budget:.2f}")
print(f"  Items: {len(cart)}")

# Set session cookie to use existing user
session = requests.Session()
session.cookies.set('session_id', USER_SESSION_ID)

print(f"\n🔄 Getting recommendations from all 3 systems...")

# Get recommendations from each system
results = {
    "budget_saving": [],
    "personalized_cf": [],
    "hybrid_ai": []
}

try:
    # Budget-Saving recommendations
    response = session.post(
        f"{BASE_URL}/api/budget/recommendations",
        json={"cart": cart, "budget": budget},
        headers={"Cookie": f"session_id={USER_SESSION_ID}"}
    )
    if response.status_code == 200:
        data = response.json()
        results["budget_saving"] = data.get("suggestions", [])
        print(f"  ✓ Budget-Saving: {len(results['budget_saving'])} suggestions")
    
    # Personalized CF recommendations
    response = session.post(
        f"{BASE_URL}/api/cf/recommendations",
        json={"cart": cart, "budget": budget},
        headers={"Cookie": f"session_id={USER_SESSION_ID}"}
    )
    if response.status_code == 200:
        data = response.json()
        results["personalized_cf"] = data.get("suggestions", [])
        print(f"  ✓ Personalized CF: {len(results['personalized_cf'])} suggestions")
    
    # Hybrid AI recommendations  
    response = session.post(
        f"{BASE_URL}/api/blended/recommendations",
        json={"cart": cart, "budget": budget},
        headers={"Cookie": f"session_id={USER_SESSION_ID}"}
    )
    if response.status_code == 200:
        data = response.json()
        results["hybrid_ai"] = data.get("suggestions", [])
        print(f"  ✓ Hybrid AI: {len(results['hybrid_ai'])} suggestions")

except Exception as e:
    print(f"  ❌ Error getting recommendations: {e}")
    print("\nMake sure Flask is running: python main.py")
    exit(1)

# Prepare user context
user_context = {
    "user_type": "Experienced shopper with 8 previous purchases ($4,187.83 total)",
    "budget": budget,
    "cart_total": cart_total,
    "over_budget": over_budget,
    "cart_items": cart
}

# Run LLM evaluation
print(f"\n🤖 Running LLM-as-a-Judge evaluation with GPT-5...")
evaluation_results = evaluate_all_systems(
    user_context,
    results["budget_saving"],
    results["personalized_cf"],
    results["hybrid_ai"]
)

# Print report
print_report(evaluation_results)

# Save detailed results
output_file = "evaluation_results_real_user.json"
with open(output_file, 'w') as f:
    json.dump(evaluation_results, f, indent=2)

print(f"\n✓ Results saved to: {output_file}")

# Print scores table
print("\n" + "="*70)
print("SCORE SUMMARY TABLE")
print("="*70)

criteria = evaluation_results.get("criteria_scores", {})

print(f"\n{'Criterion':<25} {'Budget-Saving':<15} {'Personalized':<15} {'Hybrid AI':<15}")
print("-"*70)

for criterion in ["relevance", "savings", "diversity", "explanation_quality", "feasibility", "overall_score"]:
    budget_score = criteria.get("budget_saving", {}).get(criterion, 0)
    cf_score = criteria.get("personalized_cf", {}).get(criterion, 0)
    hybrid_score = criteria.get("hybrid_ai", {}).get(criterion, 0)
    
    criterion_name = criterion.replace("_", " ").title()
    print(f"{criterion_name:<25} {budget_score:>4}/10        {cf_score:>4}/10        {hybrid_score:>4}/10")

print("="*70)
print(f"\n🏆 OVERALL WINNER: {evaluation_results['summary'].get('overall_winner', 'N/A').replace('_', ' ').title()}")
print("="*70 + "\n")
