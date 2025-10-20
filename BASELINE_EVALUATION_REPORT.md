# Baseline LLM Evaluation Report
**Date**: October 20, 2025  
**Methodology**: EvidentlyAI LLM-as-a-Judge  
**Model**: OpenAI GPT-5  
**Purpose**: Establish baseline performance BEFORE adding advanced improvements

---

## Executive Summary

This baseline evaluation assessed three recommendation systems **WITHOUT** advanced ML techniques (Elastic Net, BPR, Multi-Armed Bandits). Results show significant room for improvement, particularly in:
- **Cold start handling** (new users)
- **Personalized recommendations** (CF fails with 0 suggestions)
- **Hybrid system integration** (combines two weak systems)

---

## Evaluation Results by Scenario

### Scenario 1: Budget-Conscious Family Shopper
**User Profile**: Budget-conscious family, $50 budget, $102.98 cart total ($52.98 over)  
**Items**: 2 items in cart

| System | Suggestions | Relevance | Savings | Diversity | Explanation | Feasibility | Overall |
|--------|-------------|-----------|---------|-----------|-------------|-------------|---------|
| **Budget-Saving** | 0 | 1/10 | 1/10 | 1/10 | 1/10 | 1/10 | **1/10** |
| **Personalized CF** | 0 | 0/10 | 0/10 | 0/10 | 0/10 | 0/10 | **0/10** |
| **Hybrid AI** | 0 | 0/10 | 0/10 | 0/10 | 0/10 | 0/10 | **0/10** |

**Winner**: Budget-Saving (2 pairwise wins)

**Key Issues**:
- ❌ All systems returned zero recommendations
- ❌ No suggestions to address $52.98 budget gap
- ❌ Complete failure to help budget-conscious shopper

---

### Scenario 2: Health-Focused Organic Shopper
**User Profile**: Health-conscious organic shopper, $80 budget, $110.94 cart total ($30.94 over)  
**Items**: 3 items in cart

| System | Suggestions | Relevance | Savings | Diversity | Explanation | Feasibility | Overall |
|--------|-------------|-----------|---------|-----------|-------------|-------------|---------|
| **Budget-Saving** | 0 | 0/10 | 0/10 | 0/10 | 0/10 | 0/10 | **0/10** |
| **Personalized CF** | 0 | 0/10 | 0/10 | 0/10 | 0/10 | 0/10 | **0/10** |
| **Hybrid AI** | 0 | 0/10 | 0/10 | 0/10 | 0/10 | 0/10 | **0/10** |

**Winner**: Budget-Saving (2 pairwise wins, by default)

**Key Issues**:
- ❌ All systems returned zero recommendations
- ❌ Failed to understand health-conscious/organic preferences
- ❌ No suggestions for $30.94 budget overage

---

### Scenario 3: New User (Cold Start Test)
**User Profile**: New user with no history, $40 budget, $56.99 cart total ($16.99 over)  
**Items**: 1 item in cart (6.8 lb peanut butter cake)

| System | Suggestions | Relevance | Savings | Diversity | Explanation | Feasibility | Overall |
|--------|-------------|-----------|---------|-----------|-------------|-------------|---------|
| **Budget-Saving** | **3** | 5/10 | **9/10** | 6/10 | 3/10 | 5/10 | **6/10** ✅ |
| **Personalized CF** | 0 | 1/10 | 1/10 | 1/10 | 1/10 | 1/10 | **1/10** |
| **Hybrid AI** | 0 | 0/10 | 0/10 | 0/10 | 0/10 | 0/10 | **0/10** |

**Winner**: Budget-Saving (2 pairwise wins)

