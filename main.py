import os
from flask import Flask, jsonify, request, Response, session
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

@app.route("/")
def index():
    # Modern Tailwind CSS UI
    html = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <title>AI Grocery Shopping - Budget Smart Recommendations</title>
  <meta name="viewport" content="width=device-width,initial-scale=1"/>
  <script src="https://cdn.tailwindcss.com"></script>
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    body { font-family: 'Inter', system-ui, sans-serif; }
  </style>
</head>
<body class="bg-gradient-to-br from-blue-50 to-indigo-100 min-h-screen">
  
  <!-- Header -->
  <div class="bg-white shadow-lg border-b border-gray-200">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
      <div class="flex items-center justify-between">
        <div class="flex items-center space-x-3">
          <div class="bg-gradient-to-br from-blue-500 to-indigo-600 p-3 rounded-xl shadow-lg">
            <svg class="w-8 h-8 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 3h2l.4 2M7 13h10l4-8H5.4M7 13L5.4 5M7 13l-2.293 2.293c-.63.63-.184 1.707.707 1.707H17m0 0a2 2 0 100 4 2 2 0 000-4zm-8 2a2 2 0 11-4 0 2 2 0 014 0z"></path>
            </svg>
          </div>
          <div>
            <h1 class="text-2xl font-bold text-gray-900">AI Grocery Shopping</h1>
            <p class="text-sm text-gray-600">Smart budget recommendations powered by AI</p>
          </div>
        </div>
        <div class="flex items-center space-x-4">
          <span id="cartBadge" class="px-4 py-2 bg-indigo-100 text-indigo-700 rounded-full font-semibold text-sm">
            Cart: 0 items
          </span>
          <button onclick="viewCart()" class="bg-indigo-600 hover:bg-indigo-700 text-white font-semibold py-2 px-6 rounded-lg shadow-md transition-all duration-200 transform hover:scale-105">
            View Cart
          </button>
        </div>
      </div>
    </div>
  </div>

  <!-- Main Content -->
  <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
    
    <!-- Budget Controls -->
    <div class="bg-white rounded-2xl shadow-xl p-6 border border-gray-200">
      <div class="flex flex-wrap items-center gap-4">
        <div class="flex-1 min-w-[200px]">
          <label class="block text-sm font-semibold text-gray-700 mb-2">Your Budget</label>
          <div class="relative">
            <span class="absolute left-4 top-1/2 transform -translate-y-1/2 text-gray-500 font-semibold">$</span>
            <input id="budget" type="number" min="0" step="0.01" value="40" 
                   class="w-full pl-8 pr-4 py-3 border-2 border-gray-300 rounded-lg focus:border-indigo-500 focus:ring-2 focus:ring-indigo-200 transition-all font-semibold text-lg"/>
          </div>
        </div>
        <div class="flex-1 min-w-[200px]">
          <label class="block text-sm font-semibold text-gray-700 mb-2">Category Filter</label>
          <select id="subcatSel" onchange="refreshProducts()" 
                  class="w-full px-4 py-3 border-2 border-gray-300 rounded-lg focus:border-indigo-500 focus:ring-2 focus:ring-indigo-200 transition-all font-medium">
            <option value="">All Categories</option>
          </select>
        </div>
        <div class="flex items-end">
          <button onclick="refreshProducts()" 
                  class="bg-gradient-to-r from-blue-500 to-indigo-600 hover:from-blue-600 hover:to-indigo-700 text-white font-bold py-3 px-8 rounded-lg shadow-lg transition-all duration-200 transform hover:scale-105">
            Refresh Products
          </button>
        </div>
      </div>
    </div>

    <!-- Products Table -->
    <div id="products" class="bg-white rounded-2xl shadow-xl overflow-hidden border border-gray-200">
      <div class="bg-gradient-to-r from-gray-50 to-gray-100 px-6 py-4 border-b border-gray-200">
        <h2 class="text-xl font-bold text-gray-800">Available Products</h2>
      </div>
      <div class="overflow-x-auto">
        <table id="prodTable" class="w-full">
          <thead class="bg-gray-50 border-b-2 border-gray-200">
            <tr>
              <th class="px-6 py-4 text-left text-xs font-bold text-gray-700 uppercase tracking-wider">Product</th>
              <th class="px-6 py-4 text-left text-xs font-bold text-gray-700 uppercase tracking-wider">Category</th>
              <th class="px-6 py-4 text-left text-xs font-bold text-gray-700 uppercase tracking-wider">Price</th>
              <th class="px-6 py-4 text-left text-xs font-bold text-gray-700 uppercase tracking-wider">Size</th>
              <th class="px-6 py-4 text-left text-xs font-bold text-gray-700 uppercase tracking-wider">Nutrition</th>
              <th class="px-6 py-4"></th>
            </tr>
          </thead>
          <tbody class="divide-y divide-gray-200"></tbody>
        </table>
      </div>
    </div>

    <!-- Cart Panel -->
    <div id="cartPanel" class="bg-white rounded-2xl shadow-xl p-6 border-2 border-indigo-200" style="display:none;">
      <div class="flex items-center justify-between mb-6">
        <h2 class="text-2xl font-bold text-gray-900">Shopping Cart</h2>
        <div id="subtotal" class="text-lg font-semibold text-gray-700"></div>
      </div>
      <div id="cartItems" class="space-y-4"></div>
      <div class="mt-6 flex justify-end">
        <button onclick="hideCart()" class="bg-gray-500 hover:bg-gray-600 text-white font-semibold py-2 px-6 rounded-lg transition-all duration-200">
          Close Cart
        </button>
      </div>
    </div>

    <!-- AI Recommendations -->
    <div id="suggestions" class="bg-gradient-to-br from-blue-50 to-indigo-100 rounded-2xl shadow-xl p-6 border-2 border-indigo-300" style="display:none;">
      <div class="flex items-center space-x-3 mb-4">
        <div class="bg-indigo-600 p-2 rounded-lg">
          <svg class="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"></path>
          </svg>
        </div>
        <h3 class="text-xl font-bold text-indigo-900">AI Budget-Saving Recommendations</h3>
      </div>
      <div id="sugs" class="space-y-4"></div>
    </div>

  </div>

  <script type="text/javascript">
