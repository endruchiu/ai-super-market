"""
Run LLM Evaluation on Demo Scenarios
Gets REAL scores from GPT-5 for baseline models (no Elastic Net improvements yet)
"""

import json
import requests
from llm_judge_evaluation import evaluate_all_systems, print_report

BASE_URL = "http://localhost:5000"

def load_demo_scenarios():
    """Load pre-generated demo scenarios."""
    with open('demo_evaluation_scenarios.json', 'r') as f:
        data = json.load(f)
    return data['scenarios']

def get_recommendations_for_cart(cart, budget, session_id=None):
    """Get recommendations from all 3 systems."""
    payload = {
        "cart": cart,
        "budget": budget
    }
    
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
        else:
            print(f"  ⚠️  Budget-Saving API error: {response.status_code}")
        
        # Personalized CF recommendations
        response = requests.post(f"{BASE_URL}/api/cf/recommendations", json=payload)
        if response.status_code == 200:
            data = response.json()
            results["personalized_cf"] = data.get("suggestions", [])
        else:
            print(f"  ⚠️  CF API error: {response.status_code}")
        
        # Hybrid AI recommendations
        response = requests.post(f"{BASE_URL}/api/blended/recommendations", json=payload)
        if response.status_code == 200:
            data = response.json()
            results["hybrid_ai"] = data.get("suggestions", [])
        else:
            print(f"  ⚠️  Hybrid API error: {response.status_code}")
    
    except Exception as e:
        print(f"  ❌ Error getting recommendations: {e}")
    
    return results

def run_demo_evaluation(scenario):
    """Run LLM evaluation for one demo scenario."""
    
    print("\n" + "="*70)
    print(f"📊 EVALUATING: {scenario['name']}")
    print("="*70)
    
    print(f"\nUser: {scenario['session_id']}")
    print(f"Budget: ${scenario['budget']:.2f}")
    print(f"Cart Total: ${scenario['cart_total']:.2f} (Over by ${scenario['over_budget']:.2f})")
    print(f"Items in cart:")
    for item in scenario['cart']:
        print(f"  - {item['title'][:60]} (${item['price']:.2f})")
    
    # Get recommendations from all systems
    print(f"\n🔍 Fetching recommendations from all 3 systems...")
    recommendations = get_recommendations_for_cart(
        scenario['cart'], 
        scenario['budget'],
        session_id=scenario.get('session_id')
    )
    
    print(f"  ✓ Budget-Saving: {len(recommendations['budget_saving'])} suggestions")
    print(f"  ✓ Personalized CF: {len(recommendations['personalized_cf'])} suggestions")
    print(f"  ✓ Hybrid AI: {len(recommendations['hybrid_ai'])} suggestions")
    
    # Prepare user context
    user_context = {
        "user_type": scenario['user_type'],
        "budget": scenario['budget'],
        "cart_total": scenario['cart_total'],
        "over_budget": scenario['over_budget'],
        "cart_items": scenario['cart'],
        "is_warm_start": True,
        "session_id": scenario.get('session_id')
    }
    
    # Run LLM evaluation (REAL GPT-5 scores)
    print(f"\n🤖 Running GPT-5 evaluation (this may take 30-60 seconds)...")
    results = evaluate_all_systems(
        user_context,
        recommendations["budget_saving"],
        recommendations["personalized_cf"],
        recommendations["hybrid_ai"]
    )
    
    # Print report
    print_report(results)
    
    # Save results
    output_file = f"evaluation_results_demo_{scenario['name']}.json"
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n✅ Results saved to: {output_file}")
    
    return results

def run_all_demo_evaluations():
    """Run evaluation for all demo scenarios."""
    
    print("\n" + "="*70)
    print("🎯 BASELINE MODEL EVALUATION")
    print("="*70)
    print("\nMethodology: EvidentlyAI LLM-as-a-Judge")
    print("Model: OpenAI GPT-5")
    print("Status: Baseline (NO Elastic Net, NO BPR, NO Bandits)")
    print("="*70)
    
    scenarios = load_demo_scenarios()
    all_results = {}
    
    for i, scenario in enumerate(scenarios, 1):
        print(f"\n\n{'='*70}")
        print(f"SCENARIO {i} of {len(scenarios)}")
        print(f"{'='*70}")
        
        try:
            results = run_demo_evaluation(scenario)
            all_results[scenario['name']] = results
        except Exception as e:
            print(f"\n❌ Error evaluating {scenario['name']}: {e}")
            import traceback
            traceback.print_exc()
            continue
    
    # Generate combined summary
    print("\n\n" + "="*70)
    print("📊 COMBINED BASELINE SUMMARY")
    print("="*70)
    
    overall_wins = {"budget_saving": 0, "personalized_cf": 0, "hybrid_ai": 0}
    overall_scores = {"budget_saving": [], "personalized_cf": [], "hybrid_ai": []}
    
    for scenario_name, results in all_results.items():
        summary = results.get("summary", {})
        winner = summary.get("overall_winner")
        
        # Get criteria scores
        for system in ["budget_saving", "personalized_cf", "hybrid_ai"]:
            criteria = results.get("criteria_based", {}).get(system, {})
            overall_score = criteria.get("overall", 0)
            overall_scores[system].append(overall_score)
        
        if winner:
            overall_wins[winner] += 1
            print(f"\n✓ {scenario_name}: Winner = {winner.replace('_', ' ').title()}")
    
    # Calculate averages
    print(f"\n\n{'='*70}")
    print("FINAL BASELINE SCORES (Averaged Across All Scenarios)")
    print(f"{'='*70}\n")
    
    for system in ["budget_saving", "personalized_cf", "hybrid_ai"]:
        scores = overall_scores[system]
        avg_score = sum(scores) / len(scores) if scores else 0
        wins = overall_wins[system]
        
        system_name = system.replace('_', ' ').title()
        print(f"{system_name}:")
        print(f"  Average Score: {avg_score:.1f}/10")
        print(f"  Wins: {wins}/{len(all_results)}")
        print(f"  Individual Scores: {scores}")
        print()
    
    # Save combined results
    with open("evaluation_results_demo_combined.json", 'w') as f:
        json.dump({
            'summary': {
                'overall_wins': overall_wins,
                'overall_scores': overall_scores,
                'average_scores': {
                    system: sum(scores) / len(scores) if scores else 0
                    for system, scores in overall_scores.items()
                }
            },
            'individual_results': all_results
        }, f, indent=2)
    
    print(f"\n✅ Combined results saved to: evaluation_results_demo_combined.json")
    print("="*70)

if __name__ == "__main__":
    import sys
    
    print("\n🎯 Demo Scenario LLM Evaluation")
    print("Using realistic scenarios with expensive items\n")
    
    # Check if specific scenario requested
    if len(sys.argv) > 1:
        scenario_name = sys.argv[1]
        scenarios = load_demo_scenarios()
        scenario = next((s for s in scenarios if s['name'] == scenario_name), None)
        
        if scenario:
            run_demo_evaluation(scenario)
        else:
            print(f"ERROR: Scenario '{scenario_name}' not found")
            print(f"Available: {[s['name'] for s in scenarios]}")
    else:
        # Run all scenarios
        run_all_demo_evaluations()
