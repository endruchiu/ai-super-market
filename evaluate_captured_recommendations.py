"""
Evaluate captured recommendations from live web session
Uses both traditional metrics and LLM-as-a-Judge (GPT-5)
"""

import json
from llm_judge_evaluation import evaluate_all_systems, print_report
from traditional_evaluation_metrics import compare_recommendation_systems

def load_captured_recommendations(filename='captured_recommendations.json'):
    """Load recommendations captured from browser console"""
    with open(filename, 'r') as f:
        data = json.load(f)
    return data

def run_complete_evaluation():
    """Run both traditional and LLM evaluations on captured data"""
    
    print("\n" + "="*70)
    print("🎯 COMPLETE EVALUATION OF CAPTURED RECOMMENDATIONS")
    print("="*70)
    print("\nData Source: Live web session with real purchase history")
    print("="*70)
    
    # Load captured data
    data = load_captured_recommendations()
    
    user_context = data['user_context']
    budget_saving = data['budget_saving']
    personalized_cf = data['personalized_cf']
    hybrid_ai = data['hybrid_ai']
    
    cart = user_context['cart_items']
    budget = user_context['budget']
    cart_total = user_context['cart_total']
    
    print(f"\n📊 User Context:")
    print(f"  Budget: ${budget:.2f}")
    print(f"  Cart Total: ${cart_total:.2f}")
    print(f"  Over Budget: ${user_context['over_budget']:.2f}")
    print(f"  Cart Items: {len(cart)}")
    for item in cart:
        print(f"    - {item['title'][:50]}... ${item['price']:.2f}")
    
    print(f"\n🤖 Recommendations Captured:")
    print(f"  Budget-Saving: {len(budget_saving)} recommendations")
    print(f"  Personalized CF: {len(personalized_cf)} recommendations")
    print(f"  Hybrid AI: {len(hybrid_ai)} recommendations")
    
    # ==================================================================
    # PART 1: TRADITIONAL EVALUATION
    # ==================================================================
    print("\n" + "="*70)
    print("PART 1: TRADITIONAL EVALUATION (Objective Metrics)")
    print("="*70)
    
    comparison_df = compare_recommendation_systems(
        budget_saving,
        personalized_cf,
        hybrid_ai,
        cart
    )
    
    print("\n" + comparison_df.to_string(index=False))
    
    # Save traditional results
    comparison_df.to_csv('live_session_traditional_results.csv', index=False)
    print(f"\n✓ Traditional results saved to: live_session_traditional_results.csv")
    
    # ==================================================================
    # PART 2: LLM EVALUATION (GPT-5)
    # ==================================================================
    print("\n" + "="*70)
    print("PART 2: LLM-AS-A-JUDGE EVALUATION (GPT-5)")
    print("="*70)
    
    user_context_for_llm = {
        "user_type": "Active shopper with real purchase history (completed 1 order, building shopping patterns)",
        "budget": budget,
        "cart_total": cart_total,
        "over_budget": cart_total - budget,
        "cart_items": cart
    }
    
    try:
        evaluation_results = evaluate_all_systems(
            user_context_for_llm,
            budget_saving,
            personalized_cf,
            hybrid_ai
        )
        
        print_report(evaluation_results)
        
        # Save LLM results
        with open('live_session_llm_results.json', 'w') as f:
            json.dump(evaluation_results, f, indent=2)
        
        print(f"\n✓ LLM results saved to: live_session_llm_results.json")
        
        # ==================================================================
        # FINAL COMPARISON
        # ==================================================================
        print("\n" + "="*70)
        print("📈 FINAL SCORES COMPARISON")
        print("="*70)
        
        print(f"\n🔢 Traditional Metrics:")
        print(f"\n{'System':<20} {'Recs':<8} {'Savings':<12} {'Diversity':<12} {'Category Match':<15}")
        print("-"*70)
        
        for _, row in comparison_df.iterrows():
            sys_name = row['System']
            print(f"{sys_name:<20} {row['Recommendations']:<8} ${row['Total Savings ($)']:<11} {row['Diversity Score']:<12.2f} {row['Category Match']:<15.2f}")
        
        print(f"\n🤖 LLM Scores (GPT-5, 0-10 scale):")
        criteria = evaluation_results.get("criteria_scores", {})
        
        print(f"\n{'System':<20} {'Relevance':<12} {'Savings':<12} {'Diversity':<12} {'Feasibility':<12} {'Overall':<10}")
        print("-"*70)
        
        for system in ["budget_saving", "personalized_cf", "hybrid_ai"]:
            scores = criteria.get(system, {})
            sys_name = system.replace('_', ' ').title()
            print(f"{sys_name:<20} {scores.get('relevance', 0):>4}/10      {scores.get('savings', 0):>4}/10      {scores.get('diversity', 0):>4}/10      {scores.get('feasibility', 0):>4}/10      {scores.get('overall_score', 0):>4}/10")
        
        print(f"\n🏆 Winners:")
        print(f"  Traditional: {comparison_df.iloc[0]['System']} ({comparison_df.iloc[0]['Total Savings ($)']} total savings)")
        print(f"  LLM: {evaluation_results['summary'].get('overall_winner', 'N/A').replace('_', ' ').title()}")
        
        # Check if we achieved 7-8/10 goal
        print(f"\n🎯 Goal Achievement (7-8/10 LLM scores):")
        for system in ["personalized_cf", "hybrid_ai"]:
            scores = criteria.get(system, {})
            overall = scores.get('overall_score', 0)
            sys_name = system.replace('_', ' ').title()
            if overall >= 7:
                print(f"  ✅ {sys_name}: {overall}/10 - GOAL ACHIEVED!")
            elif overall >= 5:
                print(f"  ⚠️  {sys_name}: {overall}/10 - Close! Needs minor improvement")
            else:
                print(f"  ❌ {sys_name}: {overall}/10 - Needs improvement")
        
    except Exception as e:
        print(f"\n❌ LLM Evaluation failed: {e}")
        print("(Traditional metrics still available)")
    
    print("\n" + "="*70)
    print("✅ EVALUATION COMPLETE!")
    print("="*70)
    print("\nResults saved:")
    print("  - live_session_traditional_results.csv (Traditional metrics)")
    print("  - live_session_llm_results.json (GPT-5 scores)")
    print("  - captured_recommendations.json (Raw recommendation data)")
    print("="*70 + "\n")


if __name__ == "__main__":
    run_complete_evaluation()