let CART = [];

function fmt(n){ return (Math.round(n*100)/100).toFixed(2); }

async function refreshProducts(){
  try {
    const subcat = document.getElementById('subcatSel').value || '';
    const qs = subcat ? ('?subcat=' + encodeURIComponent(subcat)) : '';
    console.log('Fetching products from:', '/api/products' + qs);
    const res = await fetch('/api/products' + qs);
    if (!res.ok) {
      console.error('API error:', res.status, res.statusText);
      alert('Failed to load products. Error: ' + res.status);
      return;
    }
    const data = await res.json();
    console.log('Got products:', data);

  // fill subcat select once
  const sel = document.getElementById('subcatSel');
  if (sel.options.length <= 1){
    data.subcats.forEach(s => {
      const o = document.createElement('option'); o.value = s; o.textContent = s; sel.appendChild(o);
    });
  }

  const tb = document.querySelector('#prodTable tbody');
  tb.innerHTML = '';
  data.items.forEach(p => {
    const tr = document.createElement('tr');
    tr.className = 'hover:bg-gray-50 transition-colors';
    const nutr = p.nutrition ? Object.entries(p.nutrition).slice(0,3).map(([k,v]) => k+': '+v).join(', ') : '';
    const size = (p.size_value && p.size_unit) ? (p.size_value + p.size_unit) : '—';
    
    const titleCell = document.createElement('td');
    titleCell.className = 'px-6 py-4 text-sm font-medium text-gray-900';
    titleCell.textContent = p.title;
    
    const subcatCell = document.createElement('td');
    subcatCell.className = 'px-6 py-4 text-sm text-gray-600';
    subcatCell.innerHTML = `<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">${p.subcat}</span>`;
    
    const priceCell = document.createElement('td');
    priceCell.className = 'px-6 py-4 text-sm font-bold text-green-600';
    priceCell.textContent = '$' + fmt(p.price||0);
    
    const sizeCell = document.createElement('td');
    sizeCell.className = 'px-6 py-4 text-sm text-gray-500';
    sizeCell.textContent = size;
    
    const nutrCell = document.createElement('td');
    nutrCell.className = 'px-6 py-4 text-xs text-gray-500';
    nutrCell.textContent = nutr;
    
    const addCell = document.createElement('td');
    addCell.className = 'px-6 py-4 text-right';
    const addBtn = document.createElement('button');
    addBtn.className = 'bg-indigo-600 hover:bg-indigo-700 text-white font-semibold py-2 px-4 rounded-lg transition-all duration-200 transform hover:scale-105 shadow-md';
    addBtn.textContent = 'Add';
    addBtn.onclick = () => addToCart(p);
    addCell.appendChild(addBtn);
    
    tr.appendChild(titleCell);
    tr.appendChild(subcatCell);
    tr.appendChild(priceCell);
    tr.appendChild(sizeCell);
    tr.appendChild(nutrCell);
    tr.appendChild(addCell);
    
    tb.appendChild(tr);
  });
  } catch (error) {
    console.error('Error loading products:', error);
    alert('Failed to load products: ' + error.message);
  }
}

