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
Product, ShoppingCart, UserBudget, User, Order, OrderItem, UserEvent, ReplenishableProduct, UserReplenishmentCycle = init_models(db)

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
        current_intent = intent_detector.detect_intent(user_id, cart, db.session)
        
        # Map ISRec intent to guardrail mode
        if current_intent >= 0.6:
            guardrail_mode = 'quality'
            mode_label = "Quality mode"
        elif current_intent <= 0.4:
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
    Sign in a user by setting their email as the session_id
    This allows the backend to track purchases by email
    """
    try:
        data = request.get_json(force=True)
        email = data.get("email")
        
        if not email:
            return jsonify({"success": False, "error": "Email required"}), 400
        
        # Set the session to use email as session_id (for demo purposes)
        session['user_session'] = email
        
        return jsonify({"success": True, "message": "Signed in successfully"})
    except Exception as e:
        print(f"Sign-in error: {e}")
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
                
                # Quality signals
                is_premium = any(kw in title_lower for kw in premium_keywords)
                is_expensive = price > 25
                
                if event.event_type == 'view':
                    if is_premium:
                        quality_score += 1.0
                    if is_expensive:
                        quality_score += 0.5
                elif event.event_type == 'cart_add':
                    if is_premium:
                        quality_score += 2.0
                    if is_expensive:
                        quality_score += 1.0
                elif event.event_type == 'cart_remove' and price < 15:
                    quality_score += 1.5
                
                # Economy signals
                is_value = any(kw in title_lower for kw in budget_keywords)
                is_cheap = price < 10
                
                if event.event_type == 'view':
                    if is_value or is_cheap:
                        economy_score += 1.0
                elif event.event_type == 'cart_add':
                    if is_value:
                        economy_score += 2.0
                    if is_cheap:
                        economy_score += 1.5
                elif event.event_type == 'cart_remove' and price > 20:
                    economy_score += 2.0
        
        # Calculate intent score
        total = quality_score + economy_score
        intent_score = quality_score / total if total > 0 else 0.5
        
        # Determine mode
        if intent_score > 0.7:
            mode = "quality"
        elif intent_score < 0.3:
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
    Use LLM to generate natural, conversational recommendation message.
    Connects ISRec intent detection with product recommendations using AI.
    
    Args:
        intent_score: 0.0-1.0 (0=economy-focused, 1=quality-focused)
        product_name: Recommended product
        original_product: Original product being replaced
        savings: Dollar amount saved
        discount_pct: Percentage cheaper
    
    Returns:
        Natural, human-friendly message from AI (max 10 words)
    """
    try:
        # Determine user's shopping style from ISRec and set focus
        if intent_score >= 0.6:
            # Quality mode - emphasize maintaining quality while saving
            system_prompt = "You're a grocery assistant helping quality-focused shoppers. Generate a 10-word (maximum) recommendation emphasizing similar quality/premium while saving money. Be warm and conversational."
            focus = "Emphasize: same quality, just better price"
        elif intent_score <= 0.4:
            # Economy mode - emphasize maximum savings
            system_prompt = "You're a grocery assistant helping budget-conscious shoppers. Generate a 10-word (maximum) recommendation emphasizing great savings and value. Be warm and conversational."
            focus = "Emphasize: big savings, great deal"
        else:
            # Balanced mode
            system_prompt = "You're a grocery assistant. Generate a 10-word (maximum) recommendation balancing quality and price. Be warm and conversational."
            focus = "Emphasize: good balance of quality and savings"
        
        # Use GPT to generate natural message
        response = openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": system_prompt
                },
                {
                    "role": "user",
                    "content": f"Recommend '{product_name}' instead of '{original_product}'. Saves ${savings:.2f}. {focus}. Max 10 words!"
                }
            ],
            temperature=0.7,
            max_tokens=30
        )
        
        return response.choices[0].message.content.strip()
    
    except Exception as e:
        # Fallback to simple template if LLM fails
        print(f"LLM generation failed: {e}")
        if intent_score >= 0.6:
            return f"Same quality, saves ${savings:.2f}"
        elif intent_score <= 0.4:
            return f"Big savings: ${savings:.2f} off!"
        else:
            return f"Good value, saves ${savings:.2f}"

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

@app.route("/static/<path:filename>")
def static_files(filename):
    return send_from_directory('static', filename)

@app.route("/demo-login")
def demo_login():
    """
    QR code demo login endpoint.
    Generates a confirmation page that auto-logs in the user.
    """
    token = request.args.get('token', 'demo_unknown')
    
    # Return a simple confirmation page with auto-login script
    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Demo Login - AI Supermarket</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
        <style>
            body {{ font-family: 'Inter', system-ui, sans-serif; }}
        </style>
    </head>
    <body class="bg-gradient-to-br from-indigo-50 to-purple-50 min-h-screen flex items-center justify-center p-4">
        <div class="bg-white rounded-2xl shadow-2xl p-8 max-w-md w-full text-center">
            <!-- Success Icon -->
            <div class="mb-6">
                <div class="w-20 h-20 bg-green-100 rounded-full mx-auto flex items-center justify-center">
                    <svg class="w-12 h-12 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path>
                    </svg>
                </div>
            </div>
            
            <!-- Title -->
            <h1 class="text-3xl font-bold text-gray-900 mb-2">You're Signed In!</h1>
            <p class="text-gray-600 mb-6">Welcome to the AI Supermarket demo</p>
            
            <!-- User Info -->
            <div class="bg-gradient-to-r from-indigo-50 to-purple-50 rounded-xl p-4 mb-6">
                <p class="text-sm text-gray-600 mb-1">Signed in as</p>
                <p id="userName" class="text-lg font-bold text-indigo-600">Demo User</p>
            </div>
            
            <!-- Button -->
            <a href="/" class="inline-block w-full bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-700 hover:to-purple-700 text-white font-bold py-3 px-6 rounded-lg transition-all transform hover:scale-105 shadow-lg">
                Open on Tablet
            </a>
            
            <p class="text-xs text-gray-500 mt-6">This is a demo session for presentation purposes only</p>
        </div>
        
        <script>
            // Auto-login the user
            const token = '{token}';
            const demoNames = ['Alice Johnson', 'Bob Smith', 'Carol Davis', 'David Lee', 'Emma Wilson'];
            const randomName = demoNames[Math.floor(Math.random() * demoNames.length)];
            const randomEmail = randomName.toLowerCase().replace(' ', '.') + '@demo.com';
            
            const userData = {{
                name: randomName,
                email: randomEmail,
                token: token,
                signedInAt: new Date().toISOString()
            }};
            
            localStorage.setItem('demoUser', JSON.stringify(userData));
            document.getElementById('userName').textContent = randomName;
            
            // Send signin to backend
            fetch('/api/user/signin', {{
                method: 'POST',
                headers: {{ 'Content-Type': 'application/json' }},
                body: JSON.stringify({{ email: randomEmail, name: randomName }})
            }});
        </script>
    </body>
    </html>
    """

@app.route("/")
def index():
    return render_template("index.html")

if __name__ == "__main__":
    # For Replit, host=0.0.0.0 is typical
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")), debug=True)