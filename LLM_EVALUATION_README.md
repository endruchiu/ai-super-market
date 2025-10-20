# LLM-as-a-Judge Evaluation System

This evaluation system uses OpenAI GPT-5 to scientifically compare the three recommendation engines following the **EvidentlyAI methodology**.

## Overview

The system evaluates three recommendation engines:
1. **Budget-Saving** - Semantic similarity-based (Hugging Face sentence-transformers)
2. **Personalized CF** - Collaborative Filtering (Keras 32-dim embeddings)
3. **Hybrid AI** - Blended (60% CF + 40% Semantic)

## Methodology

Following EvidentlyAI's LLM-as-a-Judge approach:

### 1. Pairwise Comparisons
- Budget vs CF
- Budget vs Hybrid
- CF vs Hybrid

Each comparison evaluates:
- **Relevance** (1-10): Match to user needs and cart items
- **Savings** (1-10): Realistic money savings
- **Practicality** (1-10): Realistic substitutes
- **User Experience** (1-10): Would users click "Replace"?

### 2. Criteria-Based Scoring
Individual evaluation of each system:
- **Relevance**: Match to preferences and cart
- **Savings**: Money saved
- **Diversity**: Variety of recommendations
- **Explanation Quality**: Clarity of reasons
- **Feasibility**: Realistic product swaps
- **Overall Score**: Composite rating

## Test Scenarios

### Budget-Conscious Shopper
- Budget: $50
- Cart: Premium items totaling $102.98
- Tests: Budget optimization, smart substitutions

### Health-Focused Shopper
- Budget: $80
- Cart: Organic items + one indulgent dessert
- Tests: Balance of health vs. budget

### New User (Cold Start)
- Budget: $40
- Cart: Single expensive item
- Tests: Cold start handling, general recommendations

## Usage

### Run Single Scenario
```bash
python test_llm_evaluation.py budget_conscious
```

Available scenarios:
- `budget_conscious`
- `health_focused`
- `new_user`

### Run All Scenarios
```bash
python test_llm_evaluation.py
# Then type 'y' when prompted
```

## Output

### Evaluation Results
Each run generates:
- `evaluation_results_<scenario>.json` - Detailed results
- Console report with winner and scores

### Combined Results
Running all scenarios generates:
- `evaluation_results_all_scenarios.json` - Full comparison
- Overall champion across all scenarios

## Example Report

```
============================================================
EVALUATION REPORT
============================================================

USER PROFILE:
  Type: Budget-conscious family shopper
  Budget: $50.0
  Cart Total: $102.98 ($52.98 over)
  Items: 2

OVERALL WINNER: Hybrid Ai
  Win counts: {'budget_saving': 0, 'personalized_cf': 1, 'hybrid_ai': 2}

BEST FOR SPECIFIC NEEDS:
  Savings: Budget Saving
  Relevance: Hybrid Ai
  User Experience: Hybrid Ai

DETAILED CRITERIA SCORES:
  Budget Saving:
    Relevance: 8/10
    Savings: 9/10
    Diversity: 7/10
    Explanation Quality: 8/10
    Feasibility: 8/10
    Overall: 8.2/10
```

## Quickstart Guide

### 1. Set Up OpenAI API Key
```bash
export OPENAI_API_KEY="sk-..."
```
Or use Replit Secrets to store `OPENAI_API_KEY`.

### 2. Install Dependencies
Install all required packages:
```bash
pip install -r requirements.txt
```

Or install manually if needed:
```bash
pip install flask flask-sqlalchemy pandas openai requests sentence-transformers tensorflow-cpu
```

### 3. Start the Flask API
The evaluation system requires the Flask app running:
```bash
python main.py
```
Wait for the server to start on `http://localhost:5000`

### 4. Run the Demo (Optional)
See system overview without using API credits:
```bash
python demo_llm_evaluation.py
```

### 5. Run Evaluation
Single scenario:
```bash
python test_llm_evaluation.py budget_conscious
```

All scenarios (uses ~18 GPT-5 API calls):
```bash
python test_llm_evaluation.py
# Type 'y' when prompted
```

## Prerequisites

- **OpenAI API Key**: Set via environment variable or Replit Secrets
- **Flask App Running**: Required on `http://localhost:5000`
- **API Endpoints**: `/api/budget/recommendations`, `/api/cf/recommendations`, `/api/blended/recommendations`

## Files

- `llm_judge_evaluation.py` - Core evaluation engine with GPT-5 integration
- `test_llm_evaluation.py` - Test runner with 3 scenarios
- `demo_llm_evaluation.py` - Demonstration script (no API calls)
- `LLM_EVALUATION_README.md` - This documentation

## Technical Details

### GPT-5 Prompts
Prompts are engineered to:
- Provide full user context (budget, cart, shopping style)
- Request JSON-formatted responses
- Enforce objective, criteria-based scoring
- Generate actionable insights

### Error Handling
- Gracefully handles OpenAI API errors
- Null-safe report generation
- Continues evaluation even if individual comparisons fail

### Cold Start Testing
The "new_user" scenario tests how each system handles:
- Users with no purchase history
- Limited cart data
- General recommendations vs. personalized

## Limitations

- Requires OpenAI API credits
- GPT-5 model must be available
- Evaluation quality depends on prompt engineering
- Real user testing still recommended

## Troubleshooting

### Flask Server Not Running
```bash
# Error: "Connection refused" or "Failed to connect"
# Solution: Start the Flask app
python main.py
# Wait for: "Running on http://127.0.0.1:5000"
```

### Missing Dependencies
```bash
# Error: "ModuleNotFoundError: No module named 'openai'"
# Solution: Install requirements
pip install -r requirements.txt
```

### OpenAI API Errors
```bash
# Error: "OPENAI_API_KEY environment variable is not set"
# Solution: Set the API key
export OPENAI_API_KEY="sk-..."

# Error: "Invalid API key" or "Rate limit exceeded"
# Solution: Check your OpenAI account has credits and valid key
```

### Empty Recommendations
```bash
# Error: Recommendations come back as []
# Solution: Ensure you have purchase history for CF testing
# Try the "budget_conscious" scenario first (works without history)
```

## Next Steps

1. **Optimize Prompts**: Fine-tune evaluation criteria
2. **Add More Scenarios**: Test edge cases
3. **Human Validation**: Compare LLM judgments with real user feedback
4. **A/B Testing**: Deploy winner to production
5. **Continuous Monitoring**: Re-evaluate as recommendation engines improve
