"""
Test runner for LLM-as-a-Judge evaluation
Generates test scenarios and evaluates all 3 recommendation systems
Supports both cold-start and warm-start scenarios for fair CF evaluation
"""

import json
import requests
from llm_judge_evaluation import evaluate_all_systems, print_report

# Base URL for local Flask API
BASE_URL = "http://localhost:5000"

# Load warm-start scenarios if available
WARM_START_SCENARIOS = None
try:
    with open('warm_start_test_scenarios.json', 'r') as f:
        data = json.load(f)
        WARM_START_SCENARIOS = {f"warm_start_{i+1}": scenario 
                                for i, scenario in enumerate(data.get('scenarios', []))}
except FileNotFoundError:
    print("⚠️  warm_start_test_scenarios.json not found - warm-start scenarios unavailable")
    print("    Run: python warm_start_scenarios.py to generate them")


def get_recommendations_for_cart(cart, budget, session_id=None):
    """
    Get recommendations from all 3 systems for a given cart.
    
    Args:
        cart: List of cart items
        budget: Budget amount
        session_id: Optional session ID for warm-start scenarios (enables CF personalization)
    """
    
    payload = {
        "cart": cart,
        "budget": budget
    }
    
    # Add session_id to payload if provided (for CF personalization)
    if session_id:
        payload["session_id"] = session_id
    
    results = {
        "budget_saving": [],
        "personalized_cf": [],
        "hybrid_ai": []
    }
    
    try:
        # Budget-Saving recommendations
        response = requests.post(f"{BASE_URL}/api/budget/recommendations", json=payload)
        if response.status_code == 200:
            data = response.json()
            results["budget_saving"] = data.get("suggestions", [])
        
        # Personalized CF recommendations
        response = requests.post(f"{BASE_URL}/api/cf/recommendations", json=payload)
        if response.status_code == 200:
            data = response.json()
            results["personalized_cf"] = data.get("suggestions", [])
        
        # Hybrid AI recommendations
        response = requests.post(f"{BASE_URL}/api/blended/recommendations", json=payload)
        if response.status_code == 200:
            data = response.json()
            results["hybrid_ai"] = data.get("suggestions", [])
    
    except Exception as e:
        print(f"Error getting recommendations: {e}")
    
    return results


def create_test_scenario(scenario_type="budget_conscious"):
    """
    Create test scenarios for different user types.
    """
    
    scenarios = {
        "budget_conscious": {
            "user_type": "Budget-conscious family shopper",
            "budget": 50.0,
            "cart": [
                {
                    "id": "7875624813017570385",
                    "title": "David's Cookies Mile High Peanut Butter Cake, 6.8 lbs (14 Servings)",
                    "subcat": "Dessert",
                    "price": 56.99,
                    "qty": 1
                },
                {
                    "id": "8602147923846103921",
                    "title": "Premium Organic Beef Ribeye Steak, 12 oz",
                    "subcat": "Meat & Seafood",
                    "price": 45.99,
                    "qty": 1
                }
            ]
        },
        
        "health_focused": {
            "user_type": "Health-conscious organic shopper",
            "budget": 80.0,
            "cart": [
                {
                    "id": "6988010420398241892",
                    "title": "Kirkland Signature, Organic Chicken Stock, 32 fl oz, 6-Count",
                    "subcat": "Organic",
                    "price": 11.99,
                    "qty": 2
                },
                {
                    "id": "3575723596463500350",
                    "title": "Kirkland Signature, Organic Almond Beverage, Vanilla, 32 fl oz, 6-Count",
                    "subcat": "Organic",
                    "price": 9.99,
                    "qty": 3
                },
                {
                    "id": "7875624813017570385",
                    "title": "David's Cookies Mile High Peanut Butter Cake, 6.8 lbs",
                    "subcat": "Dessert",
                    "price": 56.99,
                    "qty": 1
                }
            ]
        },
        
        "new_user": {
            "user_type": "New user (tests cold start handling)",
            "budget": 40.0,
            "cart": [
                {
                    "id": "7875624813017570385",
                    "title": "David's Cookies Mile High Peanut Butter Cake, 6.8 lbs",
                    "subcat": "Dessert",
                    "price": 56.99,
                    "qty": 1
                }
            ]
        },
        
        "frequent_shopper": {
            "user_type": "Frequent shopper with purchase history (10+ orders)",
            "budget": 60.0,
            "cart": [
                {
                    "id": "1234567890",
                    "title": "Kirkland Signature Protein Bars Chocolate Chip Cookie Dough 20-count",
                    "subcat": "Snacks",
                    "price": 24.99,
                    "qty": 2
                },
                {
                    "id": "9876543210",
                    "title": "Organic Whole Milk, 1 Gallon",
                    "subcat": "Dairy",
                    "price": 8.99,
                    "qty": 3
                }
            ],
            "note": "Tests CF with purchase history - should show personalized recommendations"
        },
        
        "loyal_customer": {
            "user_type": "Loyal customer with extensive history (50+ orders)",
            "budget": 100.0,
            "cart": [
                {
                    "id": "5555555555",
                    "title": "Premium Organic Chicken Breast, 5 lbs",
                    "subcat": "Meat & Poultry",
                    "price": 42.99,
                    "qty": 2
                },
                {
                    "id": "6666666666",
                    "title": "Kirkland Signature Organic Quinoa, 4 lbs",
                    "subcat": "Grains & Rice",
                    "price": 19.99,
                    "qty": 1
                },
                {
                    "id": "7777777777",
                    "title": "Organic Mixed Berries, 3 lbs",
                    "subcat": "Frozen Fruit",
                    "price": 15.99,
                    "qty": 2
                }
            ],
            "note": "Tests CF peak performance - should show highly accurate personalization"
        }
    }
    
    return scenarios.get(scenario_type, scenarios["budget_conscious"])


