"""
LightGBM Re-ranker Model Evaluation Service
Computes ROC-AUC curve and confusion matrix for recommendation system performance
"""

import numpy as np
from sklearn.metrics import roc_curve, roc_auc_score, confusion_matrix
from datetime import datetime, timedelta


def compute_model_performance(interactions, use_ltr_score=True):
    """
    Compute ROC-AUC and confusion matrix from recommendation interactions.
    
    Args:
        interactions: List of RecommendationInteraction objects
        use_ltr_score: If True, use ltr_score; else use blended_score
        
    Returns:
        dict with ROC curve data, AUC, confusion matrix, optimal threshold
    """
    if len(interactions) == 0:
        return {
            'error': 'No interactions found',
            'auc': None,
            'confusion_matrix': None,
            'roc_curve': None
        }
    
    # Map user actions to binary labels
    # accept_swap → 1 (positive), dismiss → 0 (negative), maybe_later → exclude
    y_true = []
    y_score = []
    
    for interaction in interactions:
        # Only include accept and dismiss actions (exclude maybe_later and shown)
        if interaction.action_type == 'accept_swap':
            y_true.append(1)
        elif interaction.action_type == 'dismiss':
            y_true.append(0)
        else:
            continue  # Skip maybe_later, shown, cart_removal
        
        # Get score (prefer ltr_score, fallback to blended_score)
        if use_ltr_score and interaction.ltr_score is not None:
            y_score.append(float(interaction.ltr_score))
        elif interaction.blended_score is not None:
            y_score.append(float(interaction.blended_score))
        else:
            # If no score available, remove this sample
            y_true.pop()
            continue
    
    if len(y_true) < 10:
        return {
            'error': 'Not enough labeled data (need at least 10 accept/dismiss actions)',
            'sample_count': len(y_true),
            'auc': None,
            'confusion_matrix': None,
            'roc_curve': None
        }
    
    # Convert to numpy arrays
    y_true = np.array(y_true)
    y_score = np.array(y_score)
    
    # Check for class diversity (need both positive and negative samples)
    positive_count = int(np.sum(y_true))
    negative_count = int(len(y_true) - positive_count)
    
    if positive_count == 0 or negative_count == 0:
        return {
            'error': f'Not enough class diversity for ROC-AUC evaluation. Need both accepts and dismisses. Found {positive_count} accepts, {negative_count} dismisses.',
            'sample_count': len(y_true),
            'positive_count': positive_count,
            'negative_count': negative_count,
            'auc': None,
            'confusion_matrix': None,
            'roc_curve': None
        }
    
    # Compute ROC curve
    fpr, tpr, thresholds = roc_curve(y_true, y_score)
    
    # Compute AUC
    auc = roc_auc_score(y_true, y_score)
    
    # Find optimal threshold (Youden's J statistic: TPR - FPR)
    j_scores = tpr - fpr
    optimal_idx = np.argmax(j_scores)
    optimal_threshold = float(thresholds[optimal_idx])
    
    # Compute confusion matrix using optimal threshold
    y_pred = (y_score >= optimal_threshold).astype(int)
    cm = confusion_matrix(y_true, y_pred)
    
    # Extract TP, TN, FP, FN
    tn, fp, fn, tp = cm.ravel() if cm.size == 4 else (0, 0, 0, 0)
    
    # Compute metrics
    accuracy = (tp + tn) / (tp + tn + fp + fn) if (tp + tn + fp + fn) > 0 else 0
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    f1_score = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
    
    # ROC curve data (sample 100 points for visualization)
    sample_indices = np.linspace(0, len(fpr) - 1, min(100, len(fpr))).astype(int)
    roc_points = [
        {'fpr': float(fpr[i]), 'tpr': float(tpr[i])}
        for i in sample_indices
    ]
    
    return {
        'auc': float(auc),
        'optimal_threshold': float(optimal_threshold),
        'confusion_matrix': {
            'true_positive': int(tp),
            'true_negative': int(tn),
            'false_positive': int(fp),
            'false_negative': int(fn)
        },
        'metrics': {
            'accuracy': float(accuracy),
            'precision': float(precision),
            'recall': float(recall),
            'f1_score': float(f1_score)
        },
        'roc_curve': roc_points,
        'sample_count': len(y_true),
        'positive_count': int(np.sum(y_true)),
        'negative_count': int(len(y_true) - np.sum(y_true)),
        'score_type': 'ltr_score' if use_ltr_score else 'blended_score'
    }


def filter_interactions_by_period(interactions, period='all'):
    """
    Filter interactions by time period.
    
    Args:
        interactions: List of RecommendationInteraction objects
        period: '7d', '30d', or 'all'
        
    Returns:
        Filtered list of interactions
    """
    if period == 'all':
        return interactions
    
    now = datetime.utcnow()
    
    if period == '7d':
        cutoff = now - timedelta(days=7)
    elif period == '30d':
        cutoff = now - timedelta(days=30)
    else:
        return interactions
    
    return [i for i in interactions if i.shown_at >= cutoff]


def filter_interactions_by_user(interactions, user_id=None):
    """
    Filter interactions by user ID.
    
    Args:
        interactions: List of RecommendationInteraction objects
        user_id: User ID to filter (None = all users)
        
    Returns:
        Filtered list of interactions
    """
    if user_id is None:
        return interactions
    
    return [i for i in interactions if i.user_id == int(user_id)]
