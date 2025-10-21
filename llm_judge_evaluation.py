"""
LLM-as-a-Judge Evaluation System
Following EvidentlyAI methodology to evaluate recommendation systems
"""

import json
import os
from openai import OpenAI

# the newest OpenAI model is "gpt-5" which was released August 7, 2025.
# do not change this unless explicitly requested by the user
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

def validate_api_key():
    """Validate OpenAI API key before starting evaluation."""
    if not OPENAI_API_KEY:
        raise ValueError(
            "OPENAI_API_KEY environment variable is not set. "
            "Please set it via: export OPENAI_API_KEY='sk-...' "
            "or configure it in Replit Secrets."
        )
    if not OPENAI_API_KEY.startswith('sk-'):
        raise ValueError(
            f"Invalid OPENAI_API_KEY format. Expected key starting with 'sk-', "
            f"got: '{OPENAI_API_KEY[:10]}...'"
        )

openai = OpenAI(api_key=OPENAI_API_KEY)


def pairwise_comparison(user_context, system_a_name, system_a_recs, system_b_name, system_b_recs):
    """
    Compare two recommendation systems using GPT-5 as judge.
    Returns winner and detailed scores.
    """
    
    prompt = f"""
TASK: Compare two grocery recommendation systems and determine which is better.

USER CONTEXT:
- Budget: ${user_context['budget']}
- Cart Total: ${user_context['cart_total']} (${user_context['over_budget']} over budget)
- Cart Items: {', '.join([item['title'] for item in user_context['cart_items']])}
- Shopping Style: {user_context.get('user_type', 'General shopper')}

SYSTEM A ({system_a_name}):
{json.dumps(system_a_recs, indent=2)}

SYSTEM B ({system_b_name}):
{json.dumps(system_b_recs, indent=2)}

EVALUATION CRITERIA:
1. Relevance (1-10): How well do recommendations match the user's needs and cart items?
2. Savings (1-10): How much money can the user realistically save?
3. Practicality (1-10): Are these realistic, practical substitutes the user would accept?
4. User Experience (1-10): Would users actually click "Replace" on these suggestions?

Respond with JSON in this exact format:
{{
  "winner": "A" or "B",
  "reasoning": "brief 2-3 sentence explanation",
  "scores": {{
    "relevance": {{"A": 0-10, "B": 0-10}},
    "savings": {{"A": 0-10, "B": 0-10}},
    "practicality": {{"A": 0-10, "B": 0-10}},
    "ux": {{"A": 0-10, "B": 0-10}}
  }}
}}
"""
    
    try:
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert evaluator of recommendation systems. Provide fair, objective assessments based on the criteria provided."
                },
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"}
        )
        
        result = json.loads(response.choices[0].message.content)
        return result
    
    except Exception as e:
        print(f"Error in pairwise comparison: {e}")
        return None


def criteria_evaluation(user_context, system_name, recommendations):
    """
    Evaluate a single recommendation system on specific criteria.
    Returns detailed scores and analysis.
    """
    
    prompt = f"""
TASK: Evaluate this grocery recommendation system's performance.

USER CONTEXT:
- Budget: ${user_context['budget']}
- Cart Total: ${user_context['cart_total']} (${user_context['over_budget']} over budget)
- Cart Items: {', '.join([item['title'] for item in user_context['cart_items']])}
- Shopping Style: {user_context.get('user_type', 'General shopper')}

SYSTEM: {system_name}
RECOMMENDATIONS:
{json.dumps(recommendations, indent=2)}

Evaluate on a scale of 1-10:
1. Relevance: Do recommendations match user preferences and cart items?
2. Savings: How much money does this realistically save?
3. Diversity: Are recommendations varied or too repetitive?
4. Explanation Quality: Are reasons clear, helpful, and convincing?
5. Substitution Feasibility: Are these realistic product swaps the user would accept?

Respond with JSON in this exact format:
{{
  "relevance": 0-10,
  "savings": 0-10,
  "diversity": 0-10,
  "explanation_quality": 0-10,
  "feasibility": 0-10,
  "overall_score": 0-10,
  "reasoning": "brief 2-3 sentence summary"
}}
"""
    
    try:
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert evaluator of recommendation systems. Provide detailed, objective assessments."
                },
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"}
        )
        
        result = json.loads(response.choices[0].message.content)
        return result
    
    except Exception as e:
        print(f"Error in criteria evaluation: {e}")
        return None