function addToCart(p){
  console.log('Adding to cart:', p.title);
  // simplify: push one qty
  const idx = CART.findIndex(x => x.title===p.title && x.subcat===p.subcat);
  if (idx>=0) CART[idx].qty += 1;
  else CART.push({...p, qty:1});
  updateBadge();
  console.log('Cart now has', CART.length, 'items');
}

function updateBadge(){
  const items = CART.reduce((s,x)=>s+x.qty, 0);
  document.getElementById('cartBadge').innerHTML = `Cart: <span class="font-bold">${items}</span> items`;
}

function viewCart(){
  console.log('View Cart clicked. Cart has', CART.length, 'items:', CART);
  const div = document.getElementById('cartItems');
  if (!div) {
    console.error('cartItems div not found!');
    return;
  }
  div.innerHTML = '';
  
  const budget = parseFloat(document.getElementById('budget').value || '0');
  
  if (CART.length === 0) {
    div.innerHTML = '<div class="bg-gray-50 border-2 border-dashed border-gray-300 rounded-xl p-12 text-center"><p class="text-gray-500 text-lg">Your cart is empty</p><p class="text-gray-400 text-sm mt-2">Add some products to get started!</p></div>';
    document.getElementById('subtotal').textContent = 'Subtotal: $0.00';
  } else {
    let sum = 0;
    CART.forEach((x, i) => {
      const line = x.price * x.qty;
      sum += line;
      const size = (x.size_value && x.size_unit) ? (x.size_value + x.size_unit) : '—';
      const row = document.createElement('div');
      row.className = 'bg-gray-50 border border-gray-200 rounded-xl p-4 hover:shadow-md transition-all';
      
      // Add substitution badge if item was replaced
      const badge = x.isSubstitute ? '<span class="ml-2 inline-flex items-center px-3 py-1 rounded-full text-xs font-bold bg-green-500 text-white">✓ Budget-Friendly</span>' : '';
      
      row.innerHTML = `
        <div class="font-semibold text-gray-900 mb-2">${x.title}${badge}</div>
        <div class="text-sm text-gray-600 mb-2">
          <span class="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">${x.subcat}</span>
          <span class="ml-2 text-gray-500">Size: ${size}</span>
        </div>
        <div class="flex items-center justify-between">
          <div class="text-sm">
            <span class="font-bold text-green-600">$${fmt(x.price)}</span> 
            <span class="text-gray-500">× ${x.qty} = </span>
            <span class="font-bold text-gray-900">$${fmt(line)}</span>
          </div>
          <div class="flex items-center space-x-2">
            <button onclick="decQty(${i})" class="bg-gray-500 hover:bg-gray-600 text-white font-bold w-8 h-8 rounded-lg transition-colors">-</button>
            <button onclick="incQty(${i})" class="bg-indigo-600 hover:bg-indigo-700 text-white font-bold w-8 h-8 rounded-lg transition-colors">+</button>
            <button onclick="removeItem(${i})" class="bg-red-500 hover:bg-red-600 text-white font-semibold px-4 py-2 rounded-lg transition-colors">Remove</button>
          </div>
        </div>`;
      div.appendChild(row);
    });
    
    // Budget warning display
    const warningThreshold75 = budget * 0.75;
    let warningHtml = '';
    if (sum > budget) {
      warningHtml = `<div class="bg-red-50 border-l-4 border-red-500 p-4 mb-4 rounded-lg">
        <div class="flex items-center">
          <svg class="w-5 h-5 text-red-500 mr-2" fill="currentColor" viewBox="0 0 20 20">
            <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd"/>
          </svg>
          <span class="font-bold text-red-700">⚠ Over Budget!</span>
        </div>
        <p class="text-red-600 text-sm mt-1">Your cart total ($${fmt(sum)}) exceeds your budget ($${fmt(budget)}) by $${fmt(sum - budget)}</p>
      </div>`;
    } else if (sum >= warningThreshold75) {
      warningHtml = `<div class="bg-yellow-50 border-l-4 border-yellow-500 p-4 mb-4 rounded-lg">
        <div class="flex items-center">
          <svg class="w-5 h-5 text-yellow-500 mr-2" fill="currentColor" viewBox="0 0 20 20">
            <path fill-rule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clip-rule="evenodd"/>
          </svg>
          <span class="font-bold text-yellow-700">⚡ Budget Alert</span>
        </div>
        <p class="text-yellow-600 text-sm mt-1">You've used ${Math.round((sum/budget)*100)}% of your budget ($${fmt(sum)} of $${fmt(budget)})</p>
      </div>`;
    }
    
    document.getElementById('subtotal').innerHTML = warningHtml + '<span class="text-2xl font-bold text-gray-900">Subtotal: <span class="text-indigo-600">$' + fmt(sum) + '</span></span>';
  }
  
  const panel = document.getElementById('cartPanel');
  if (!panel) {
    console.error('cartPanel not found!');
    return;
  }
  panel.style.display = 'block';
  console.log('Cart panel should now be visible');
  
  // Auto-show suggestions if over budget
  const sum = CART.reduce((s,x) => s + (x.price * x.qty), 0);
  if (sum > budget && budget > 0) {
    console.log('Over budget, auto-showing suggestions...');
    setTimeout(() => getSuggestions(), 100);
  } else {
    // Hide suggestions if within budget
    document.getElementById('suggestions').style.display = 'none';
  }
}

