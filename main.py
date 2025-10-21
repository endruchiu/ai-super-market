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
Product, ShoppingCart, UserBudget, User, Order, OrderItem, UserEvent = init_models(db)

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
        recs = get_blended_recommendations(user_id, top_k=100)
        
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
                            
                            # Convert blended score to user-friendly confidence phrase
                            score = float(rec.get('blended_score', 0))
                            if score >= 0.7:
                                confidence = "Perfect match for you"
                            elif score >= 0.5:
                                confidence = "Great choice based on AI analysis"
                            elif score >= 0.3:
                                confidence = "Smart recommendation"
                            else:
                                confidence = "AI-powered suggestion"
                            
                            # Create compelling hybrid recommendation reason
                            reason = f"{confidence}: {rec_title} — similar product, {discount_pct}% cheaper (save ${saving:.2f})"
                            
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
                                
                                # Convert blended score to user-friendly confidence phrase
                                score = float(rec.get('blended_score', 0))
                                if score >= 0.7:
                                    confidence = "AI highly recommends"
                                elif score >= 0.5:
                                    confidence = "AI suggests"
                                elif score >= 0.3:
                                    confidence = "Worth considering"
                                else:
                                    confidence = "Alternative option"
                                
                                # Create compelling cross-category hybrid reason
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

@app.route("/api/user/profile", methods=["GET"])
def api_user_profile():
    """Get user profile data including purchase history and stats"""
    try:
        if 'user_session' not in session:
            session['user_session'] = str(uuid.uuid4())
        session_id = session['user_session']
        
        user = User.query.filter_by(session_id=session_id).first()
        if not user:
            return jsonify({
                "session_id": session_id,
                "total_orders": 0,
                "total_spent": 0.0,
                "total_items": 0,
                "avg_order": 0.0,
                "purchase_history": [],
                "preferences": {
                    "ai_recommendations": True,
                    "budget_alerts": True
                }
            })
        
        orders = Order.query.filter_by(user_id=user.id).order_by(Order.created_at.desc()).limit(10).all()
        
        total_orders = Order.query.filter_by(user_id=user.id).count()
        total_spent = db.session.query(db.func.sum(Order.total_amount)).filter_by(user_id=user.id).scalar() or 0.0
        total_items = db.session.query(db.func.sum(Order.item_count)).filter_by(user_id=user.id).scalar() or 0
        avg_order = total_spent / total_orders if total_orders > 0 else 0.0
        
        purchase_history = []
        for order in orders:
            order_items = OrderItem.query.filter_by(order_id=order.id).all()
            items_list = [{
                "title": item.product_title,
                "subcat": item.product_subcat,
                "quantity": item.quantity,
                "unit_price": float(item.unit_price),
                "line_total": float(item.line_total)
            } for item in order_items]
            
            purchase_history.append({
                "order_id": order.id,
                "created_at": order.created_at.isoformat(),
                "total_amount": float(order.total_amount),
                "item_count": order.item_count,
                "items": items_list
            })
        
        budget = UserBudget.query.filter_by(session_id=session_id).first()
        current_budget = float(budget.budget_amount) if budget else 0.0
        
        return jsonify({
            "session_id": session_id,
            "total_orders": total_orders,
            "total_spent": float(total_spent),
            "total_items": int(total_items),
            "avg_order": float(avg_order),
            "current_budget": current_budget,
            "purchase_history": purchase_history,
            "preferences": {
                "ai_recommendations": user.preferences.get("ai_recommendations", True) if user.preferences else True,
                "budget_alerts": user.preferences.get("budget_alerts", True) if user.preferences else True
            }
        })
        
    except Exception as e:
        print(f"Profile fetch error: {e}")
        return jsonify({"error": "Failed to fetch profile"}), 500

@app.route("/api/user/preferences", methods=["POST"])
def api_user_preferences():
    """Update user preferences"""
    try:
        if 'user_session' not in session:
            session['user_session'] = str(uuid.uuid4())
        session_id = session['user_session']
        
        user = User.query.filter_by(session_id=session_id).first()
        if not user:
            user = User(session_id=session_id)
            db.session.add(user)
            db.session.flush()
        
        payload = request.get_json(force=True)
        preferences = payload.get("preferences", {})
        
        if user.preferences is None:
            user.preferences = {}
        
        user.preferences["ai_recommendations"] = preferences.get("ai_recommendations", True)
        user.preferences["budget_alerts"] = preferences.get("budget_alerts", True)
        user.last_active = db.func.current_timestamp()
        
        db.session.commit()
        
        return jsonify({
            "success": True,
            "preferences": user.preferences
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"Preferences update error: {e}")
        return jsonify({"success": False, "error": "Failed to update preferences"}), 500

@app.route("/api/user/clear-session", methods=["POST"])
def api_clear_session():
    """Clear user session data"""
    try:
        if 'user_session' in session:
            session_id = session['user_session']
            user = User.query.filter_by(session_id=session_id).first()
            
            if user:
                UserEvent.query.filter_by(user_id=user.id).delete()
                OrderItem.query.filter(OrderItem.order_id.in_(
                    db.session.query(Order.id).filter_by(user_id=user.id)
                )).delete(synchronize_session=False)
                Order.query.filter_by(user_id=user.id).delete()
                UserBudget.query.filter_by(session_id=session_id).delete()
                CartItem.query.filter_by(session_id=session_id).delete()
                db.session.delete(user)
                db.session.commit()
            
            session.pop('user_session', None)
        
        return jsonify({"success": True, "message": "Session data cleared"})
        
    except Exception as e:
        db.session.rollback()
        print(f"Clear session error: {e}")
        return jsonify({"success": False, "error": "Failed to clear session"}), 500

@app.route("/static/<path:filename>")
def static_files(filename):
    return send_from_directory('static', filename)

@app.route("/")
def index():
    return render_template("index.html")

if __name__ == "__main__":
    # For Replit, host=0.0.0.0 is typical
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")), debug=True)