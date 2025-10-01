"""
Collaborative Filtering Inference
Loads trained CF model and generates personalized recommendations.
"""

import os
import numpy as np
import pickle
from typing import List, Dict, Optional, Tuple

# Lazy loading to avoid startup delays
_CF_MODEL = None
_CF_ARTIFACTS = None


def load_cf_model():
    """
    Load trained CF model and artifacts.
    Returns (model, artifacts) or (None, None) if not trained yet.
    """
    global _CF_MODEL, _CF_ARTIFACTS
    
    if _CF_MODEL is not None and _CF_ARTIFACTS is not None:
        return _CF_MODEL, _CF_ARTIFACTS
    
    model_path = 'ml_data/cf_model.keras'
    artifacts_path = 'ml_data/cf_artifacts.pkl'
    
    if not os.path.exists(model_path) or not os.path.exists(artifacts_path):
        print("CF model not trained yet. Run python train_cf_model.py first.")
        return None, None
    
    try:
        # Import keras only when needed
        from tensorflow import keras
        
        print("Loading CF model...")
        _CF_MODEL = keras.models.load_model(model_path)
        
        with open(artifacts_path, 'rb') as f:
            _CF_ARTIFACTS = pickle.load(f)
        
        print(f"✓ CF model loaded: {_CF_ARTIFACTS['num_users']} users, {_CF_ARTIFACTS['num_products']} products")
        return _CF_MODEL, _CF_ARTIFACTS
    
    except Exception as e:
        print(f"Error loading CF model: {e}")
        return None, None


def get_cf_recommendations(
    user_id: str,
    top_k: int = 10,
    exclude_products: Optional[List[int]] = None
) -> List[Dict]:
    """
    Get collaborative filtering recommendations for a user.
    
    Args:
        user_id: User ID (string, e.g., session_id)
        top_k: Number of recommendations to return
        exclude_products: List of product IDs to exclude (e.g., already purchased)
    
    Returns:
        List of recommendations:
        [
            {"product_id": "123456", "score": 0.85, "rank": 1},
            ...
        ]
        Returns empty list if model not trained or user unknown.
    """
    model, artifacts = load_cf_model()
    
    if model is None or artifacts is None:
        return []
    
    # Map user_id to user_idx
    user_id_to_idx = artifacts['user_id_to_idx']
    product_idx_to_id = artifacts['product_idx_to_id']
    
    if user_id not in user_id_to_idx:
        # Unknown user - return empty (or could return popular items)
        return []
    
    user_idx = user_id_to_idx[user_id]
    num_products = artifacts['num_products']
    
    # Score all products for this user
    user_batch = np.full(num_products, user_idx)
    all_product_indices = np.arange(num_products)
    
    scores = model.predict([user_batch, all_product_indices], verbose=0).flatten()
    
    # Sort by score (descending)
    sorted_indices = np.argsort(scores)[::-1]
    
    # Filter out excluded products if provided
    exclude_set = set(exclude_products) if exclude_products else set()
    
    recommendations = []
    for rank, prod_idx in enumerate(sorted_indices, 1):
        product_id = product_idx_to_id[prod_idx]
        
        # Skip excluded products
        if product_id in exclude_set:
            continue
        
        recommendations.append({
            "product_id": str(product_id),  # String for JSON safety
            "score": float(scores[prod_idx]),
            "rank": rank
        })
        
        if len(recommendations) >= top_k:
            break
    
    return recommendations


def get_user_purchase_history(user_id: str) -> List[int]:
    """
    Get list of product IDs the user has purchased.
    This is used to exclude already-purchased items from recommendations.
    
    Args:
        user_id: User ID (session_id)
    
    Returns:
        List of product IDs (integers)
    """
    try:
        from models import init_models
        from flask import current_app
        from flask_sqlalchemy import SQLAlchemy
        
        db = current_app.extensions['sqlalchemy']
        _, _, _, User, Order, OrderItem, _ = init_models(db)
        
        # Find user
        user = db.session.query(User).filter_by(session_id=user_id).first()
        if not user:
            return []
        
        # Get all purchased product IDs
        purchased_ids = (
            db.session.query(OrderItem.product_id)
            .join(Order, OrderItem.order_id == Order.id)
            .filter(Order.user_id == user.id)
            .distinct()
            .all()
        )
        
        return [pid[0] for pid in purchased_ids]
    
    except Exception as e:
        print(f"Error fetching purchase history: {e}")
        return []


if __name__ == '__main__':
    """
    Test CF inference
    """
    # Try to load model
    model, artifacts = load_cf_model()
    
    if model is None:
        print("\nNo trained model found.")
        print("To train: python train_cf_model.py")
    else:
        print(f"\nModel loaded successfully!")
        print(f"Users: {artifacts['num_users']}")
        print(f"Products: {artifacts['num_products']}")
        
        # Test with first user
        if artifacts['num_users'] > 0:
            test_user_id = list(artifacts['user_id_to_idx'].keys())[0]
            print(f"\nGenerating recommendations for user: {test_user_id}")
            
            recs = get_cf_recommendations(test_user_id, top_k=10)
            
            if recs:
                print(f"\nTop 10 CF Recommendations:")
                for rec in recs:
                    print(f"  Rank {rec['rank']}: Product {rec['product_id']} (score: {rec['score']:.4f})")
            else:
                print("No recommendations generated.")
