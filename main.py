import os
import hashlib
from flask import Flask, jsonify, request, Response, session, render_template, send_from_directory
import pandas as pd
import numpy as np
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
import uuid
from semantic_budget import ensure_index, recommend_substitutions
from cf_inference import get_cf_recommendations, get_user_purchase_history
from blended_recommendations import get_blended_recommendations
from intent_detector import intent_detector
import qrcode
from io import BytesIO

# SQLAlchemy base class
class Base(DeclarativeBase):
    pass

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///grocery_app.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_recycle': 280,
    'pool_pre_ping': True,
}

# Initialize database
db = SQLAlchemy(model_class=Base)
db.init_app(app)

# Import and initialize models
from models import init_models
Product, ShoppingCart, UserBudget, User, Order, OrderItem, UserEvent, ReplenishableProduct, UserReplenishmentCycle, RecommendationInteraction = init_models(db)

# Create tables
with app.app_context():
    db.create_all()
    print("✓ Database tables created successfully")

# Build semantic index once and keep a lightweight products frame for listing
PRODUCTS_DF = None

def _init_index():
    global PRODUCTS_DF
    if PRODUCTS_DF is not None:
        return
    print("Loading semantic index and product data...")
    idx = ensure_index()  # uses env GROCERY_CSV or default path
    PRODUCTS_DF = idx["df"]
    # keep only columns we display in /api/products
    # (the recommender uses more columns internally via semantic_budget cache)
    keep = ["Title","Sub Category","_price_final","_size_value","_size_unit",
            "Calories","Fat_g","Carbs_g","Sugar_g","Protein_g","Sodium_mg","Feature","Product Description"]
    for c in keep:
        if c not in PRODUCTS_DF.columns:
            PRODUCTS_DF[c] = np.nan
    
    # Generate stable unique product IDs by hashing Title + SubCategory deterministically
    def generate_product_id(row):
        # Combine title and subcategory into a single unique key
        key = f"{row['Title']}|{row['Sub Category']}"
        # Use deterministic hash that's stable across restarts
        hash_bytes = hashlib.blake2b(key.encode('utf-8'), digest_size=8).digest()
        # Convert to positive int64
        return int.from_bytes(hash_bytes, 'big', signed=False) & ((1 << 63) - 1)
    
    PRODUCTS_DF['id'] = PRODUCTS_DF.apply(generate_product_id, axis=1)
    
    # Verify uniqueness of IDs
    if not PRODUCTS_DF['id'].is_unique:
        print("Warning: Duplicate product IDs detected, de-duplicating...")
        PRODUCTS_DF = PRODUCTS_DF.drop_duplicates(subset=['id'], keep='first')
    
    # Set id as index for O(1) lookups
    PRODUCTS_DF.set_index('id', inplace=True)
    assert PRODUCTS_DF.index.is_unique, "Product IDs must be unique"
    
    print(f"✓ Loaded {len(PRODUCTS_DF)} products successfully")

# Initialize the index at startup to avoid timeout on first request
print("Initializing product catalog...")
_init_index()

@app.route("/healthz")
def healthz():
    return "ok", 200

@app.route("/api/products")
def api_products():
    """
    Returns a small page of products for UI demo.
    Query params:
      - subcat (optional): filter by Sub Category
      - limit (optional): default 24
      - skip (optional): default 0
    """
    if PRODUCTS_DF is None:
        _init_index()
    subcat = request.args.get("subcat")
    limit = int(request.args.get("limit", 24))
    skip = int(request.args.get("skip", 0))
    df = PRODUCTS_DF
    if subcat:
        df = df[df["Sub Category"] == subcat]
    # deterministic sample: slice
    df = df.iloc[skip: skip + limit].copy()

    def to_item(row):
        # Minimal product dict compatible with cart/recommender
        # Use the DataFrame index (product ID) directly - already computed in _init_index
        # Convert to string to avoid JavaScript safe integer issues (2^53-1 limit)
        item = {
            "id": str(int(row.name)),  # Convert int64 to string for JSON safety
            "title": str(row["Title"]),
            "subcat": str(row["Sub Category"]),
            "price": float(row["_price_final"]) if pd.notna(row["_price_final"]) else None,
            "qty": 1,
        }
        # size info
        if pd.notna(row.get("_size_value")) and pd.notna(row.get("_size_unit")):
            item["size_value"] = float(row["_size_value"])
            item["size_unit"]  = str(row["_size_unit"])
        else:
            item["size_value"] = None
            item["size_unit"]  = None
        # nutrition (if present)
        nutr = {}
        for k in ["Calories","Sugar_g","Protein_g","Sodium_mg","Fat_g","Carbs_g"]:
            if k in row and pd.notna(row[k]):
                try:
                    v = float(row[k])
                    nutr[k] = v
                except Exception:
                    pass
        if nutr:
            item["nutrition"] = nutr
        # extra display fields
        item["feature"] = str(row.get("Feature") or "")
        item["desc"] = str(row.get("Product Description") or "")
        return item

    data = [to_item(r) for _, r in df.iterrows()]
    # also include a small list of available subcats for UI filters
    subcats = sorted(PRODUCTS_DF["Sub Category"].dropna().unique().tolist())[:50]
    return jsonify({"items": data, "subcats": subcats})

@app.route("/api/budget/recommendations", methods=["POST"])
def api_budget_recommendations():
    payload = request.get_json(force=True)
    cart = payload.get("cart", [])
    budget = float(payload.get("budget", 0))
    res = recommend_substitutions(cart, budget)
    return jsonify(res)

@app.route("/api/cf/recommendations", methods=["GET", "POST"])
def api_cf_recommendations():
    """
    Get collaborative filtering (CF) personalized recommendations.
    
    POST (cart-aware budget replacements):
      Body: {"cart": [...], "budget": 40.0}
      Returns cheaper alternatives when cart > budget
    
    GET (general recommendations - legacy):
      Query params: top_k
      Returns general personalized recommendations
    """
    from cf_inference import load_cf_model
    
    # Get or create session_id
    if 'user_session' not in session:
        session['user_session'] = str(uuid.uuid4())
    
    user_id = session['user_session']
    
    # Ensure user exists in database for CF to work
    user = User.query.filter_by(session_id=user_id).first()
    if not user:
        user = User(session_id=user_id)
        db.session.add(user)
        db.session.commit()
    
    # Check if model is available
    model, artifacts = load_cf_model()
    model_available = (model is not None and artifacts is not None)
    
    if not model_available:
        return jsonify({
            "recommendations": [],
            "suggestions": [],
            "user_id": user_id,
            "model_available": False,
            "reason": "Model not trained yet. Make purchases to accumulate history, then run: python train_cf_model.py"
        })
    
    # Handle POST request for cart-aware budget replacements
    if request.method == "POST":
        payload = request.get_json(force=True)
        cart = payload.get("cart", [])
        budget = float(payload.get("budget", 0))
        
        # Calculate cart total
        total = sum(float(item.get("price", 0.0)) * int(item.get("qty", 1)) for item in cart)
        
        # Only return recommendations if over budget
        if total <= budget or budget <= 0:
            return jsonify({
                "suggestions": [],
                "user_id": user_id,
                "model_available": True,
                "total": total,
                "budget": budget,
                "message": f"Current total ${total:.2f} is within budget ${budget:.2f}"
            })
        
        # Get CF-based cheaper alternatives for each cart item (requires purchase history)
        suggestions = []
        recs = get_cf_recommendations(user_id, top_k=100, exclude_products=[])
        
        # Only generate suggestions if user has purchase history
        if len(recs) > 0:
            for item in cart:
                item_title = item.get("title", "")
                item_subcat = item.get("subcat", "")
                item_price = float(item.get("price", 0.0))
                item_qty = int(item.get("qty", 1))
                
                cheaper_alts = []
                for rec in recs:
                    product_id = int(rec["product_id"])
                    if product_id in PRODUCTS_DF.index:
                        row = PRODUCTS_DF.loc[product_id]
                        rec_price = float(row.get("_price_final", 0))
                        rec_subcat = str(row.get("Sub Category", ""))
                        rec_title = str(row["Title"])
                        
                        # Cheaper AND same subcategory AND not the same product
                        if rec_price < item_price and rec_subcat == item_subcat and rec_title != item_title:
                            saving = (item_price - rec_price) * item_qty
                            discount_pct = int((1 - rec_price / item_price) * 100)
                            
                            # Convert score to user-friendly confidence phrase
                            score = float(rec.get('score', 0))
                            if score >= 0.7:
                                confidence = "Highly recommended for you"
                            elif score >= 0.4:
                                confidence = "Good match based on your taste"
                            else:
                                confidence = "Popular among shoppers like you"
                            
                            # Create compelling, specific reason with confidence
                            reason = f"{confidence}: {rec_title} — similar taste, {discount_pct}% cheaper (save ${saving:.2f})"
                            
                            cheaper_alts.append({
                                "replace": item_title,
                                "with": rec_title,
                                "expected_saving": f"{saving:.2f}",
                                "similarity": confidence,
                                "reason": reason,
                                "replacement_product": {
                                    "id": str(product_id),
                                    "title": rec_title,
                                    "subcat": rec_subcat,
                                    "price": rec_price,
                                    "qty": 1,
                                    "size_value": float(row["_size_value"]) if pd.notna(row.get("_size_value")) else None,
                                    "size_unit": str(row["_size_unit"]) if pd.notna(row.get("_size_unit")) else None
                                }
                            })
                
                # If no same-subcategory alternatives found, allow any cheaper alternative
                if not cheaper_alts:
                    for rec in recs[:20]:  # Check top 20 recommendations
                        product_id = int(rec["product_id"])
                        if product_id in PRODUCTS_DF.index:
                            row = PRODUCTS_DF.loc[product_id]
                            rec_price = float(row.get("_price_final", 0))
                            rec_subcat = str(row.get("Sub Category", ""))
                            rec_title = str(row["Title"])
                            
                            # Just cheaper AND not the same product (relax subcategory requirement)
                            if rec_price < item_price and rec_title != item_title:
                                saving = (item_price - rec_price) * item_qty
                                discount_pct = int((1 - rec_price / item_price) * 100)
                                
                                # Convert score to user-friendly confidence phrase
                                score = float(rec.get('score', 0))
                                if score >= 0.7:
                                    confidence = "Strongly recommended"
                                elif score >= 0.4:
                                    confidence = "Recommended based on your history"
                                else:
                                    confidence = "Customers like you also bought"
                                
                                # Create compelling reason for cross-category recommendation
                                reason = f"{confidence}: {rec_title} — {discount_pct}% cheaper (save ${saving:.2f})"
                                
                                cheaper_alts.append({
                                    "replace": item_title,
                                    "with": rec_title,
                                    "expected_saving": f"{saving:.2f}",
                                    "similarity": confidence,
                                    "reason": reason,
                                    "replacement_product": {
                                        "id": str(product_id),
                                        "title": rec_title,
                                        "subcat": rec_subcat,
                                        "price": rec_price,
                                        "qty": 1,
                                        "size_value": float(row["_size_value"]) if pd.notna(row.get("_size_value")) else None,
                                        "size_unit": str(row["_size_unit"]) if pd.notna(row.get("_size_unit")) else None
                                    }
                                })
                                if len(cheaper_alts) >= 2:
                                    break
                
                # Add top 2 alternatives for this item
                cheaper_alts.sort(key=lambda x: float(x["expected_saving"]), reverse=True)
                suggestions.extend(cheaper_alts[:2])
        
        return jsonify({
            "suggestions": suggestions,
            "total": total,
            "budget": budget,
            "message": f"Found {len(suggestions)} CF-based cheaper alternatives" if suggestions else "No CF alternatives found",
            "user_id": user_id,
            "model_available": True
        })
    
    # Handle GET request (legacy - general recommendations)
    try:
        top_k = int(request.args.get("top_k", 10))
        top_k = max(1, min(top_k, 50))
    except (ValueError, TypeError):
        top_k = 10
    
    exclude_products = get_user_purchase_history(user_id)
    recs = get_cf_recommendations(user_id, top_k=top_k, exclude_products=exclude_products)
    
    if len(recs) == 0:
        return jsonify({
            "recommendations": [],
            "user_id": user_id,
            "model_available": True,
            "reason": "Unknown user (no purchase history). Make purchases to get personalized recommendations."
        })
    
    # Enrich with product info
    enriched_recs = []
    for rec in recs:
        product_id = int(rec["product_id"])
        if product_id in PRODUCTS_DF.index:
            row = PRODUCTS_DF.loc[product_id]
            rec["product_info"] = {
                "title": str(row["Title"]),
                "subcat": str(row["Sub Category"]),
                "price": float(row["_price_final"]) if pd.notna(row["_price_final"]) else None,
            }
        else:
            rec["product_info"] = None
        enriched_recs.append(rec)
    
    return jsonify({
        "recommendations": enriched_recs,
        "user_id": user_id,
        "model_available": True
    })

