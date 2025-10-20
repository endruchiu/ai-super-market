"""
Quick Demo of LLM-as-a-Judge Evaluation System
Shows how the system evaluates the three recommendation models
"""

import json

print("\n" + "="*70)
print("  LLM-as-a-Judge Evaluation System Demo")
print("  Following EvidentlyAI Methodology")
print("="*70)

print("\n📚 SYSTEM OVERVIEW")
print("-" * 70)
print("""
This evaluation system uses OpenAI GPT-5 to scientifically compare three
recommendation engines:

1. 💙 Budget-Saving (Semantic Similarity)
   - Uses sentence-transformers for product similarity
   - Focuses on cost savings through similar but cheaper items

2. 💜 Personalized (Collaborative Filtering)
   - Uses TensorFlow/Keras with 32-dim embeddings
   - Learns from user purchase history (currently 15 users, 564 events)
   - Provides personalized recommendations based on shopping patterns

3. 💚 Hybrid AI (Blended Approach)
   - Combines 60% CF + 40% Semantic Similarity
   - Balances personalization with budget optimization
""")

print("\n🔬 EVALUATION METHODOLOGY")
print("-" * 70)
print("""
Following EvidentlyAI's LLM-as-a-Judge approach with two methods:

A. PAIRWISE COMPARISONS (3 head-to-head matchups)
   - Budget-Saving vs Personalized CF
   - Budget-Saving vs Hybrid AI
   - Personalized CF vs Hybrid AI
   
   Each comparison evaluates:
   • Relevance (1-10): Match to user needs and cart items
   • Savings (1-10): Realistic money savings
   • Practicality (1-10): Are these realistic substitutes?
   • User Experience (1-10): Would users actually use these?

B. CRITERIA-BASED SCORING (individual system evaluation)
   • Relevance: Match to preferences and cart
   • Savings: Money saved
   • Diversity: Variety of recommendations
   • Explanation Quality: Clarity of reasons
   • Feasibility: Realistic product swaps
   • Overall Score: Composite rating (0-10)
""")

print("\n🧪 TEST SCENARIOS")
print("-" * 70)
print("""
Three carefully designed scenarios test different aspects:

1. BUDGET-CONSCIOUS SHOPPER
   - Budget: $50
   - Cart: $102.98 (Premium peanut butter cake + ribeye steak)
   - Tests: Budget optimization, smart substitutions
   - Expected Winner: Budget-Saving or Hybrid
   
2. HEALTH-FOCUSED SHOPPER
   - Budget: $80
   - Cart: Organic items + one indulgent dessert ($91.94)
   - Tests: Balance of health preferences vs. budget
   - Expected Winner: Personalized CF or Hybrid

3. NEW USER (COLD START)
   - Budget: $40
   - Cart: $56.99 (Single expensive dessert item)
   - Tests: Cold start handling without purchase history
   - Expected Winner: Budget-Saving (CF has no history data)
""")

print("\n⚙️  HOW TO RUN EVALUATION")
print("-" * 70)
print("""
Prerequisites:
1. Set OpenAI API key: export OPENAI_API_KEY="sk-..."
   (Already configured ✅)

2. Ensure Flask app is running on http://localhost:5000
   (Run: python main.py)

Commands:

# Run single scenario evaluation
python test_llm_evaluation.py budget_conscious

# Run all three scenarios
python test_llm_evaluation.py
# (then type 'y' when prompted)

# Available scenarios:
# - budget_conscious
# - health_focused  
# - new_user
""")

print("\n📊 OUTPUT FILES")
print("-" * 70)
print("""
Each evaluation generates:

- evaluation_results_<scenario>.json
  Detailed results with scores, comparisons, and LLM reasoning

- evaluation_results_all_scenarios.json
  Combined results across all scenarios with overall champion

Console output includes:
- User profile (budget, cart, shopping style)
- Recommendation counts from each system
- Pairwise comparison winners
- Detailed criteria scores (0-10)
- Overall winner and best-for-specific-needs analysis
""")

print("\n📈 EXAMPLE OUTPUT")
print("-" * 70)

example_report = {
    "scenario": "Budget-Conscious Shopper",
    "user_profile": {
        "budget": "$50",
        "cart_total": "$102.98",
        "over_budget": "$52.98"
    },
    "pairwise_winners": {
        "Budget vs CF": "Hybrid AI",
        "Budget vs Hybrid": "Hybrid AI",
        "CF vs Hybrid": "Hybrid AI"
    },
    "criteria_scores": {
        "Budget-Saving": {
            "relevance": "8/10",
            "savings": "9/10",
            "diversity": "7/10",
            "explanation_quality": "8/10",
            "feasibility": "8/10",
            "overall": "8.2/10"
        },
        "Personalized-CF": {
            "relevance": "7/10",
            "savings": "7/10",
            "diversity": "8/10",
            "explanation_quality": "7/10",
            "feasibility": "7/10",
            "overall": "7.2/10"
        },
        "Hybrid-AI": {
            "relevance": "9/10",
            "savings": "8/10",
            "diversity": "8/10",
            "explanation_quality": "9/10",
            "feasibility": "9/10",
            "overall": "8.6/10"
        }
    },
    "overall_winner": "Hybrid AI",
    "best_for": {
        "savings": "Budget-Saving",
        "relevance": "Hybrid AI",
        "user_experience": "Hybrid AI"
    }
}

print(json.dumps(example_report, indent=2))

print("\n" + "="*70)
print("✨ Ready to run LLM-as-a-Judge evaluation!")
print("="*70)
print("\nTo start, run:")
print("  python test_llm_evaluation.py budget_conscious")
print("\nNote: Each full evaluation uses OpenAI API credits")
print("      (approximately 6 GPT-5 calls per scenario)")
print("="*70 + "\n")