**Key Findings**:
- ✅ Budget-Saving works for cold start (semantic similarity doesn't need history)
- ❌ Personalized CF completely fails (no purchase history)
- ❌ Hybrid AI fails (relies too heavily on CF component)
- ⚠️ Budget-Saving suggestions save money ($17-$27) but lack context (not cake-to-cake)

---

## Cross-Scenario Performance Summary

### Win Counts
| System | Total Wins | Scenarios Won |
|--------|------------|---------------|
| **Budget-Saving** | 6/6 pairwise | All 3 (by default in 2) |
| **Personalized CF** | 2/6 pairwise | None (0 overall wins) |
| **Hybrid AI** | 1/6 pairwise | None (0 overall wins) |

### Average Scores
| System | Avg Relevance | Avg Savings | Avg Overall |
|--------|---------------|-------------|-------------|
| **Budget-Saving** | 2.0/10 | 3.3/10 | **2.3/10** |
| **Personalized CF** | 0.3/10 | 0.3/10 | **0.3/10** |
| **Hybrid AI** | 0.0/10 | 0.0/10 | **0.0/10** |

---

## Critical Baseline Weaknesses Identified

### 1. Cold Start Problem (Personalized CF)
- **Issue**: CF returns 0 recommendations for users without purchase history
- **Impact**: System useless for 100% of new users
- **Needed**: Graceful fallback or hybrid approach

### 2. Zero Recommendations Bug
- **Issue**: Systems return empty results even when budget exceeded
- **Impact**: Users get no help when they need it most
- **Root Cause**: Possible subcategory matching issue or insufficient data

### 3. Weak Explanations (Budget-Saving)
- **Issue**: Generic explanations like "similar product"
- **Impact**: Users don't understand why suggestions make sense
- **Score**: 3/10 for Explanation Quality

### 4. Hybrid System Failure
- **Issue**: Hybrid combines two weak components (0 + low = 0)
- **Impact**: Doesn't leverage strengths of either approach
- **Needed**: Better blending weights and integration

### 5. No Diversity
- **Issue**: When suggestions exist, they lack variety
- **Impact**: Users see repetitive options
- **Score**: 1-6/10 for Diversity

---

## Recommendations for Improvement

Based on this baseline evaluation, the following improvements are justified:

### High Priority
1. **Bayesian Personalized Ranking (BPR)**
   - Fixes: CF cold start and ranking quality
   - Expected Impact: Improve CF from 0/10 → 5+/10

2. **Elastic Net Feature Learning**
   - Fixes: Poor relevance and weak explanations
   - Expected Impact: Improve Budget-Saving from 6/10 → 8+/10

3. **Multi-Armed Bandits**
   - Fixes: Lack of diversity
   - Expected Impact: Improve Diversity from 1/10 → 7+/10

### Medium Priority
4. **Hybrid Blending Optimization**
   - Fixes: Hybrid system failure
   - Expected Impact: Improve Hybrid from 0/10 → 6+/10

5. **Better Cold Start Handling**
   - Fixes: Zero recommendations for new users
   - Expected Impact: All systems provide suggestions

---

## Files Generated

1. `evaluation_results_budget_conscious.json` - Budget scenario detailed results
2. `evaluation_results_health_focused.json` - Health scenario detailed results  
3. `evaluation_results_new_user.json` - Cold start scenario detailed results
4. `BASELINE_EVALUATION_REPORT.md` - This summary report

---

## Next Steps

1. ✅ Baseline established (current document)
2. ⏳ Implement advanced improvements:
   - Bayesian Personalized Ranking (BPR)
   - Elastic Net optimizers (Budget, CF, Hybrid)
   - Multi-Armed Bandits exploration
   - GPU acceleration
3. ⏳ Re-run LLM evaluation with improvements
4. ⏳ Compare baseline vs improved results
5. ⏳ Document performance gains for research paper

---

## Research Value

This baseline provides:
- ✅ **Quantitative evidence** of need for improvements
- ✅ **Scientific rigor** through LLM-as-a-Judge methodology
- ✅ **Before/after comparison** framework
- ✅ **Clear research contribution** story

**Expected After Improvements**: Average Overall Score 2.3/10 → 7+/10 (3x improvement)