function hideCart(){ document.getElementById('cartPanel').style.display = 'none'; }

function incQty(i){ CART[i].qty += 1; viewCart(); updateBadge(); }
function decQty(i){ CART[i].qty = Math.max(1, CART[i].qty - 1); viewCart(); updateBadge(); }
function removeItem(i){ CART.splice(i,1); viewCart(); updateBadge(); }

// Auto-load products on page load
document.addEventListener('DOMContentLoaded', function() {
  console.log('Page loaded, auto-loading products...');
  refreshProducts();
});

function applyReplacement(originalTitle, replacementProduct) {
  console.log('Applying replacement:', originalTitle, '->', replacementProduct.title);
  
  // Find and remove the original item from cart
  const idx = CART.findIndex(x => x.title === originalTitle);
  if (idx === -1) {
    alert('Original item not found in cart. It may have been removed.');
    return;
  }
  
  // Remove original item
  CART.splice(idx, 1);
  
  // Mark as substitute for UI indicator
  replacementProduct.isSubstitute = true;
  replacementProduct.replacedItem = originalTitle;
  
  // Add replacement item
  CART.push(replacementProduct);
  
  // Update UI
  updateBadge();
  viewCart();
  
  // Show success message (non-intrusive)
  const msg = document.createElement('div');
  msg.className = 'fixed top-6 right-6 bg-green-500 text-white px-6 py-4 rounded-xl shadow-2xl z-50 transform transition-all duration-300 ease-in-out';
  msg.innerHTML = `
    <div class="flex items-center space-x-3">
      <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path>
      </svg>
      <div>
        <div class="font-bold">✓ Replacement Applied!</div>
        <div class="text-sm text-green-100 mt-1">${originalTitle.substring(0,35)}... → ${replacementProduct.title.substring(0,35)}...</div>
      </div>
    </div>`;
  document.body.appendChild(msg);
  setTimeout(() => {
    msg.style.opacity = '0';
    msg.style.transform = 'translateY(-20px)';
    setTimeout(() => msg.remove(), 300);
  }, 3000);
}