@app.route("/api/blended/recommendations", methods=["GET", "POST"])
def api_blended_recommendations():
    """
    Get blended recommendations combining CF (60%) and semantic similarity (40%).
    
    POST (cart-aware budget replacements):
      Body: {"cart": [...], "budget": 40.0}
      Returns cheaper alternatives when cart > budget
    
    GET (general recommendations - legacy):
      Query params: top_k
      Returns general blended recommendations
    """
    # Get or create session_id
    if 'user_session' not in session:
        session['user_session'] = str(uuid.uuid4())
    
    user_id = session['user_session']
    
    # Ensure user exists in database for blended recommendations to work
    user = User.query.filter_by(session_id=user_id).first()
    if not user:
        user = User(session_id=user_id)
        db.session.add(user)
        db.session.commit()
    
    # Check if model was available
    from cf_inference import load_cf_model
    model, artifacts = load_cf_model()
    model_available = (model is not None and artifacts is not None)
    
    if not model_available:
        return jsonify({
            "recommendations": [],
            "suggestions": [],
            "user_id": user_id,
            "model_available": False,
            "reason": "Model not trained yet. Make purchases to accumulate history, then run: python train_cf_model.py"
        })
    
    # Handle POST request for cart-aware budget replacements
    if request.method == "POST":
        payload = request.get_json(force=True)
        cart = payload.get("cart", [])
        budget = float(payload.get("budget", 0))
        
        # Calculate cart total
        total = sum(float(item.get("price", 0.0)) * int(item.get("qty", 1)) for item in cart)
        
        # Only return recommendations if over budget
        if total <= budget or budget <= 0:
            return jsonify({
                "suggestions": [],
                "user_id": user_id,
                "model_available": True,
                "total": total,
                "budget": budget,
                "message": f"Current total ${total:.2f} is within budget ${budget:.2f}"
            })
        
        # Get blended cheaper alternatives for each cart item (requires purchase history)
        suggestions = []
        
        # Detect user intent from recent session behavior
        # Use the SAME calculation as the UI panel (without EMA smoothing) for consistency
        user = User.query.filter_by(session_id=user_id).first()
        if not user:
            current_intent = 0.5
        else:
            from datetime import datetime, timedelta
            cutoff = datetime.utcnow() - timedelta(minutes=10)
            recent_events = UserEvent.query.filter(
                UserEvent.user_id == user.id,
                UserEvent.created_at >= cutoff
            ).order_by(UserEvent.created_at.desc()).limit(10).all()
            
            # Calculate raw intent (same logic as /api/isrec/intent endpoint)
            quality_score = 0.0
            economy_score = 0.0
            
            premium_keywords = ['organic', 'premium', 'grass-fed', 'free-range', 'artisan', 'imported', 'gourmet', 'specialty']
            budget_keywords = ['value', 'budget', 'saver', 'basic', 'everyday']
            
            for event in recent_events:
                product_id = event.product_id
                if product_id in PRODUCTS_DF.index:
                    row = PRODUCTS_DF.loc[product_id]
                    price = float(row.get("_price_final", 0))
                    title_lower = str(row['Title']).lower()
                    
                    # Quality signals - only track cart_add and cart_remove
                    is_premium = any(kw in title_lower for kw in premium_keywords)
                    is_expensive = price > 25
                    
                    if event.event_type == 'cart_add':
                        if is_premium:
                            quality_score += 2.0
                        if is_expensive:
                            quality_score += 1.0
                    elif event.event_type == 'cart_remove' and price < 15:
                        quality_score += 1.5
                    
                    # Economy signals - only track cart_add and cart_remove
                    is_value = any(kw in title_lower for kw in budget_keywords)
                    is_cheap = price < 10
                    
                    if event.event_type == 'cart_add':
                        if is_value:
                            economy_score += 2.0
                        if is_cheap:
                            economy_score += 1.5
                    elif event.event_type == 'cart_remove' and price > 20:
                        economy_score += 2.0
            
            # Calculate intent score (same as UI panel)
            total = quality_score + economy_score
            current_intent = quality_score / total if total > 0 else 0.5
        
        # Map ISRec intent to guardrail mode (stricter thresholds for instant responsiveness)
        if current_intent > 0.65:
            guardrail_mode = 'quality'
            mode_label = "Quality mode"
        elif current_intent < 0.35:
            guardrail_mode = 'economy'
            mode_label = "Economy mode"
        else:
            guardrail_mode = 'balanced'
            mode_label = "Balanced mode"
        
        # DEBUG: Log intent detection for recommendations
        print(f"🎯 ISRec Intent: {current_intent:.2f} → Guardrail Mode: {guardrail_mode} ({mode_label})")
        
        # Build session context for LightGBM re-ranking
        session_context = {
            'session_id': user_id,
            'cart': cart,
            'cart_value': total,
            'cart_size': len(cart),
            'budget': budget,
            'budget_pressure': max(0, (total - budget) / budget) if budget > 0 else 0,
            'current_intent': current_intent  # Intent score [0=economy, 1=quality]
        }
        
        recs = get_blended_recommendations(
            user_id, 
            top_k=100,
            cf_weight=0.6,      # ← Change this (Collaborative Filtering weight)
            semantic_weight=0.4, # ← Change this (Semantic similarity weight)
            session_context=session_context,
            use_lgbm=True,
            guardrail_mode=guardrail_mode  # ← Use ISRec intent to filter products!
        )
        
        # Only generate suggestions if user has purchase history
        if len(recs) > 0:
            for item in cart:
                item_title = item.get("title", "")
                item_subcat = item.get("subcat", "")
                item_price = float(item.get("price", 0.0))
                item_qty = int(item.get("qty", 1))
                
                cheaper_alts = []
                for rec in recs:
                    product_id = int(rec["product_id"])
                    if product_id in PRODUCTS_DF.index:
                        row = PRODUCTS_DF.loc[product_id]
                        rec_price = float(row.get("_price_final", 0))
                        rec_subcat = str(row.get("Sub Category", ""))
                        rec_title = str(row["Title"])
                        
                        # Cheaper AND same subcategory AND not the same product
                        if rec_price < item_price and rec_subcat == item_subcat and rec_title != item_title:
                            saving = (item_price - rec_price) * item_qty
                            discount_pct = int((1 - rec_price / item_price) * 100)
                            
                            # Use LLM to generate natural, conversational message
                            # This connects ISRec intent with the recommendation
                            score = float(rec.get('blended_score', 0))
                            reason = generate_llm_recommendation_message(
                                intent_score=current_intent,
                                product_name=rec_title,
                                original_product=item_title,
                                savings=saving,
                                discount_pct=discount_pct
                            )
                            
                            cheaper_alts.append({
                                "replace": item_title,
                                "with": rec_title,
                                "expected_saving": f"{saving:.2f}",
                                "similarity": "Great match",  # Human-friendly, no numbers
                                "reason": reason,
                                "intent_score": current_intent,  # Pass ISRec intent score to frontend
                                "replacement_product": {
                                    "id": str(product_id),
                                    "title": rec_title,
                                    "subcat": rec_subcat,
                                    "price": rec_price,
                                    "qty": 1,
                                    "size_value": float(row["_size_value"]) if pd.notna(row.get("_size_value")) else None,
                                    "size_unit": str(row["_size_unit"]) if pd.notna(row.get("_size_unit")) else None
                                }
                            })
                
                # If no same-subcategory alternatives found, allow any cheaper alternative
                if not cheaper_alts:
                    for rec in recs[:20]:  # Check top 20 recommendations
                        product_id = int(rec["product_id"])
                        if product_id in PRODUCTS_DF.index:
                            row = PRODUCTS_DF.loc[product_id]
                            rec_price = float(row.get("_price_final", 0))
                            rec_subcat = str(row.get("Sub Category", ""))
                            rec_title = str(row["Title"])
                            
                            # Just cheaper AND not the same product (relax subcategory requirement)
                            if rec_price < item_price and rec_title != item_title:
                                saving = (item_price - rec_price) * item_qty
                                discount_pct = int((1 - rec_price / item_price) * 100)
                                
                                # Use LLM to generate natural, conversational message
                                # This connects ISRec intent with cross-category recommendation
                                score = float(rec.get('blended_score', 0))
                                reason = generate_llm_recommendation_message(
                                    intent_score=current_intent,
                                    product_name=rec_title,
                                    original_product=item_title,
                                    savings=saving,
                                    discount_pct=discount_pct
                                )
                                
                                cheaper_alts.append({
                                    "replace": item_title,
                                    "with": rec_title,
                                    "expected_saving": f"{saving:.2f}",
                                    "similarity": "Good alternative",  # Human-friendly, no numbers
                                    "reason": reason,
                                    "intent_score": current_intent,  # Pass ISRec intent score to frontend
                                    "replacement_product": {
                                        "id": str(product_id),
                                        "title": rec_title,
                                        "subcat": rec_subcat,
                                        "price": rec_price,
                                        "qty": 1,
                                        "size_value": float(row["_size_value"]) if pd.notna(row.get("_size_value")) else None,
                                        "size_unit": str(row["_size_unit"]) if pd.notna(row.get("_size_unit")) else None
                                    }
                                })
                                if len(cheaper_alts) >= 2:
                                    break
                
                # Add top 2 alternatives for this item
                cheaper_alts.sort(key=lambda x: float(x["expected_saving"]), reverse=True)
                suggestions.extend(cheaper_alts[:2])
        
        return jsonify({
            "suggestions": suggestions,
            "total": total,
            "budget": budget,
            "message": f"Found {len(suggestions)} hybrid AI cheaper alternatives" if suggestions else "No hybrid alternatives found",
            "user_id": user_id,
            "model_available": True,
            "weights": {"cf": 0.6, "semantic": 0.4}
        })
    
    # Handle GET request (legacy - general recommendations)
    try:
        top_k = int(request.args.get("top_k", 10))
        top_k = max(1, min(top_k, 50))
    except (ValueError, TypeError):
        top_k = 10
    
    recs = get_blended_recommendations(user_id, top_k=top_k)
    
    if len(recs) == 0:
        return jsonify({
            "recommendations": [],
            "user_id": user_id,
            "model_available": True,
            "reason": "Unknown user (no purchase history). Make purchases to get personalized recommendations."
        })
    
    # Enrich with product info
    enriched_recs = []
    for rec in recs:
        product_id = int(rec["product_id"])
        if product_id in PRODUCTS_DF.index:
            row = PRODUCTS_DF.loc[product_id]
            rec["product_info"] = {
                "title": str(row["Title"]),
                "subcat": str(row["Sub Category"]),
                "price": float(row["_price_final"]) if pd.notna(row["_price_final"]) else None,
            }
        else:
            rec["product_info"] = None
        enriched_recs.append(rec)
    
    return jsonify({
        "recommendations": enriched_recs,
        "user_id": user_id,
        "model_available": True,
        "weights": {"cf": 0.6, "semantic": 0.4}
    })

