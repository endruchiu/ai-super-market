"""
Blended Recommendations: Combines CF and Semantic Similarity
60% Collaborative Filtering + 40% Semantic Content Similarity
"""

import numpy as np
from typing import List, Dict, Optional
from cf_inference import get_cf_recommendations, get_user_purchase_history, load_cf_model
from semantic_budget import _GLOBAL, ensure_index, _encode


def get_blended_recommendations(
    user_id: str,
    top_k: int = 10,
    cf_weight: float = 0.6,
    semantic_weight: float = 0.4
) -> List[Dict]:
    """
    Get blended recommendations combining CF and semantic similarity.
    
    Args:
        user_id: User ID (session_id)
        top_k: Number of recommendations to return
        cf_weight: Weight for CF scores (default 0.6)
        semantic_weight: Weight for semantic scores (default 0.4)
    
    Returns:
        List of recommendations with blended scores:
        [
            {
                "product_id": "123",
                "cf_score": 0.85,
                "semantic_score": 0.72,
                "blended_score": 0.80,
                "rank": 1
            },
            ...
        ]
    """
    # Load semantic index
    if _GLOBAL["df"] is None:
        idx = ensure_index()
        _GLOBAL.update(idx)
    
    df = _GLOBAL["df"]
    emb = _GLOBAL["emb"]
    
    # Check CF model availability
    model, artifacts = load_cf_model()
    if model is None or artifacts is None:
        return []
    
    # Get user's purchase history
    purchased_product_ids = get_user_purchase_history(user_id)
    has_purchase_history = len(purchased_product_ids) > 0
    
    # Get CF recommendations (get more candidates for blending)
    cf_recs = get_cf_recommendations(
        user_id, 
        top_k=top_k * 3,  # Get 3x candidates for reranking
        exclude_products=purchased_product_ids if has_purchase_history else []
    )
    
    if len(cf_recs) == 0:
        return []
    
    # Build user profile from purchase history (average embedding of purchased items)
    user_profile_emb = None
    purchase_embeddings = []
    
    if has_purchase_history:
        # semantic_budget df is NOT indexed by product_id, it has a 'product_id' column
        # We need to find the row position in the df to get the correct embedding
        for prod_id in purchased_product_ids:
            # Find product in dataframe by product_id column
            if 'product_id' in df.columns:
                mask = (df['product_id'] == prod_id).values
                row_indices = np.where(mask)[0]
                if len(row_indices) > 0:
                    row_pos = row_indices[0]
                    purchase_embeddings.append(emb[row_pos])
        
        if len(purchase_embeddings) > 0:
            # Average of purchased items = user's content preference
            user_profile_emb = np.mean(purchase_embeddings, axis=0)
            # Normalize for cosine similarity
            user_profile_emb = user_profile_emb / (np.linalg.norm(user_profile_emb) + 1e-9)
    
    # Compute semantic scores for CF recommendations
    blended_recs = []
    
    for cf_rec in cf_recs:
        product_id = int(cf_rec["product_id"])
        cf_score = cf_rec["score"]
        
        # Compute semantic score
        semantic_score = 0.0
        if user_profile_emb is not None and 'product_id' in df.columns:
            # Find product in dataframe by product_id column
            mask = (df['product_id'] == product_id).values
            row_indices = np.where(mask)[0]
            if len(row_indices) > 0:
                row_pos = row_indices[0]
                product_emb = emb[row_pos]
                
                # Normalize product embedding for true cosine similarity
                product_emb_norm = product_emb / (np.linalg.norm(product_emb) + 1e-9)
                
                # Cosine similarity (both normalized) - result in [-1, 1]
                cosine_sim = float(np.dot(user_profile_emb, product_emb_norm))
                
                # Rescale to [0, 1] to match CF score range
                semantic_score = (cosine_sim + 1.0) / 2.0
        
        # Blend scores (both now in [0, 1] range)
        blended_score = cf_weight * cf_score + semantic_weight * semantic_score
        
        blended_recs.append({
            "product_id": str(product_id),
            "cf_score": float(cf_score),
            "semantic_score": float(semantic_score),
            "blended_score": float(blended_score),
            "rank": 0  # Will be set after sorting
        })
    
    # Sort by blended score
    blended_recs.sort(key=lambda x: x["blended_score"], reverse=True)
    
    # Set ranks and return top-K
    for i, rec in enumerate(blended_recs[:top_k], 1):
        rec["rank"] = i
    
    return blended_recs[:top_k]


if __name__ == '__main__':
    """
    Test blended recommendations
    """
    from cf_inference import load_cf_model
    
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
            print(f"\nGenerating blended recommendations for user: {test_user_id}")
            
            recs = get_blended_recommendations(test_user_id, top_k=10)
            
            if recs:
                print(f"\nTop 10 Blended Recommendations (60% CF + 40% Semantic):")
                for rec in recs:
                    print(f"  Rank {rec['rank']}: Product {rec['product_id']}")
                    print(f"    CF: {rec['cf_score']:.4f}, Semantic: {rec['semantic_score']:.4f}, Blended: {rec['blended_score']:.4f}")
            else:
                print("No recommendations generated.")