def evaluate_all_systems(user_context, budget_recs, cf_recs, hybrid_recs):
    """
    Run complete evaluation comparing all 3 systems.
    Returns comprehensive comparison report.
    """
    
    # Validate API key before starting
    validate_api_key()
    
    print("\n" + "="*60)
    print("LLM-as-a-Judge Evaluation")
    print("="*60)
    
    results = {
        "user_context": user_context,
        "pairwise_comparisons": {},
        "criteria_scores": {},
        "summary": {}
    }
    
    # Pairwise comparisons
    print("\n[1/3] Running pairwise comparisons...")
    
    # Budget vs CF
    print("  - Budget-Saving vs Personalized CF...")
    comparison_1 = pairwise_comparison(
        user_context,
        "Budget-Saving (Semantic)",
        budget_recs,
        "Personalized (CF)",
        cf_recs
    )
    if comparison_1:
        results["pairwise_comparisons"]["budget_vs_cf"] = comparison_1
    
    # Budget vs Hybrid
    print("  - Budget-Saving vs Hybrid AI...")
    comparison_2 = pairwise_comparison(
        user_context,
        "Budget-Saving (Semantic)",
        budget_recs,
        "Hybrid AI (60% CF + 40% Semantic)",
        hybrid_recs
    )
    if comparison_2:
        results["pairwise_comparisons"]["budget_vs_hybrid"] = comparison_2
    
    # CF vs Hybrid
    print("  - Personalized CF vs Hybrid AI...")
    comparison_3 = pairwise_comparison(
        user_context,
        "Personalized (CF)",
        cf_recs,
        "Hybrid AI (60% CF + 40% Semantic)",
        hybrid_recs
    )
    if comparison_3:
        results["pairwise_comparisons"]["cf_vs_hybrid"] = comparison_3
    
    # Criteria-based evaluation
    print("\n[2/3] Running criteria-based evaluations...")
    
    print("  - Evaluating Budget-Saving system...")
    budget_scores = criteria_evaluation(user_context, "Budget-Saving (Semantic)", budget_recs)
    if budget_scores:
        results["criteria_scores"]["budget_saving"] = budget_scores
    
    print("  - Evaluating Personalized CF system...")
    cf_scores = criteria_evaluation(user_context, "Personalized (CF)", cf_recs)
    if cf_scores:
        results["criteria_scores"]["personalized_cf"] = cf_scores
    
    print("  - Evaluating Hybrid AI system...")
    hybrid_scores = criteria_evaluation(user_context, "Hybrid AI", hybrid_recs)
    if hybrid_scores:
        results["criteria_scores"]["hybrid_ai"] = hybrid_scores
    
    # Generate summary
    print("\n[3/3] Generating summary...")
    results["summary"] = generate_summary(results)
    
    print("\n✓ Evaluation complete!")
    return results


def generate_summary(results):
    """
    Generate executive summary from evaluation results.
    Detects incomplete evaluations and avoids fabricating winners.
    """
    
    summary = {
        "evaluation_status": "incomplete",
        "overall_winner": None,
        "best_for_savings": None,
        "best_for_relevance": None,
        "best_for_ux": None,
        "key_insights": [],
        "win_counts": {"budget_saving": 0, "personalized_cf": 0, "hybrid_ai": 0}
    }
    
    # Check if we have any pairwise comparison data
    pairwise = results.get("pairwise_comparisons", {})
    has_pairwise_data = len(pairwise) > 0
    
    # Check if we have any criteria scores
    criteria = results.get("criteria_scores", {})
    has_criteria_data = len(criteria) > 0
    
    # If no evaluation data at all, return incomplete status
    if not has_pairwise_data and not has_criteria_data:
        summary["key_insights"].append("No evaluation data collected - check OpenAI API key and quota")
        return summary
    
    # Count wins from pairwise comparisons (only if we have data)
    wins = {"budget_saving": 0, "personalized_cf": 0, "hybrid_ai": 0}
    
    if "budget_vs_cf" in pairwise:
        winner = pairwise["budget_vs_cf"]["winner"]
        if winner == "A":
            wins["budget_saving"] += 1
        else:
            wins["personalized_cf"] += 1
    
    if "budget_vs_hybrid" in pairwise:
        winner = pairwise["budget_vs_hybrid"]["winner"]
        if winner == "A":
            wins["budget_saving"] += 1
        else:
            wins["hybrid_ai"] += 1
    
    if "cf_vs_hybrid" in pairwise:
        winner = pairwise["cf_vs_hybrid"]["winner"]
        if winner == "A":
            wins["personalized_cf"] += 1
        else:
            wins["hybrid_ai"] += 1
    
    summary["win_counts"] = wins
    
    # Only determine overall winner if we have at least some wins
    total_wins = sum(wins.values())
    if total_wins > 0:
        summary["overall_winner"] = max(wins, key=wins.get)
        summary["evaluation_status"] = "partial" if total_wins < 3 else "complete"
    
    # Best for specific criteria (only if we have criteria data)
    if has_criteria_data:
        # Best for savings
        savings_scores = {
            "budget_saving": criteria.get("budget_saving", {}).get("savings", 0),
            "personalized_cf": criteria.get("personalized_cf", {}).get("savings", 0),
            "hybrid_ai": criteria.get("hybrid_ai", {}).get("savings", 0)
        }
        # Only set winner if at least one score > 0
        if max(savings_scores.values()) > 0:
            summary["best_for_savings"] = max(savings_scores, key=savings_scores.get)
        
        # Best for relevance
        relevance_scores = {
            "budget_saving": criteria.get("budget_saving", {}).get("relevance", 0),
            "personalized_cf": criteria.get("personalized_cf", {}).get("relevance", 0),
            "hybrid_ai": criteria.get("hybrid_ai", {}).get("relevance", 0)
        }
        if max(relevance_scores.values()) > 0:
            summary["best_for_relevance"] = max(relevance_scores, key=relevance_scores.get)
        
        # Best for UX (explanation quality + feasibility)
        ux_scores = {
            "budget_saving": (criteria.get("budget_saving", {}).get("explanation_quality", 0) + 
                            criteria.get("budget_saving", {}).get("feasibility", 0)) / 2,
            "personalized_cf": (criteria.get("personalized_cf", {}).get("explanation_quality", 0) + 
                              criteria.get("personalized_cf", {}).get("feasibility", 0)) / 2,
            "hybrid_ai": (criteria.get("hybrid_ai", {}).get("explanation_quality", 0) + 
                        criteria.get("hybrid_ai", {}).get("feasibility", 0)) / 2
        }
        if max(ux_scores.values()) > 0:
            summary["best_for_ux"] = max(ux_scores, key=ux_scores.get)
    
    return summary