def run_evaluation(scenario_name="budget_conscious"):
    """
    Run complete evaluation for a scenario (cold-start or warm-start).
    """
    
    print("\n" + "="*60)
    print(f"TESTING SCENARIO: {scenario_name.replace('_', ' ').upper()}")
    print("="*60)
    
    # Check if this is a warm-start scenario
    is_warm_start = scenario_name.startswith("warm_start_")
    session_id = None
    
    if is_warm_start:
        if not WARM_START_SCENARIOS or scenario_name not in WARM_START_SCENARIOS:
            print(f"ERROR: Warm-start scenario '{scenario_name}' not found")
            print("Run: python warm_start_scenarios.py to generate warm-start scenarios")
            return None
        
        # Load warm-start scenario from file
        ws_scenario = WARM_START_SCENARIOS[scenario_name]
        session_id = ws_scenario["session_id"]
        cart = ws_scenario["cart"]
        budget = ws_scenario["budget"]
        cart_total = ws_scenario["cart_total"]
        over_budget = ws_scenario["over_budget"]
        
        user_type = f"Warm-Start: {ws_scenario['strategy']} ({ws_scenario['context']['user_stats']['total_orders']} orders)"
        
        print(f"\n🔥 WARM-START Scenario (has purchase history)")
        print(f"   Session ID: {session_id}")
        print(f"   Strategy: {ws_scenario['strategy']}")
        print(f"   User Stats: {ws_scenario['context']['user_stats']}")
        
    else:
        # Cold-start scenario (original behavior)
        scenario = create_test_scenario(scenario_name)
        cart = scenario["cart"]
        budget = scenario["budget"]
        cart_total = sum(item["price"] * item.get("qty", 1) for item in cart)
        over_budget = cart_total - budget
        user_type = scenario["user_type"]
        
        print(f"\n❄️  COLD-START Scenario (no purchase history)")
    
    # Get recommendations from all systems (pass session_id for warm-start)
    print(f"\nGetting recommendations from all 3 systems...")
    recommendations = get_recommendations_for_cart(cart, budget, session_id=session_id)
    
    print(f"  Budget-Saving: {len(recommendations['budget_saving'])} suggestions")
    print(f"  Personalized CF: {len(recommendations['personalized_cf'])} suggestions")
    print(f"  Hybrid AI: {len(recommendations['hybrid_ai'])} suggestions")
    
    # Prepare user context
    user_context = {
        "user_type": user_type,
        "budget": budget,
        "cart_total": cart_total,
        "over_budget": over_budget,
        "cart_items": cart,
        "is_warm_start": is_warm_start,
        "session_id": session_id if is_warm_start else None
    }
    
    # Run LLM evaluation
    results = evaluate_all_systems(
        user_context,
        recommendations["budget_saving"],
        recommendations["personalized_cf"],
        recommendations["hybrid_ai"]
    )
    
    # Print report
    print_report(results)
    
    # Save results
    output_file = f"evaluation_results_{scenario_name}.json"
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n✓ Results saved to: {output_file}")
    
    return results