async function getSuggestions(){
  const budget = parseFloat(document.getElementById('budget').value || '0');
  if (!CART.length){ alert('Cart is empty'); return; }
  const res = await fetch('/api/budget/recommendations', {
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify({cart:CART, budget})
  });
  const data = await res.json();
  const sugsDiv = document.getElementById('sugs');
  sugsDiv.innerHTML = '';
  if (!data.suggestions || !data.suggestions.length){
    sugsDiv.innerHTML = '<div class="bg-white border border-indigo-200 rounded-xl p-6 text-center text-gray-500">No suggestions available - you\'re within budget! 🎉</div>';
  } else {
    sugsDiv.innerHTML = `<div class="bg-indigo-50 border-l-4 border-indigo-500 p-4 mb-4 rounded-r-lg">
      <p class="text-indigo-800 font-medium">${data.message}</p>
    </div>`;
    data.suggestions.forEach(s => {
      const card = document.createElement('div');
      card.className = 'bg-white border border-indigo-200 rounded-xl p-5 hover:shadow-lg transition-all';
      
      const replaceText = document.createElement('div');
      replaceText.className = 'mb-3';
      replaceText.innerHTML = `
        <div class="flex items-center space-x-2 mb-2">
          <svg class="w-5 h-5 text-indigo-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7h12m0 0l-4-4m4 4l-4 4m0 6H4m0 0l4 4m-4-4l4-4"></path>
          </svg>
          <span class="text-gray-700">Replace:</span>
        </div>
        <div class="ml-7">
          <div class="text-sm text-gray-600 line-through">${s.replace.substring(0, 60)}...</div>
          <div class="text-lg font-bold text-indigo-900 mt-1">${s.with.substring(0, 60)}...</div>
        </div>`;
      
      const savingsText = document.createElement('div');
      savingsText.className = 'flex items-center justify-between mb-3 bg-green-50 p-3 rounded-lg';
      savingsText.innerHTML = `
        <div class="flex items-center space-x-2">
          <svg class="w-5 h-5 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>
          </svg>
          <span class="font-bold text-green-700">Save $${s.expected_saving}</span>
        </div>
        <span class="text-sm text-gray-600">Similarity: <span class="font-semibold">${s.similarity}</span></span>`;
      
      const reasonText = document.createElement('div');
      reasonText.className = 'text-sm text-gray-600 mb-4 italic';
      reasonText.innerHTML = `<span class="font-semibold text-gray-700">Reason:</span> ${s.reason}`;
      
      const applyBtn = document.createElement('button');
      applyBtn.className = 'w-full bg-gradient-to-r from-green-500 to-green-600 hover:from-green-600 hover:to-green-700 text-white font-bold py-3 px-6 rounded-lg transition-all duration-200 transform hover:scale-105 shadow-md';
      applyBtn.innerHTML = `
        <div class="flex items-center justify-center space-x-2">
          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path>
          </svg>
          <span>Apply This Replacement</span>
        </div>`;
      applyBtn.onclick = () => applyReplacement(s.replace, s.replacement_product);
      
      card.appendChild(replaceText);
      card.appendChild(savingsText);
      card.appendChild(reasonText);
      card.appendChild(applyBtn);
      
      sugsDiv.appendChild(card);
    });
  }
  document.getElementById('suggestions').style.display = 'block';
}
</script>
</body></html>
    """
    return Response(html, mimetype="text/html")

if __name__ == "__main__":
    # For Replit, host=0.0.0.0 is typical
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")), debug=True)