def print_report(results):
    """
    Print formatted evaluation report.
    Handles incomplete evaluations gracefully.
    """
    
    print("\n" + "="*60)
    print("EVALUATION REPORT")
    print("="*60)
    
    # User context
    ctx = results["user_context"]
    print(f"\nUSER PROFILE:")
    print(f"  Type: {ctx.get('user_type', 'General')}")
    print(f"  Budget: ${ctx['budget']}")
    print(f"  Cart Total: ${ctx['cart_total']} (${ctx['over_budget']} over)")
    print(f"  Items: {len(ctx['cart_items'])}")
    
    # Summary
    summary = results["summary"]
    eval_status = summary.get("evaluation_status", "unknown")
    
    # Show evaluation status
    print(f"\nEVALUATION STATUS: {eval_status.upper()}")
    
    # Show overall winner (if available)
    if summary.get("overall_winner"):
        print(f"\nOVERALL WINNER: {summary['overall_winner'].replace('_', ' ').title()}")
        print(f"  Win counts: {summary['win_counts']}")
    else:
        print(f"\nOVERALL WINNER: INCOMPLETE")
        print(f"  Win counts: {summary.get('win_counts', {})}")
        print(f"  ⚠️  No valid evaluation data - check OpenAI API key and quota")
    
    print(f"\nBEST FOR SPECIFIC NEEDS:")
    savings_winner = summary.get('best_for_savings', 'N/A')
    savings_winner = savings_winner.replace('_', ' ').title() if savings_winner != 'N/A' and savings_winner is not None else 'N/A'
    print(f"  Savings: {savings_winner}")
    
    relevance_winner = summary.get('best_for_relevance', 'N/A')
    relevance_winner = relevance_winner.replace('_', ' ').title() if relevance_winner != 'N/A' and relevance_winner is not None else 'N/A'
    print(f"  Relevance: {relevance_winner}")
    
    ux_winner = summary.get('best_for_ux', 'N/A')
    ux_winner = ux_winner.replace('_', ' ').title() if ux_winner != 'N/A' and ux_winner is not None else 'N/A'
    print(f"  User Experience: {ux_winner}")
    
    # Detailed scores
    print(f"\nDETAILED CRITERIA SCORES:")
    criteria = results.get("criteria_scores", {})
    
    for system_name, scores in criteria.items():
        print(f"\n  {system_name.replace('_', ' ').title()}:")
        print(f"    Relevance: {scores.get('relevance', 0)}/10")
        print(f"    Savings: {scores.get('savings', 0)}/10")
        print(f"    Diversity: {scores.get('diversity', 0)}/10")
        print(f"    Explanation Quality: {scores.get('explanation_quality', 0)}/10")
        print(f"    Feasibility: {scores.get('feasibility', 0)}/10")
        print(f"    Overall: {scores.get('overall_score', 0)}/10")
        print(f"    Reasoning: {scores.get('reasoning', 'N/A')}")
    
    print("\n" + "="*60)


if __name__ == "__main__":
    # Example test
    print("LLM-as-a-Judge Evaluation System")
    print("Following EvidentlyAI methodology")
    print("\nNote: Run test_llm_evaluation.py for full evaluation")
