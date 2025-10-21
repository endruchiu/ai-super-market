"""
Blended Recommendations: Combines CF and Semantic Similarity
60% Collaborative Filtering + 40% Semantic Content Similarity
Enhanced with LightGBM LambdaMART re-ranking for behavior-aware recommendations
"""

import numpy as np
from typing import List, Dict, Optional
from cf_inference import get_cf_recommendations, get_user_purchase_history, load_cf_model
from semantic_budget import _GLOBAL, ensure_index, _encode

# LightGBM Re-Ranker (optional, graceful fallback if not available)
LGBM_AVAILABLE = False
try:
    from lgbm_reranker import get_reranker
    LGBM_AVAILABLE = True
    print("✓ LightGBM re-ranker loaded successfully")
except (ImportError, OSError) as e:
    print(f"⚠ LightGBM re-ranker not available (system dependency issue): {str(e)[:100]}")
    print("  → Using standard 60% CF + 40% Semantic blending")
    print("  → To enable LightGBM: install system libraries (libgomp) via Nix packages")


def get_blended_recommendations(
    user_id: str,
    top_k: int = 10,
    cf_weight: float = 0.6,
    semantic_weight: float = 0.4,
    session_context: Optional[Dict] = None,
    use_lgbm: bool = True,
    guardrail_mode: str = 'balanced'
) -> List[Dict]:
    """
    Get blended recommendations combining CF and semantic similarity.
    Enhanced with LightGBM LambdaMART re-ranking when available.
    
    Args:
        user_id: User ID (session_id)
        top_k: Number of recommendations to return
        cf_weight: Weight for CF scores (default 0.6)
        semantic_weight: Weight for semantic scores (default 0.4)
        session_context: Session context (cart, budget, etc.) for LightGBM
        use_lgbm: Whether to use LightGBM re-ranking (default True)
        guardrail_mode: Filtering mode: 'quality', 'economy', or 'balanced'
    
    Returns:
        List of recommendations with blended scores:
        [
            {
                "product_id": "123",
                "cf_score": 0.85,
                "semantic_score": 0.72,
                "blended_score": 0.80,
                "ltr_score": 0.92,  # If LightGBM is used
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
    
    # Compute semantic scores for CF recommendations and add metadata
    # Import PRODUCTS_DF for fast in-memory lookup
    from main import PRODUCTS_DF
    import pandas as pd
    
    blended_recs = []
    
    # Get session context for feature computation
    budget = session_context.get('budget', 40.0) if session_context else 40.0
    cart_value = session_context.get('cart_value', 0.0) if session_context else 0.0
    cart_size = session_context.get('cart_size', 0) if session_context else 0
    
    for cf_rec in cf_recs:
        product_id = int(cf_rec["product_id"])
        cf_score = cf_rec["score"]
        
        # Skip if product not in catalog
        if product_id not in PRODUCTS_DF.index:
            continue
        
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
        
        # Get product metadata for LightGBM features from PRODUCTS_DF
        product_row = PRODUCTS_DF.loc[product_id]
        product_price = float(product_row.get("_price_final", 10.0))
        product_name_lower = str(product_row.get("Title", "")).lower()
        product_rating = float(product_row.get("_rating", 2.5)) if pd.notna(product_row.get("_rating")) else 2.5
        product_category = str(product_row.get("Sub Category", ""))
        
        # Compute feature-rich candidate dict
        avg_cart_price = cart_value / cart_size if cart_size > 0 else 20.0
        price_saving = avg_cart_price - product_price
        within_budget = 1 if (cart_value - avg_cart_price + product_price) <= budget else 0
        
        # Quality and diet features
        quality_keywords = ['organic', 'premium', 'gourmet', 'artisan', 'fresh']
        quality_tags_score = sum(1 for kw in quality_keywords if kw in product_name_lower) / len(quality_keywords)
        
        diet_keywords = ['organic', 'gluten-free', 'vegan', 'non-gmo']
        diet_match_flag = 1 if any(kw in product_name_lower for kw in diet_keywords) else 0
        
        blended_recs.append({
            "product_id": str(product_id),
            "cf_score": float(cf_score),
            "semantic_score": float(semantic_score),
            "blended_score": float(blended_score),
            "rank": 0,  # Will be set after sorting
            # Additional features for LightGBM (using correct key names)
            "price": product_price,
            "price_saving": price_saving,
            "within_budget_flag": within_budget,
            "category": product_category,
            "category_match": 0,  # Will be computed if needed
            "popularity": product_rating / 5.0,
            "recency": 0.5,
            # Match lgbm_reranker expected keys
            "semantic_sim": semantic_score,  # Key for LightGBM
            "diet_match": diet_match_flag,  # Key for LightGBM
            "quality_tags_score": quality_tags_score,
            "same_semantic_cluster": 0,  # Key for LightGBM
            "semantic_distance": semantic_score,  # Key for LightGBM
            "size_ratio": 1.0
        })
    
    # Apply LightGBM re-ranking if available and enabled
    if use_lgbm and LGBM_AVAILABLE and session_context is not None:
        try:
            reranker = get_reranker(use_lgbm=True)
            
            session_id = session_context.get('session_id', f"sess_{user_id}")
            
            blended_recs = reranker.re_rank(
                session_id=session_id,
                user_id=user_id,
                candidates=blended_recs,
                session_context=session_context,
                guardrail_mode=guardrail_mode
            )
            
        except Exception as e:
            print(f"⚠ LightGBM re-ranking failed, using standard blending: {e}")
    else:
        # Standard blending: sort by blended score
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