@app.route("/api/model/feature-importance", methods=["GET"])
def api_model_feature_importance():
    """
    Get feature importance from trained LightGBM model.
    Shows what the ML model learned (not hardcoded 60/40 weights).
    """
    try:
        from lgbm_reranker import get_reranker
        
        # Get the reranker instance
        reranker = get_reranker(use_lgbm=True)
        
        # Extract feature importance
        importance = reranker.get_feature_importance()
        
        if not importance:
            return jsonify({
                "model_available": False,
                "reason": "LightGBM model not loaded or feature importance unavailable",
                "fallback_weights": {"cf": 60, "semantic": 40}
            })
        
        # Get training stats (if available)
        training_samples = 289  # From training data
        training_sessions = 68  # From training data
        
        # Group related features for display
        top_features = dict(list(importance.items())[:10])  # Top 10 features
        
        # Calculate aggregated scores for main components
        cf_importance = importance.get('cf_bpr_score', 0)
        semantic_importance = importance.get('semantic_sim', 0)
        price_importance = importance.get('price_saving', 0)
        budget_importance = importance.get('budget_pressure', 0)
        
        return jsonify({
            "model_available": True,
            "all_features": importance,
            "top_features": top_features,
            "key_weights": {
                "cf_score": round(cf_importance, 1),
                "semantic_similarity": round(semantic_importance, 1),
                "price_saving": round(price_importance, 1),
                "budget_pressure": round(budget_importance, 1)
            },
            "training_info": {
                "samples": training_samples,
                "sessions": training_sessions,
                "total_features": len(importance)
            }
        })
        
    except Exception as e:
        print(f"Error getting feature importance: {e}")
        return jsonify({
            "model_available": False,
            "reason": str(e),
            "fallback_weights": {"cf": 60, "semantic": 40}
        })