def run_all_scenarios():
    """
    Run evaluation for all test scenarios (cold-start + warm-start).
    """
    
    # Include both cold-start and warm-start scenarios
    scenarios = [
        "budget_conscious",      # Cold-start
        "health_focused",        # Cold-start  
        "new_user",             # Cold-start
        "frequent_shopper",     # Warm-start
        "loyal_customer"        # Warm-start
    ]
    all_results = {}
    
    for scenario in scenarios:
        try:
            results = run_evaluation(scenario)
            all_results[scenario] = results
        except Exception as e:
            print(f"\nError evaluating {scenario}: {e}")
            continue
    
    # Generate combined summary
    print("\n" + "="*60)
    print("COMBINED SUMMARY ACROSS ALL SCENARIOS")
    print("="*60)
    
    overall_wins = {"budget_saving": 0, "personalized_cf": 0, "hybrid_ai": 0}
    incomplete_count = 0
    
    for scenario, results in all_results.items():
        summary = results.get("summary", {})
        winner = summary.get("overall_winner")
        eval_status = summary.get("evaluation_status", "unknown")
        
        if winner:
            overall_wins[winner] += 1
            print(f"\n{scenario.replace('_', ' ').title()}: Winner = {winner.replace('_', ' ').title()} (Status: {eval_status})")
        else:
            incomplete_count += 1
            print(f"\n{scenario.replace('_', ' ').title()}: INCOMPLETE (Status: {eval_status})")
    
    print(f"\nOVERALL RESULTS:")
    print(f"  Win counts: {overall_wins}")
    print(f"  Incomplete evaluations: {incomplete_count}/{len(all_results)}")
    
    # Only declare a champion if we have valid wins
    total_wins = sum(overall_wins.values())
    if total_wins > 0:
        print(f"  Champion: {max(overall_wins, key=overall_wins.get).replace('_', ' ').title()}")
    else:
        print(f"  Champion: NONE (all evaluations incomplete)")
    
    # Save combined results
    with open("evaluation_results_all_scenarios.json", 'w') as f:
        json.dump(all_results, f, indent=2)
    
    print(f"\n✓ All results saved to: evaluation_results_all_scenarios.json")
    print("="*60)


if __name__ == "__main__":
    import sys
    
    print("\n🎯 LLM-as-a-Judge Evaluation System")
    print("Following EvidentlyAI Methodology\n")
    
    # Check if scenario specified
    if len(sys.argv) > 1:
        scenario = sys.argv[1]
        
        # Special cases for running all warm or all cold scenarios
        if scenario == "--warm-start" or scenario == "-w":
            print("Running warm-start scenarios only...")
            if WARM_START_SCENARIOS:
                for ws_name in list(WARM_START_SCENARIOS.keys())[:5]:  # Run first 5
                    run_evaluation(ws_name)
            else:
                print("ERROR: No warm-start scenarios available")
                print("Run: python warm_start_scenarios.py to generate them")
        elif scenario == "--cold-start" or scenario == "-c":
            print("Running cold-start scenarios only...")
            for cold in ["budget_conscious", "health_focused", "new_user"]:
                run_evaluation(cold)
        else:
            run_evaluation(scenario)
    else:
        # Run all scenarios
        print("Running evaluation for all scenarios...")
        print("(Use: python test_llm_evaluation.py <scenario_name> for single scenario)")
        print("\nAvailable scenarios:")
        print("  ❄️  Cold-Start: budget_conscious, health_focused, new_user")
        if WARM_START_SCENARIOS:
            print(f"  🔥 Warm-Start: {', '.join(list(WARM_START_SCENARIOS.keys())[:5])}")
        print("\nQuick options:")
        print("  --warm-start (-w): Run first 5 warm-start scenarios only")
        print("  --cold-start (-c): Run all cold-start scenarios only\n")
        
        response = input("Run all scenarios? (y/n): ")
        if response.lower() == 'y':
            run_all_scenarios()
        else:
            # Run single warm-start scenario to demonstrate CF with purchase history
            if WARM_START_SCENARIOS:
                print("\nRunning single warm-start scenario to demonstrate CF with purchase history...")
                run_evaluation(list(WARM_START_SCENARIOS.keys())[0])
            else:
                print("\nRunning single cold-start scenario...")
                run_evaluation("budget_conscious")
