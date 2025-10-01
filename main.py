import os
from flask import Flask, jsonify, request, Response, session, render_template, send_from_directory
import pandas as pd
import numpy as np
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
import uuid
from semantic_budget import ensure_index, recommend_substitutions

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
        item = {
            "id": int(pd.util.hash_pandas_object(pd.Series([row["Title"], row["Sub Category"]])).astype(np.int64).iloc[0]),
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

@app.route("/static/<path:filename>")
def static_files(filename):
    return send_from_directory('static', filename)

@app.route("/")
def index():
    return render_template("index.html")

if __name__ == "__main__":
    # For Replit, host=0.0.0.0 is typical
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")), debug=True)