@app.route("/api/checkout", methods=["POST"])
def api_checkout():
    """Complete the purchase and persist order history"""
    try:
        payload = request.get_json(force=True)
        cart = payload.get("cart", [])
        
        if not cart:
            return jsonify({"success": False, "error": "Cart is empty"}), 400
        
        # Get or create session_id
        if 'user_session' not in session:
            session['user_session'] = str(uuid.uuid4())
        session_id = session['user_session']
        
        # Get or create user
        user = User.query.filter_by(session_id=session_id).first()
        if not user:
            user = User(session_id=session_id)
            db.session.add(user)
            db.session.flush()
        else:
            user.last_active = db.func.current_timestamp()
        
        # Validate cart items and calculate totals server-side
        validated_items = []
        total_amount = 0.0
        item_count = 0
        
        for item in cart:
            product_id_str = item.get('id')
            if product_id_str is None:
                continue  # Skip items without product_id
            
            # Convert string ID back to int64 for server-side lookup
            try:
                product_id = int(product_id_str)
            except (ValueError, TypeError):
                print(f"Invalid product ID format: {product_id_str}")
                return jsonify({"success": False, "error": "Invalid product in cart"}), 400
            
            # Validate and parse quantity
            try:
                quantity = int(item.get('qty', 1))
                quantity = max(1, min(quantity, 1000))  # Clamp to reasonable range
            except (ValueError, TypeError):
                print(f"Invalid quantity for product {product_id}, defaulting to 1")
                quantity = 1
            
            # Look up authoritative price from indexed PRODUCTS_DF
            try:
                product_row = PRODUCTS_DF.loc[product_id]
            except KeyError:
                print(f"Error: Product {product_id} not found in catalog, rejecting item")
                return jsonify({"success": False, "error": "Invalid product in cart"}), 400
            
            # Use server-side authoritative price
            server_price = product_row.get('_price_final')
            if pd.isna(server_price):
                unit_price = 0.0
            else:
                unit_price = float(server_price)
            
            # Get authoritative title and subcat from server
            title = str(product_row.get('Title', ''))
            subcat = str(product_row.get('Sub Category', ''))
            
            # Calculate line total
            line_total = unit_price * quantity
            total_amount += line_total
            item_count += quantity
            
            validated_items.append({
                'product_id': product_id,
                'title': title,
                'subcat': subcat,
                'quantity': quantity,
                'unit_price': unit_price,
                'line_total': line_total,
                'was_substitute': bool(item.get('isSubstitute', False))
            })
        
        # Reject empty orders
        if not validated_items:
            return jsonify({"success": False, "error": "No valid items in cart"}), 400
        
        # Create order with server-validated totals
        order = Order(
            user_id=user.id,
            total_amount=total_amount,
            item_count=item_count
        )
        db.session.add(order)
        db.session.flush()
        
        # Create order items and purchase events with validated data
        for item in validated_items:
            # Create order item
            order_item = OrderItem(
                order_id=order.id,
                product_id=item['product_id'],
                product_title=item['title'],
                product_subcat=item['subcat'],
                quantity=item['quantity'],
                unit_price=item['unit_price'],
                line_total=item['line_total']
            )
            db.session.add(order_item)
            
            # Create purchase event
            purchase_event = UserEvent(
                user_id=user.id,
                event_type='purchase',
                product_id=item['product_id'],
                product_title=item['title'],
                product_subcat=item['subcat'],
                event_data={
                    'order_id': order.id,
                    'quantity': item['quantity'],
                    'unit_price': item['unit_price'],
                    'was_substitute': item['was_substitute']
                }
            )
            db.session.add(purchase_event)
        
        # Commit all changes
        db.session.commit()
        
        # AUTO-UPDATE REPLENISHMENT CYCLES after purchase
        try:
            from replenishment_engine import ReplenishmentEngine
            engine = ReplenishmentEngine(db, PRODUCTS_DF, Order, OrderItem, ReplenishableProduct, UserReplenishmentCycle)
            
            # Identify replenishable products (quick check)
            engine.identify_replenishable_products(min_purchases=2, min_users=1)
            
            # Update cycles for this user
            cycles_updated = engine.calculate_user_cycles(user.id)
            
            if cycles_updated > 0:
                print(f"✓ Updated {cycles_updated} replenishment cycles for user {user.id}")
        except Exception as e:
            # Don't fail checkout if replenishment update fails
            print(f"⚠️  Replenishment update warning: {e}")
        
        return jsonify({
            "success": True,
            "order_id": order.id,
            "total_amount": float(total_amount),
            "item_count": item_count,
            "message": "Order completed successfully!"
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"Checkout error: {e}")
        return jsonify({"success": False, "error": "Checkout failed. Please try again."}), 500

@app.route("/api/user/signin", methods=["POST"])
def user_signin():
    """
    Sign in a user with email and name (no password required)
    This allows the backend to track purchases by email
    """
    try:
        data = request.get_json(force=True)
        email = data.get("email")
        name = data.get("name")
        
        if not email or not name:
            return jsonify({"success": False, "error": "Email and name required"}), 400
        
        # Set the session to use email as session_id
        session['user_session'] = email
        
        # Find or create user
        user = User.query.filter_by(session_id=email).first()
        
        if not user:
            # Create new user
            user = User(
                session_id=email,
                name=name,
                intent_ema=0.5
            )
            db.session.add(user)
            db.session.commit()
        else:
            # Update name if changed
            if user.name != name:
                user.name = name
                db.session.commit()
        
        return jsonify({
            "success": True, 
            "message": "Signed in successfully",
            "user": {
                "id": user.id,
                "email": user.session_id,
                "name": user.name
            }
        })
    except Exception as e:
        db.session.rollback()
        print(f"Sign-in error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/qr-code")
def generate_qr_code():
    """
    Generate a QR code image for quick login
    The QR code points to /qr-login endpoint
    """
    try:
        base_url = request.host_url.rstrip('/')
        qr_url = f"{base_url}/qr-login"
        
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(qr_url)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        
        img_io = BytesIO()
        img.save(img_io, 'PNG')
        img_io.seek(0)
        
        return Response(img_io.getvalue(), mimetype='image/png')
        
    except Exception as e:
        print(f"QR code generation error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/qr-login")
def qr_login_page():
    """
    Landing page when QR code is scanned
    This page will handle device fingerprinting and auto-login
    """
    return render_template('qr_login.html')

@app.route("/api/qr-login", methods=["POST"])
def qr_login():
    """
    Handle QR code login with device fingerprinting
    Creates or retrieves a demo account based on device_id
    """
    try:
        data = request.get_json(force=True)
        device_id = data.get("device_id")
        
        if not device_id:
            return jsonify({"success": False, "error": "Device ID required"}), 400
        
        demo_email = f"qr_demo_{device_id}@ai-supermarket.demo"
        
        user = User.query.filter_by(session_id=demo_email).first()
        
        if not user:
            user = User(
                session_id=demo_email,
                name=f"QR Demo User",
                intent_ema=0.5
            )
            db.session.add(user)
            db.session.commit()
            is_new = True
        else:
            is_new = False
        
        session['user_session'] = demo_email
        
        return jsonify({
            "success": True,
            "message": "QR login successful",
            "is_new_user": is_new,
            "user": {
                "id": user.id,
                "email": demo_email,
                "name": user.name
            }
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"QR login error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/user/stats", methods=["POST"])
def get_user_stats():
    """
    Get purchase statistics for the signed-in user
    Expects: {"email": "user@example.com"}
    Returns: total_orders, total_spent, total_items, avg_order, recent_orders
    """
    try:
        data = request.get_json(force=True)
        email = data.get("email")
        
        if not email:
            return jsonify({"success": False, "error": "Email required"}), 400
        
        # Find user by email in session_id (email is stored in session_id for demo)
        user = User.query.filter_by(session_id=email).first()
        
        if not user:
            # New user - return empty stats
            return jsonify({
                "success": True,
                "total_orders": 0,
                "total_spent": 0.0,
                "total_items": 0,
                "avg_order": 0.0,
                "recent_orders": []
            })
        
        # Query user's orders
        orders = Order.query.filter_by(user_id=user.id).order_by(Order.created_at.desc()).all()
        
        total_orders = len(orders)
        total_spent = sum(float(order.total_amount) for order in orders)
        total_items = sum(order.item_count for order in orders)
        avg_order = total_spent / total_orders if total_orders > 0 else 0.0
        
        # Get recent orders (last 5)
        recent_orders = []
        for order in orders[:5]:
            # Get items for this order
            items = OrderItem.query.filter_by(order_id=order.id).all()
            order_items = [
                {
                    "product_title": item.product_title,
                    "quantity": item.quantity,
                    "unit_price": float(item.unit_price),
                    "line_total": float(item.line_total)
                }
                for item in items
            ]
            
            recent_orders.append({
                "order_id": order.id,
                "created_at": order.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                "total_amount": float(order.total_amount),
                "item_count": order.item_count,
                "items": order_items
            })
        
        return jsonify({
            "success": True,
            "total_orders": total_orders,
            "total_spent": round(total_spent, 2),
            "total_items": total_items,
            "avg_order": round(avg_order, 2),
            "recent_orders": recent_orders
        })
        
    except Exception as e:
        print(f"User stats error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/track-event", methods=["POST"])
def track_event():
    """
    Track user interactions (cart_add, cart_remove, view) for model training
    """
    try:
        data = request.json
        # Use session_id pattern like the rest of the code
        if 'user_session' not in session:
            session['user_session'] = str(uuid.uuid4())
        session_id = session['user_session']
        
        user = User.query.filter_by(session_id=session_id).first()
        if not user:
            # Auto-create user record for anonymous tracking
            user = User(session_id=session_id)
            db.session.add(user)
            db.session.commit()
        
        event_type = data.get('event_type')  # 'cart_add', 'cart_remove', 'view'
        product_id = data.get('product_id')
        
        if not event_type or not product_id:
            return jsonify({"success": False, "error": "Missing event_type or product_id"}), 400
        
        # Convert product_id to integer for database lookup
        try:
            product_id = int(product_id)
        except (ValueError, TypeError):
            return jsonify({"success": False, "error": "Invalid product_id"}), 400
        
        # Get product details from in-memory DataFrame
        if product_id not in PRODUCTS_DF.index:
            return jsonify({"success": False, "error": "Product not found"}), 404
        
        product_row = PRODUCTS_DF.loc[product_id]
        product_title = str(product_row['Title'])
        product_subcat = str(product_row['Sub Category'])
        
        # Create event
        event = UserEvent(
            user_id=user.id,
            event_type=event_type,
            product_id=product_id,
            product_title=product_title,
            product_subcat=product_subcat,
            event_data=data.get('metadata', {})
        )
        db.session.add(event)
        db.session.commit()
        
        return jsonify({"success": True, "event_id": event.id})
        
    except Exception as e:
        db.session.rollback()
        print(f"Event tracking error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/isrec/intent", methods=["GET"])
def get_isrec_intent():
    """
    Get current ISRec intent detection results for display in UI
    """
    try:
        if 'user_session' not in session:
            session['user_session'] = str(uuid.uuid4())
        user_id = session['user_session']
        
        user = User.query.filter_by(session_id=user_id).first()
        if not user:
            return jsonify({
                "intent_score": 0.5,
                "mode": "balanced",
                "quality_signals": 0,
                "economy_signals": 0,
                "recent_actions": [],
                "message": "No activity yet"
            })
        
        # Get recent events (last 10 minutes)
        from datetime import datetime, timedelta
        cutoff = datetime.utcnow() - timedelta(minutes=10)
        recent_events = UserEvent.query.filter(
            UserEvent.user_id == user.id,
            UserEvent.created_at >= cutoff
        ).order_by(UserEvent.created_at.desc()).limit(10).all()
        
        # Calculate signals manually (mirror intent_detector logic)
        quality_score = 0.0
        economy_score = 0.0
        
        premium_keywords = ['organic', 'premium', 'grass-fed', 'free-range', 'artisan', 'imported', 'gourmet', 'specialty']
        budget_keywords = ['value', 'budget', 'saver', 'basic', 'everyday']
        
        for event in recent_events:
            product_id = event.product_id
            if product_id in PRODUCTS_DF.index:
                row = PRODUCTS_DF.loc[product_id]
                price = float(row.get("_price_final", 0))
                title_lower = str(row['Title']).lower()
                
                # Quality signals - only track cart_add and cart_remove
                is_premium = any(kw in title_lower for kw in premium_keywords)
                is_expensive = price > 25
                
                if event.event_type == 'cart_add':
                    if is_premium:
                        quality_score += 2.0
                    if is_expensive:
                        quality_score += 1.0
                elif event.event_type == 'cart_remove' and price < 15:
                    quality_score += 1.5
                
                # Economy signals - only track cart_add and cart_remove
                is_value = any(kw in title_lower for kw in budget_keywords)
                is_cheap = price < 10
                
                if event.event_type == 'cart_add':
                    if is_value:
                        economy_score += 2.0
                    if is_cheap:
                        economy_score += 1.5
                elif event.event_type == 'cart_remove' and price > 20:
                    economy_score += 2.0
        
        # Calculate intent score
        total = quality_score + economy_score
        intent_score = quality_score / total if total > 0 else 0.5
        
        # Determine mode (stricter thresholds for instant responsiveness)
        if intent_score > 0.65:
            mode = "quality"
        elif intent_score < 0.35:
            mode = "economy"
        else:
            mode = "balanced"
        
        # Format recent actions for display
        actions_list = []
        for event in recent_events[:5]:  # Show last 5
            if event.product_id in PRODUCTS_DF.index:
                row = PRODUCTS_DF.loc[event.product_id]
                actions_list.append({
                    "type": event.event_type,
                    "product": str(row['Title'])[:40] + "...",
                    "price": float(row.get("_price_final", 0)),
                    "timestamp": event.created_at.strftime("%H:%M:%S")
                })
        
        return jsonify({
            "intent_score": round(intent_score, 2),
            "mode": mode,
            "quality_signals": round(quality_score, 1),
            "economy_signals": round(economy_score, 1),
            "recent_actions": actions_list,
            "message": f"Analyzed {len(recent_events)} actions in last 10 min"
        })
        
    except Exception as e:
        print(f"ISRec intent error: {e}")
        return jsonify({
            "intent_score": 0.5,
            "mode": "balanced",
            "quality_signals": 0,
            "economy_signals": 0,
            "recent_actions": [],
            "message": f"Error: {str(e)}"
        }), 500

@app.route("/api/model/retrain", methods=["POST"])
def retrain_model():
    """
    Trigger model retraining with fresh data from database
    """
    try:
        import subprocess
        import threading
        
        # Check if retraining is already in progress
        if hasattr(app, '_retrain_in_progress') and app._retrain_in_progress:
            return jsonify({"success": False, "error": "Retraining already in progress"}), 429
        
        def background_retrain():
            try:
                app._retrain_in_progress = True
                print("\n🎓 Starting model retraining...")
                
                # Step 1: Export fresh training data from database
                result1 = subprocess.run(
                    ['python', 'prepare_ltr_data.py'],
                    capture_output=True,
                    text=True,
                    timeout=120
                )
                print("Export result:", result1.stdout if result1.returncode == 0 else result1.stderr)
                
                if result1.returncode != 0:
                    print(f"❌ Data export failed: {result1.stderr}")
                    return
                
                # Step 2: Train new model
                result2 = subprocess.run(
                    ['python', 'train_lgbm_ranker.py'],
                    capture_output=True,
                    text=True,
                    timeout=300
                )
                print("Training result:", result2.stdout if result2.returncode == 0 else result2.stderr)
                
                if result2.returncode == 0:
                    print("✅ Model retrained successfully! Reloading...")
                    # Reload the model in the recommendation system
                    from lgbm_reranker import reranker
                    reranker.reload_model()
                else:
                    print(f"❌ Training failed: {result2.stderr}")
                    
            except Exception as e:
                print(f"❌ Retrain error: {e}")
            finally:
                app._retrain_in_progress = False
        
        # Start background thread
        thread = threading.Thread(target=background_retrain, daemon=True)
        thread.start()
        
        return jsonify({
            "success": True,
            "message": "Model retraining started in background",
            "status": "in_progress"
        })
        
    except Exception as e:
        print(f"Retrain trigger error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

# ==================== REPLENISHMENT SYSTEM API ENDPOINTS ====================

from replenishment_engine import ReplenishmentEngine
import openai
import os

# Initialize OpenAI for LLM-powered recommendation messages
openai.api_key = os.environ.get("OPENAI_API_KEY")

def generate_llm_recommendation_message(intent_score: float, product_name: str, original_product: str, savings: float, discount_pct: int) -> str:
    """
    Generate personalized recommendation message using LLM based on ISRec intent.
    Messages adapt to user's shopping mode (quality vs economy) detected by ISRec.
    
    Args:
        intent_score: 0.0-1.0 (0=economy-focused, 1=quality-focused)
        product_name: Recommended product
        original_product: Original product being replaced
        savings: Dollar amount saved
        discount_pct: Percentage cheaper
    
    Returns:
        Natural language message adapted to shopping mode
    """
    # Debug: Log intent detection for message generation
    mode = "quality" if intent_score >= 0.6 else "economy" if intent_score <= 0.4 else "balanced"
    print(f"🎨 Generating message: Intent={intent_score:.2f} ({mode}), Product='{product_name[:30]}', Save=${savings:.2f}")
    
    try:
        # Adapt message style based on detected shopping intent
        if intent_score >= 0.6:
            # Quality mode - user cares about maintaining standards
            system_prompt = "You help premium shoppers. Write ONE short sentence (max 8 words) about why this product maintains their quality standards. Be factual, not salesy."
            user_prompt = f"Suggest '{product_name}' as alternative to '{original_product}'. Focus on quality/premium aspects only."
        elif intent_score <= 0.4:
            # Economy mode - user cares about savings
            system_prompt = "You help budget shoppers. Write ONE short sentence (max 8 words) about the savings. Be factual, not salesy."
            user_prompt = f"Suggest '{product_name}' instead of '{original_product}'. Saves ${savings:.2f}. Focus on savings only."
        else:
            # Balanced mode - user cares about both
            system_prompt = "You help smart shoppers. Write ONE short sentence (max 8 words) about quality AND value. Be factual, not salesy."
            user_prompt = f"Suggest '{product_name}' instead of '{original_product}'. Saves ${savings:.2f}. Mention both quality and savings."
        
        # Call LLM with clearer, more focused prompts
        response = openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.5,  # Lower temperature for more consistent, less creative output
            max_tokens=20
        )
        
        message = response.choices[0].message.content.strip()
        # Remove quotes if LLM added them
        message = message.strip('"').strip("'")
        print(f"✅ LLM generated: '{message}'")
        return message
    
    except Exception as e:
        # Fallback templates if LLM fails
        print(f"⚠️ LLM generation failed: {e}")
        if intent_score >= 0.6:
            return f"Maintains quality, saves ${savings:.2f}"
        elif intent_score <= 0.4:
            return f"Save ${savings:.2f} ({discount_pct}% off)"
        else:
            return f"Quality choice, saves ${savings:.2f}"

@app.route("/api/replenishment/due-soon", methods=["GET"])
def get_replenishment_due_soon():
    """
    Get top 10 most urgent replenishment opportunities based on urgency scoring.
    Includes both established cycles (2+ purchases) and first-purchase predictions.
    Returns: {due_now: [...], due_soon: [...], upcoming: [...], total_active_cycles: N}
    """
    try:
        # Get or create user
        session_id = session.get('user_session')
        if not session_id:
            session_id = str(uuid.uuid4())
            session['user_session'] = session_id
        
        user = User.query.filter_by(session_id=session_id).first()
        if not user:
            user = User(session_id=session_id)
            db.session.add(user)
            db.session.commit()
        
        if not user:
            return jsonify({
                "due_now": [],
                "due_soon": [],
                "upcoming": [],
                "total_active_cycles": 0,
                "message": "No purchase history yet"
            })
        
        # Get top 10 replenishment opportunities using new urgency-based ranking
        engine = ReplenishmentEngine(
            db=db, 
            products_df=PRODUCTS_DF,
            Order=Order,
            OrderItem=OrderItem,
            ReplenishableProduct=ReplenishableProduct,
            UserReplenishmentCycle=UserReplenishmentCycle
        )
        
        opportunities = engine.get_top_replenishment_opportunities(
            user_id=user.id,  # Pass numeric user.id instead of session_id
            top_k=10
        )
        
        # Categorize by urgency
        due_now = []
        due_soon = []
        upcoming = []
        
        for opp in opportunities:
            item = {
                "product_id": opp['product_id'],
                "title": opp['title'],
                "subcat": opp['subcat'],
                "price": opp['price'],
                "interval_days": opp['predicted_interval'],
                "last_purchase": opp['last_purchase'],
                "days_since_purchase": opp['days_since_purchase'],
                "days_until_due": opp['days_until_due'],
                "purchase_count": opp['purchase_count'],
                "urgency_score": opp['urgency_score'],
                "prediction_type": opp['prediction_type'],  # 'personalized' or 'predicted'
                "cf_confidence": opp['cf_confidence']
            }
            
            # Categorize based on days until due
            # Due Now: 0-3 days (overdue or due very soon)
            # Due Soon: 4-7 days  
            # Upcoming: 7+ days
            if item["days_until_due"] <= 3:
                due_now.append(item)
            elif item["days_until_due"] <= 7:
                due_soon.append(item)
            else:
                upcoming.append(item)
        
        # Get total count of tracked products (for stats)
        total_tracked = len(opportunities)
        
        return jsonify({
            "due_now": due_now,
            "due_soon": due_soon,
            "upcoming": upcoming,
            "total_active_cycles": total_tracked,
            "message": f"Top {total_tracked} replenishment opportunities (urgency-ranked)"
        })
        
    except Exception as e:
        print(f"Replenishment due-soon error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route("/api/replenishment/bundles", methods=["GET"])
def get_replenishment_bundles():
    """
    Get bundled product recommendations for grouped restocking
    """
    try:
        session_id = session.get('user_session')
        if not session_id:
            return jsonify({"bundles": []})
        
        user = User.query.filter_by(session_id=session_id).first()
        if not user:
            return jsonify({"bundles": []})
        
        # Initialize replenishment engine
        engine = ReplenishmentEngine(db, PRODUCTS_DF, Order, OrderItem, ReplenishableProduct, UserReplenishmentCycle)
        
        # Get bundles
        window_days = int(request.args.get('window_days', 3))
        bundles = engine.get_bundled_reminders(user.id, window_days=window_days)
        
        return jsonify({"bundles": bundles})
        
    except Exception as e:
        print(f"Replenishment bundles error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/api/replenishment/quick-add", methods=["POST"])
def quick_add_replenishment():
    """
    Quickly add a replenishment item to cart
    Body: {cycle_id: int}
    """
    try:
        data = request.get_json()
        cycle_id = data.get('cycle_id')
        
        if not cycle_id:
            return jsonify({"success": False, "error": "cycle_id required"}), 400
        
        # Get the cycle
        cycle = UserReplenishmentCycle.query.get(cycle_id)
        if not cycle:
            return jsonify({"success": False, "error": "Cycle not found"}), 404
        
        # Get session
        session_id = session.get('user_session')
        if not session_id:
            return jsonify({"success": False, "error": "No session"}), 400
        
        # Add to cart (check if already in cart)
        existing = ShoppingCart.query.filter_by(
            session_id=session_id,
            product_id=cycle.product_id
        ).first()
        
        if existing:
            existing.quantity += 1
        else:
            new_item = ShoppingCart(
                session_id=session_id,
                product_id=cycle.product_id,
                quantity=1
            )
            db.session.add(new_item)
        
        db.session.commit()
        
        return jsonify({
            "success": True,
            "product_id": str(cycle.product_id),
            "title": cycle.product_title
        })
        
    except Exception as e:
        print(f"Quick-add error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/replenishment/skip", methods=["POST"])
def skip_replenishment():
    """
    Skip a replenishment reminder for N days
    Body: {cycle_id: int, skip_days: int}
    """
    try:
        data = request.get_json()
        cycle_id = data.get('cycle_id')
        skip_days = data.get('skip_days', 7)
        
        if not cycle_id:
            return jsonify({"success": False, "error": "cycle_id required"}), 400
        
        cycle = UserReplenishmentCycle.query.get(cycle_id)
        if not cycle:
            return jsonify({"success": False, "error": "Cycle not found"}), 404
        
        # Set skip_until_date
        from datetime import date, timedelta
        cycle.skip_until_date = date.today() + timedelta(days=skip_days)
        db.session.commit()
        
        return jsonify({
            "success": True,
            "skip_until": cycle.skip_until_date.strftime('%Y-%m-%d')
        })
        
    except Exception as e:
        print(f"Skip replenishment error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/replenishment/refresh-cycles", methods=["POST"])
def refresh_replenishment_cycles():
    """
    Manually trigger replenishment cycle calculation for current user
    """
    try:
        session_id = session.get('user_session')
        if not session_id:
            return jsonify({"success": False, "error": "No session"}), 400
        
        user = User.query.filter_by(session_id=session_id).first()
        if not user:
            return jsonify({"success": False, "error": "User not found"}), 404
        
        # Initialize replenishment engine
        engine = ReplenishmentEngine(db, PRODUCTS_DF, Order, OrderItem, ReplenishableProduct, UserReplenishmentCycle)
        
        # Identify replenishable products first
        engine.identify_replenishable_products(min_purchases=2, min_users=1)
        
        # Calculate user-specific cycles
        cycles_updated = engine.calculate_user_cycles(user.id)
        
        return jsonify({
            "success": True,
            "cycles_updated": cycles_updated,
            "message": f"Updated {cycles_updated} replenishment cycles"
        })
        
    except Exception as e:
        print(f"Refresh cycles error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/analytics/track-interaction", methods=["POST"])
def track_interaction():
    """
    Track user interaction with AI recommendations for behavioral analytics.
    
    Expected payload:
    {
        "recommendation_id": "rec_123",
        "action_type": "shown" | "accept" | "dismiss" | "cart_removal",
        "original_product": {"id": "123", "title": "...", "price": 10.99, ...},
        "recommended_product": {"id": "456", "title": "...", "price": 8.99, ...},
        "expected_saving": "2.00",
        "recommendation_reason": "...",
        "has_explanation": true,
        "shown_at": "2025-11-17T10:30:00Z",
        "action_at": "2025-11-17T10:30:15Z",  # optional, for accept/dismiss
        "scroll_depth_percent": 75,  # optional
        "was_removed": false  # optional, for cart_removal tracking
    }
    """
    try:
        data = request.get_json(force=True)
        
        # Validate required fields
        required_fields = ["recommendation_id", "action_type"]
        for field in required_fields:
            if field not in data:
                return jsonify({"success": False, "error": f"Missing required field: {field}"}), 400
        
        recommendation_id = data.get("recommendation_id")
        action_type = data.get("action_type")
        
        # Validate action_type
        valid_actions = ["shown", "accept", "dismiss", "cart_removal"]
        if action_type not in valid_actions:
            return jsonify({"success": False, "error": f"Invalid action_type. Must be one of: {valid_actions}"}), 400
        
        # Get or create session_id
        if 'user_session' not in session:
            session['user_session'] = str(uuid.uuid4())
        session_id = session['user_session']
        
        # Find or create user
        user = User.query.filter_by(session_id=session_id).first()
        if not user:
            user = User(session_id=session_id)
            db.session.add(user)
            db.session.flush()
        
        # Extract product information
        original_product = data.get("original_product", {})
        recommended_product = data.get("recommended_product", {})
        
        # Validate product data
        if not original_product.get("id") or not recommended_product.get("id"):
            return jsonify({"success": False, "error": "Missing product IDs"}), 400
        
        # Parse timestamps
        from datetime import datetime
        shown_at = None
        action_at = None
        time_to_action_seconds = None
        
        if data.get("shown_at"):
            try:
                shown_at = datetime.fromisoformat(data["shown_at"].replace('Z', '+00:00'))
            except Exception as e:
                print(f"Error parsing shown_at: {e}")
        
        if data.get("action_at"):
            try:
                action_at = datetime.fromisoformat(data["action_at"].replace('Z', '+00:00'))
                # Calculate time_to_action if both timestamps available
                if shown_at and action_at:
                    time_to_action_seconds = int((action_at - shown_at).total_seconds())
            except Exception as e:
                print(f"Error parsing action_at: {e}")
        
        # Helper function to safely extract nutrition value
        def get_nutrition_value(product_dict, field_name, is_int=False):
            """Extract nutrition value, returning None if missing or null"""
            nutrition = product_dict.get("nutrition")
            if not nutrition:
                return None
            value = nutrition.get(field_name)
            if value is None:
                return None
            try:
                return int(value) if is_int else float(value)
            except (ValueError, TypeError):
                return None
        
        # Create interaction record
        interaction = RecommendationInteraction(
            user_id=user.id,
            recommendation_id=recommendation_id,
            action_type=action_type,
            
            # Product IDs and titles
            original_product_id=int(original_product.get("id")),
            recommended_product_id=int(recommended_product.get("id")),
            original_product_title=original_product.get("title", ""),
            recommended_product_title=recommended_product.get("title", ""),
            
            # Recommendation details
            expected_saving=float(data.get("expected_saving", 0.0)),
            recommendation_reason=data.get("recommendation_reason", ""),
            has_explanation=data.get("has_explanation", True),
            
            # Timing
            shown_at=shown_at or db.func.current_timestamp(),
            action_at=action_at,
            time_to_action_seconds=time_to_action_seconds,
            scroll_depth_percent=data.get("scroll_depth_percent"),
            
            # Product attributes (from original product) - Use None for missing data
            original_price=float(original_product.get("price", 0.0)),
            original_protein=get_nutrition_value(original_product, "Protein_g"),
            original_sugar=get_nutrition_value(original_product, "Sugar_g"),
            original_calories=get_nutrition_value(original_product, "Calories", is_int=True),
            original_sodium=get_nutrition_value(original_product, "Sodium_mg"),
            
            # Product attributes (from recommended product) - Use None for missing data
            recommended_price=float(recommended_product.get("price", 0.0)),
            recommended_protein=get_nutrition_value(recommended_product, "Protein_g"),
            recommended_sugar=get_nutrition_value(recommended_product, "Sugar_g"),
            recommended_calories=get_nutrition_value(recommended_product, "Calories", is_int=True),
            recommended_sodium=get_nutrition_value(recommended_product, "Sodium_mg"),
            
            # Removal tracking
            was_removed=data.get("was_removed", False),
            removed_from_cart_at=action_at if action_type == "cart_removal" else None
        )
        
        db.session.add(interaction)
        db.session.commit()
        
        return jsonify({
            "success": True,
            "interaction_id": interaction.id,
            "user_id": user.session_id
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"Track interaction error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/analytics/metrics", methods=["GET"])
def get_analytics_metrics():
    """
    Get behavioral analytics metrics for recommendations.
    
    Query params:
    - user_id (optional): Filter by specific session_id
    - period (optional): "7d" | "30d" | "all" (default: "all")
    
    Returns 9 key metrics:
    - RAR (Replace Action Rate)
    - ACR (Action to Cart Rate)
    - Time-to-Accept
    - Average Scroll Depth
    - BCR (Basket Change Rate)
    - Dismiss Rate
    - Removal Rate
    - BDS (Behavioral Drift Score)
    - EAS (Explanation Acceptance Score)
    
    Note: HGAB metric has been removed.
    """
    try:
        # Get query parameters
        user_session_id = request.args.get("user_id")
        period = request.args.get("period", "all")
        
        # Build base query
        query = RecommendationInteraction.query
        
        # Filter by user if specified
        if user_session_id:
            user = User.query.filter_by(session_id=user_session_id).first()
            if user:
                query = query.filter_by(user_id=user.id)
            else:
                return jsonify({"success": False, "error": "User not found"}), 404
        
        # Filter by time period
        from datetime import datetime, timedelta
        if period == "7d":
            cutoff = datetime.utcnow() - timedelta(days=7)
            query = query.filter(RecommendationInteraction.shown_at >= cutoff)
        elif period == "30d":
            cutoff = datetime.utcnow() - timedelta(days=30)
            query = query.filter(RecommendationInteraction.shown_at >= cutoff)
        
        # Get all interactions
        all_interactions = query.all()
        
        # Calculate counts for each action type
        shown_count = sum(1 for i in all_interactions if i.action_type == "shown")
        accept_count = sum(1 for i in all_interactions if i.action_type == "accept")
        dismiss_count = sum(1 for i in all_interactions if i.action_type == "dismiss")
        removal_count = sum(1 for i in all_interactions if i.action_type == "cart_removal")
        
        # Calculate metrics with division by zero protection
        
        # 1. RAR (Replace Action Rate) = (# of "accept" actions) / (# of recommendations shown) * 100
        rar = (accept_count / shown_count * 100) if shown_count > 0 else 0.0
        
        # 2. ACR (Action to Cart Rate) = (# of "accept" actions) / (# of recommendations shown) * 100
        # Note: ACR is the same as RAR in this context
        acr = (accept_count / shown_count * 100) if shown_count > 0 else 0.0
        
        # 3. Time-to-Accept = Average time_to_action_seconds for "accept" actions
        accept_interactions = [i for i in all_interactions if i.action_type == "accept" and i.time_to_action_seconds is not None]
        time_to_accept = sum(i.time_to_action_seconds for i in accept_interactions) / len(accept_interactions) if accept_interactions else 0.0
        
        # 4. Average Scroll Depth = Mean scroll_depth_percent across all interactions
        interactions_with_scroll = [i for i in all_interactions if i.scroll_depth_percent is not None]
        avg_scroll_depth = sum(i.scroll_depth_percent for i in interactions_with_scroll) / len(interactions_with_scroll) if interactions_with_scroll else 0.0
        
        # 5. BCR (Basket Change Rate) = (# of items removed after recommendation) / (# of accepted recommendations) * 100
        removed_after_accept = sum(1 for i in all_interactions if i.was_removed)
        bcr = (removed_after_accept / accept_count * 100) if accept_count > 0 else 0.0
        
        # 6. Dismiss Rate = (# of "dismiss" actions) / (# of recommendations shown) * 100
        dismiss_rate = (dismiss_count / shown_count * 100) if shown_count > 0 else 0.0
        
        # 7. Removal Rate = (# of cart_removal events) / (# of accepted recommendations) * 100
        removal_rate = (removal_count / accept_count * 100) if accept_count > 0 else 0.0
        
        # 8. BDS (Behavioral Drift Score) - Detect shifts in user preferences over time
        bds_data = {
            "drift_score": 0.0,
            "drift_level": "Low drift",
            "attribute_drifts": {
                "protein_drift": 0.0,
                "sugar_drift": 0.0,
                "calories_drift": 0.0,
                "price_drift": 0.0
            },
            "sample_size": 0
        }
        
        # Get all "accept" interactions with product attributes, sorted by timestamp
        accept_with_attrs = [
            i for i in all_interactions 
            if i.action_type == "accept" 
            and i.recommended_protein is not None 
            and i.recommended_sugar is not None
            and i.recommended_calories is not None
            and i.recommended_price is not None
        ]
        
        if len(accept_with_attrs) >= 4:
            # Sort by timestamp
            accept_with_attrs.sort(key=lambda x: x.shown_at)
            
            # Split into first half and second half
            mid_point = len(accept_with_attrs) // 2
            first_half = accept_with_attrs[:mid_point]
            second_half = accept_with_attrs[mid_point:]
            
            # Calculate average attributes for each half
            def calc_avg(interactions, attr_name):
                values = [getattr(i, attr_name) for i in interactions if getattr(i, attr_name) is not None]
                return sum(float(v) for v in values) / len(values) if values else 0.0
            
            # First half averages
            first_protein = calc_avg(first_half, 'recommended_protein')
            first_sugar = calc_avg(first_half, 'recommended_sugar')
            first_calories = calc_avg(first_half, 'recommended_calories')
            first_price = calc_avg(first_half, 'recommended_price')
            
            # Second half averages
            second_protein = calc_avg(second_half, 'recommended_protein')
            second_sugar = calc_avg(second_half, 'recommended_sugar')
            second_calories = calc_avg(second_half, 'recommended_calories')
            second_price = calc_avg(second_half, 'recommended_price')
            
            # Calculate drifts (normalized by dividing by typical values to make them comparable)
            protein_drift = (second_protein - first_protein) / 10.0 if first_protein > 0 else 0.0
            sugar_drift = (second_sugar - first_sugar) / 10.0 if first_sugar > 0 else 0.0
            calories_drift = (second_calories - first_calories) / 100.0 if first_calories > 0 else 0.0
            price_drift = (second_price - first_price) / 10.0 if first_price > 0 else 0.0
            
            # Compute overall drift score: sqrt(sum of squared drifts) / 4
            import math
            drift_score = math.sqrt(
                protein_drift**2 + sugar_drift**2 + calories_drift**2 + price_drift**2
            ) / 4.0
            
            # Interpret drift level
            if drift_score > 0.15:
                drift_level = "High drift"
            elif drift_score >= 0.05:
                drift_level = "Moderate drift"
            else:
                drift_level = "Low drift"
            
            bds_data = {
                "drift_score": round(drift_score, 4),
                "drift_level": drift_level,
                "attribute_drifts": {
                    "protein_drift": round(protein_drift, 4),
                    "sugar_drift": round(sugar_drift, 4),
                    "calories_drift": round(calories_drift, 4),
                    "price_drift": round(price_drift, 4)
                },
                "sample_size": len(accept_with_attrs)
            }
        
        # 9. EAS (Explanation Acceptance Score) - Compare acceptance rates with/without explanations
        eas_data = {
            "acceptance_with_explanation": 0.0,
            "acceptance_without_explanation": 0.0,
            "explanation_lift_percent": 0.0,
            "with_explanation_count": 0,
            "without_explanation_count": 0
        }
        
        # Group interactions by has_explanation
        with_explanation = [i for i in all_interactions if i.has_explanation]
        without_explanation = [i for i in all_interactions if not i.has_explanation]
        
        # Calculate acceptance rates for each group
        with_expl_shown = sum(1 for i in with_explanation if i.action_type == "shown")
        with_expl_accept = sum(1 for i in with_explanation if i.action_type == "accept")
        
        without_expl_shown = sum(1 for i in without_explanation if i.action_type == "shown")
        without_expl_accept = sum(1 for i in without_explanation if i.action_type == "accept")
        
        acceptance_with = (with_expl_accept / with_expl_shown * 100) if with_expl_shown > 0 else 0.0
        acceptance_without = (without_expl_accept / without_expl_shown * 100) if without_expl_shown > 0 else 0.0
        
        # Calculate lift
        explanation_lift = acceptance_with - acceptance_without
        
        eas_data = {
            "acceptance_with_explanation": round(acceptance_with, 2),
            "acceptance_without_explanation": round(acceptance_without, 2),
            "explanation_lift_percent": round(explanation_lift, 2),
            "with_explanation_count": with_expl_shown,
            "without_explanation_count": without_expl_shown
        }
        
        return jsonify({
            "success": True,
            "period": period,
            "user_id": user_session_id,
            "metrics": {
                "rar": round(rar, 2),
                "acr": round(acr, 2),
                "time_to_accept_seconds": round(time_to_accept, 2),
                "avg_scroll_depth_percent": round(avg_scroll_depth, 2),
                "bcr": round(bcr, 2),
                "dismiss_rate": round(dismiss_rate, 2),
                "removal_rate": round(removal_rate, 2),
                "bds": bds_data,
                "eas": eas_data
            },
            "counts": {
                "total_interactions": len(all_interactions),
                "shown": shown_count,
                "accepted": accept_count,
                "dismissed": dismiss_count,
                "removed": removal_count,
                "removed_after_accept": removed_after_accept
            }
        })
        
    except Exception as e:
        print(f"Analytics metrics error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500

import json
from datetime import datetime

llm_insights_cache = {}

@app.route("/api/analytics/llm-insights", methods=["GET"])
def get_llm_insights():
    """
    Get LLM-powered insights for behavioral analytics metrics.
    Uses OpenAI GPT-4o-mini to analyze recommendation system performance.
    
    Query params:
    - user_id (optional): Filter by specific session_id
    - period (optional): "7d" | "30d" | "all" (default: "all")
    
    Returns:
    - overall_score: Performance score (1-10)
    - strengths: Array of what's working well
    - weaknesses: Array of problem areas
    - recommendations: Array of actionable suggestions with priority levels
    - summary: Brief overview paragraph
    """
    try:
        user_session_id = request.args.get("user_id")
        period = request.args.get("period", "all")
        
        cache_key = f"{user_session_id}_{period}"
        
        if cache_key in llm_insights_cache:
            cached_result, cached_time = llm_insights_cache[cache_key]
            cache_age = (datetime.utcnow() - cached_time).total_seconds()
            if cache_age < 300:
                return jsonify({
                    "success": True,
                    "cached": True,
                    "cache_age_seconds": int(cache_age),
                    **cached_result
                })
        
        metrics_response = get_analytics_metrics()
        metrics_data = metrics_response.get_json()
        
        if not metrics_data.get("success"):
            return jsonify({
                "success": False,
                "error": "Failed to fetch metrics data"
            }), 500
        
        metrics = metrics_data["metrics"]
        counts = metrics_data["counts"]
        
        if counts["total_interactions"] == 0:
            return jsonify({
                "success": False,
                "error": "No analytics data available yet. Start shopping and interacting with recommendations to generate insights."
            }), 400
        
        import openai
        openai.api_key = os.environ.get("OPENAI_API_KEY")
        
        if not openai.api_key:
            return jsonify({
                "success": False,
                "error": "OpenAI API key not configured. Please set OPENAI_API_KEY environment variable."
            }), 500
        
        prompt = f"""You are an expert analyst for AI-powered recommendation systems in e-commerce, specifically grocery shopping platforms.

Analyze these behavioral metrics from an AI grocery shopping assistant that provides personalized product recommendations:

CURRENT METRICS:
1. RAR (Replace Action Rate): {metrics['rar']}%
   Definition: Percentage of shown recommendations that users accept
   Industry Benchmark: Good = >20%, Excellent = >30%

2. ACR (Action to Cart Rate): {metrics['acr']}%
   Definition: Percentage of recommendations that lead to cart additions
   Industry Benchmark: Good = >15%, Excellent = >25%

3. Time-to-Accept: {metrics['time_to_accept_seconds']} seconds
   Definition: Average time users take to accept a recommendation
   Industry Benchmark: Good = <5s, Excellent = <3s (faster indicates more relevant recommendations)

4. Average Scroll Depth: {metrics['avg_scroll_depth_percent']}%
   Definition: How far users scroll through recommendation lists
   Industry Benchmark: Good = >50%, Excellent = >70% (higher engagement)

5. BCR (Basket Change Rate): {metrics['bcr']}%
   Definition: Percentage of accepted recommendations later removed from cart
   Industry Benchmark: Good = <20%, Excellent = <10% (lower is better - indicates quality recommendations)

6. Dismiss Rate: {metrics['dismiss_rate']}%
   Definition: Percentage of recommendations explicitly rejected by users
   Industry Benchmark: Good = <40%, Excellent = <25% (lower is better)

7. Removal Rate: {metrics['removal_rate']}%
   Definition: Percentage of cart items removed before checkout
   Industry Benchmark: Good = <30%, Excellent = <15% (lower is better)

8. BDS (Behavioral Drift Score): {metrics['bds']['drift_score']}
   Level: {metrics['bds']['drift_level']}
   Protein Drift: {metrics['bds']['attribute_drifts']['protein_drift']}
   Sugar Drift: {metrics['bds']['attribute_drifts']['sugar_drift']}
   Calories Drift: {metrics['bds']['attribute_drifts']['calories_drift']}
   Price Drift: {metrics['bds']['attribute_drifts']['price_drift']}
   Sample Size: {metrics['bds']['sample_size']} accepted recommendations
   Definition: Measures changes in user preferences over time
   Industry Context: Low drift = stable preferences, High drift = evolving tastes or poor initial recommendations

9. EAS (Explanation Acceptance Score): {metrics['eas']['explanation_lift_percent']}%
   With Explanation: {metrics['eas']['acceptance_with_explanation']}% ({metrics['eas']['with_explanation_count']} shown)
   Without Explanation: {metrics['eas']['acceptance_without_explanation']}% ({metrics['eas']['without_explanation_count']} shown)
   Definition: Impact of showing explanations on acceptance rates
   Industry Benchmark: Good lift = >5%, Excellent lift = >15%

INTERACTION COUNTS:
- Total interactions: {counts['total_interactions']}
- Recommendations shown: {counts['shown']}
- Accepted: {counts['accepted']}
- Dismissed: {counts['dismissed']}
- Removed from cart: {counts['removed']}

TIME PERIOD: {period}
{f"USER: {user_session_id}" if user_session_id else "ALL USERS"}

TASK:
Provide a comprehensive analysis of this recommendation system's performance. Consider:
1. Which metrics are performing well vs. poorly compared to industry benchmarks
2. Patterns and relationships between metrics (e.g., high dismiss rate + low RAR = relevance problem)
3. Specific, actionable recommendations prioritized by potential impact
4. Overall system health and areas needing immediate attention

Return ONLY a valid JSON object with this exact structure:
{{
  "overall_score": <number 1-10>,
  "strengths": ["<strength 1>", "<strength 2>", "<strength 3>"],
  "weaknesses": ["<weakness 1>", "<weakness 2>", "<weakness 3>"],
  "recommendations": [
    {{"text": "<actionable recommendation>", "priority": "High"}},
    {{"text": "<actionable recommendation>", "priority": "High"}},
    {{"text": "<actionable recommendation>", "priority": "Medium"}},
    {{"text": "<actionable recommendation>", "priority": "Medium"}},
    {{"text": "<actionable recommendation>", "priority": "Low"}}
  ],
  "summary": "<2-3 sentence overview of overall system performance>"
}}

Ensure your response is valid JSON only, with no additional text."""

        try:
            from openai import OpenAI
            client = OpenAI(api_key=openai.api_key)
            
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are an expert analyst for AI recommendation systems. You provide structured, data-driven insights in JSON format only."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=1500,
                response_format={"type": "json_object"}
            )
            
            llm_response_text = response.choices[0].message.content
            llm_insights = json.loads(llm_response_text)
            
            result = {
                "overall_score": llm_insights.get("overall_score", 5),
                "strengths": llm_insights.get("strengths", []),
                "weaknesses": llm_insights.get("weaknesses", []),
                "recommendations": llm_insights.get("recommendations", []),
                "summary": llm_insights.get("summary", "Analysis completed successfully."),
                "metrics_snapshot": {
                    "rar": metrics['rar'],
                    "acr": metrics['acr'],
                    "bcr": metrics['bcr'],
                    "dismiss_rate": metrics['dismiss_rate']
                }
            }
            
            llm_insights_cache[cache_key] = (result, datetime.utcnow())
            
            return jsonify({
                "success": True,
                "cached": False,
                **result
            })
            
        except openai.RateLimitError:
            return jsonify({
                "success": False,
                "error": "OpenAI API rate limit reached. Please try again in a few moments."
            }), 429
            
        except openai.APIError as e:
            return jsonify({
                "success": False,
                "error": f"OpenAI API error: {str(e)}"
            }), 500
            
        except json.JSONDecodeError:
            return jsonify({
                "success": False,
                "error": "Failed to parse LLM response. Please try again."
            }), 500
            
    except Exception as e:
        print(f"LLM insights error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": f"Unexpected error: {str(e)}"
        }), 500

@app.route("/static/<path:filename>")
def static_files(filename):
    return send_from_directory('static', filename)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/analytics")
def analytics():
    """Analytics dashboard to visualize all behavioral metrics"""
    return render_template("analytics.html")

if __name__ == "__main__":
    # For Replit, host=0.0.0.0 is typical
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")), debug=True)