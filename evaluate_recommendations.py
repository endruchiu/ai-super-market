"""
Evaluation metrics for recommendation systems.
Implements Precision@K, Recall@K, and MAP@K for collaborative filtering.
"""

import numpy as np
from typing import List, Dict, Set


def precision_at_k(recommended: List, relevant: Set, k: int) -> float:
    """
    Calculate Precision@K for a single user.
    
    Precision@K = (# of recommended items @K that are relevant) / K
    
    Args:
        recommended: List of recommended item IDs (ordered by score)
        relevant: Set of relevant (ground truth) item IDs for this user
        k: Number of recommendations to consider
        
    Returns:
        Precision@K score (0.0 to 1.0)
    """
    if k == 0 or len(recommended) == 0:
        return 0.0
    
    # Take top K recommendations
    recommended_at_k = recommended[:k]
    
    # Count how many are relevant
    relevant_count = sum(1 for item in recommended_at_k if item in relevant)
    
    return relevant_count / k


def recall_at_k(recommended: List, relevant: Set, k: int) -> float:
    """
    Calculate Recall@K for a single user.
    
    Recall@K = (# of recommended items @K that are relevant) / (total # of relevant items)
    
    Args:
        recommended: List of recommended item IDs (ordered by score)
        relevant: Set of relevant (ground truth) item IDs for this user
        k: Number of recommendations to consider
        
    Returns:
        Recall@K score (0.0 to 1.0)
    """
    if len(relevant) == 0:
        return 0.0
    
    if k == 0 or len(recommended) == 0:
        return 0.0
    
    # Take top K recommendations
    recommended_at_k = recommended[:k]
    
    # Count how many are relevant
    relevant_count = sum(1 for item in recommended_at_k if item in relevant)
    
    return relevant_count / len(relevant)


def average_precision_at_k(recommended: List, relevant: Set, k: int) -> float:
    """
    Calculate Average Precision@K for a single user.
    
    AP@K = (1/min(k, |relevant|)) * Σ(Precision@i * rel(i)) for i=1 to k
    where rel(i) = 1 if item at position i is relevant, else 0
    
    Args:
        recommended: List of recommended item IDs (ordered by score)
        relevant: Set of relevant (ground truth) item IDs for this user
        k: Number of recommendations to consider
        
    Returns:
        Average Precision@K score (0.0 to 1.0)
    """
    if len(relevant) == 0 or k == 0 or len(recommended) == 0:
        return 0.0
    
    # Take top K recommendations
    recommended_at_k = recommended[:k]
    
    # Calculate precision at each position where a relevant item appears
    precisions = []
    relevant_count = 0
    
    for i, item in enumerate(recommended_at_k, 1):
        if item in relevant:
            relevant_count += 1
            precisions.append(relevant_count / i)
    
    if len(precisions) == 0:
        return 0.0
    
    return sum(precisions) / min(k, len(relevant))


def evaluate_recommendations(user_recommendations: Dict[int, List[int]], 
                            user_relevant_items: Dict[int, Set[int]],
                            k_values: List[int] = [5, 10, 20, 50]) -> Dict:
    """
    Evaluate recommendation quality across multiple users and K values.
    
    Args:
        user_recommendations: Dict mapping user_id -> list of recommended product IDs (ordered)
        user_relevant_items: Dict mapping user_id -> set of relevant product IDs (ground truth)
        k_values: List of K values to evaluate (default [5, 10, 20, 50])
        
    Returns:
        Dict with evaluation results:
        {
            'precision@k': {5: 0.23, 10: 0.19, ...},
            'recall@k': {5: 0.12, 10: 0.18, ...},
            'map@k': {5: 0.18, 10: 0.16, ...}
        }
    """
    results = {
        'precision@k': {k: [] for k in k_values},
        'recall@k': {k: [] for k in k_values},
        'map@k': {k: [] for k in k_values}
    }
    
    # Evaluate each user
    evaluated_users = 0
    
    for user_id, recommended in user_recommendations.items():
        # Skip if no relevant items for this user
        if user_id not in user_relevant_items or len(user_relevant_items[user_id]) == 0:
            continue
        
        relevant = user_relevant_items[user_id]
        evaluated_users += 1
        
        # Evaluate at each K
        for k in k_values:
            prec = precision_at_k(recommended, relevant, k)
            rec = recall_at_k(recommended, relevant, k)
            ap = average_precision_at_k(recommended, relevant, k)
            
            results['precision@k'][k].append(prec)
            results['recall@k'][k].append(rec)
            results['map@k'][k].append(ap)
    
    # Average across users
    averaged_results = {
        'precision@k': {},
        'recall@k': {},
        'map@k': {},
        'num_users': evaluated_users
    }
    
    for k in k_values:
        averaged_results['precision@k'][k] = np.mean(results['precision@k'][k]) if results['precision@k'][k] else 0.0
        averaged_results['recall@k'][k] = np.mean(results['recall@k'][k]) if results['recall@k'][k] else 0.0
        averaged_results['map@k'][k] = np.mean(results['map@k'][k]) if results['map@k'][k] else 0.0
    
    return averaged_results


def print_evaluation_results(results: Dict):
    """
    Pretty print evaluation results.
    
    Args:
        results: Dict from evaluate_recommendations()
    """
    print("\n" + "=" * 60)
    print("Recommendation Evaluation Results")
    print("=" * 60)
    print(f"Number of users evaluated: {results['num_users']}")
    print()
    
    # Print table
    k_values = sorted(results['precision@k'].keys())
    
    print(f"{'K':<10} {'Precision@K':<15} {'Recall@K':<15} {'MAP@K':<15}")
    print("-" * 60)
    
    for k in k_values:
        prec = results['precision@k'][k]
        rec = results['recall@k'][k]
        map_k = results['map@k'][k]
        
        print(f"{k:<10} {prec:<15.4f} {rec:<15.4f} {map_k:<15.4f}")
    
    print("=" * 60)
    print()


if __name__ == '__main__':
    """
    Test evaluation metrics with example data.
    """
    # Example: 3 users with recommendations and ground truth
    user_recommendations = {
        1: [101, 102, 103, 104, 105, 106, 107, 108],  # User 1's recommendations
        2: [201, 202, 203, 204, 205],                  # User 2's recommendations
        3: [301, 302, 303, 304, 305, 306]              # User 3's recommendations
    }
    
    user_relevant_items = {
        1: {102, 105, 109, 110},        # User 1 actually liked items 102, 105 (plus 2 not recommended)
        2: {201, 203, 205, 207},        # User 2 actually liked 201, 203, 205 (plus 1 not recommended)
        3: {304, 306, 307}              # User 3 actually liked 304, 306 (plus 1 not recommended)
    }
    
    # Evaluate
    results = evaluate_recommendations(
        user_recommendations,
        user_relevant_items,
        k_values=[1, 3, 5, 10]
    )
    
    # Print results
    print_evaluation_results(results)
    
    print("\nInterpretation:")
    print("- Precision@5: What fraction of top-5 recommendations were relevant?")
    print("- Recall@5: What fraction of all relevant items were in top-5?")
    print("- MAP@5: Average precision considering rank position of relevant items")
