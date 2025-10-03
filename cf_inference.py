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


def get_user_db_id(session_id: str) -> Optional[int]:
    """
    Map session_id to database user.id.
    Returns None if user doesn't exist.
    """
    try:
        import os
        import psycopg2
        
        conn = psycopg2.connect(os.getenv('DATABASE_URL'))
        cur = conn.cursor()
        cur.execute("SELECT id FROM users WHERE session_id = %s", (session_id,))
        result = cur.fetchone()
        cur.close()
        conn.close()
        
        return result[0] if result else None
    except Exception as e:
        print(f"Error mapping session_id to user.id: {e}")
        return None


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
    
    # Map session_id to database user.id
    db_user_id = get_user_db_id(user_id)
    if db_user_id is None:
        # Unknown user - return empty
        return []
    
    # Map user DB ID to user_idx
    user_id_to_idx = artifacts['user_mapping']
    product_id_to_idx = artifacts['product_mapping']
    
    # Create reverse mapping: index -> product_id
    product_idx_to_id = {idx: pid for pid, idx in product_id_to_idx.items()}
    
    num_products = artifacts['num_products']
    
    # Handle cold start: create user profile from purchase history if user not in training data
    if db_user_id not in user_id_to_idx:
        # Get user's purchase history
        purchased_ids = get_user_purchase_history(user_id)
        
        if not purchased_ids:
            # No purchases, can't recommend
            return []
        
        # Get product embeddings for purchased items
        product_embedding_layer = model.layers[3]  # Product embedding layer (layer index 3)
        purchased_indices = []
        for pid in purchased_ids:
            if pid in product_id_to_idx:
                purchased_indices.append(product_id_to_idx[pid])
        
        if not purchased_indices:
            # None of their purchases are in the model
            return []
        
        # Create user profile: average of purchased product embeddings
        # Get embedding weights directly (not calling the layer)
        product_embedding_weights = product_embedding_layer.get_weights()[0]
        purchased_embeddings = product_embedding_weights[purchased_indices]
        user_profile_embedding = np.mean(purchased_embeddings, axis=0)
        
        # Score all products using dot product with user profile
        all_product_embeddings = product_embedding_weights  # All product embeddings
        scores = np.dot(all_product_embeddings, user_profile_embedding)
        
    else:
        # Known user - use trained embedding
        user_idx = user_id_to_idx[db_user_id]
        
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
        import os
        import psycopg2
        
        # Use direct SQL to avoid ORM model conflicts
        conn = psycopg2.connect(os.getenv('DATABASE_URL'))
        cur = conn.cursor()
        
        # Get purchased product IDs for this user
        query = """
            SELECT DISTINCT oi.product_id
            FROM order_items oi
            JOIN orders o ON oi.order_id = o.id
            JOIN users u ON o.user_id = u.id
            WHERE u.session_id = %s
        """
        cur.execute(query, (user_id,))
        results = cur.fetchall()
        
        cur.close()
        conn.close()
        
        return [row[0] for row in results]
    
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
            test_user_id = list(artifacts['user_mapping'].keys())[0]
            print(f"\nGenerating recommendations for user: {test_user_id}")
            
            recs = get_cf_recommendations(test_user_id, top_k=10)
            
            if recs:
                print(f"\nTop 10 CF Recommendations:")
                for rec in recs:
                    print(f"  Rank {rec['rank']}: Product {rec['product_id']} (score: {rec['score']:.4f})")
            else:
                print("No recommendations generated.")
