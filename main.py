import os
from flask import Flask, jsonify, request, Response
import pandas as pd
import numpy as np
from semantic_budget import ensure_index, recommend_substitutions

app = Flask(__name__)

# Build semantic index once and keep a lightweight products frame for listing
PRODUCTS_DF = None

def _init_index():
    global PRODUCTS_DF
    if PRODUCTS_DF is not None:
        return
    idx = ensure_index()  # uses env GROCERY_CSV or default path
    PRODUCTS_DF = idx["df"]
    # keep only columns we display in /api/products
    # (the recommender uses more columns internally via semantic_budget cache)
    keep = ["Title","Sub Category","_price_final","_size_value","_size_unit",
            "Calories","Fat_g","Carbs_g","Sugar_g","Protein_g","Sodium_mg","Feature","Product Description"]
    for c in keep:
        if c not in PRODUCTS_DF.columns:
            PRODUCTS_DF[c] = np.nan

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
    # Inline minimalist UI
    html = """
<!doctype html>
<html>
<head>
  <meta charset="utf-8"/>
  <title>Budget-Aware Substitutions (Semantic + Nutrition)</title>
  <meta name="viewport" content="width=device-width,initial-scale=1"/>
  <style>
    body{font-family:system-ui,Arial,sans-serif;max-width:1100px;margin:0 auto;padding:24px;}
    h1{font-size:20px;margin:0 0 8px;}
    .row{display:flex;gap:16px;align-items:center;flex-wrap:wrap}
    .col{flex:1}
    .card{border:1px solid #e5e7eb;border-radius:10px;padding:12px;margin:8px 0}
    .btn{background:#111827;color:#fff;border:none;border-radius:8px;padding:8px 12px;cursor:pointer}
    .btn.secondary{background:#374151}
    .btn:disabled{opacity:.6;cursor:not-allowed}
    table{width:100%;border-collapse:collapse}
    th,td{padding:8px;border-bottom:1px solid #eee;text-align:left;font-size:14px;vertical-align:top}
    .pill{display:inline-block;padding:2px 8px;background:#f3f4f6;border-radius:999px;font-size:12px;margin-right:6px}
    #suggestions .card{background:#f9fafb}
    code{background:#f3f4f6;padding:1px 4px;border-radius:4px}
  </style>
</head>
<body>
  <h1>🛒 Budget-Aware Substitutions (Semantic + Nutrition)</h1>
  <div class="row">
    <div class="col">
      <label>Budget ($): <input id="budget" type="number" min="0" step="0.01" value="40" /></label>
      <button class="btn" onclick="refreshProducts()">Load Products</button>
      <select id="subcatSel" onchange="refreshProducts()"><option value="">All Subcats</option></select>
    </div>
    <div><span class="pill" id="cartBadge">Cart: 0 items</span> <button class="btn secondary" onclick="viewCart()">View Cart</button></div>
  </div>

  <div id="products" class="card">
    <div style="margin-bottom:8px;font-weight:600;">Products</div>
    <table id="prodTable"><thead><tr>
      <th>Title</th><th>SubCat</th><th>Price</th><th>Size</th><th>Nutrition</th><th></th>
    </tr></thead><tbody></tbody></table>
  </div>

  <div id="cartPanel" class="card" style="display:none;">
    <div class="row"><div style="font-weight:600;">Cart</div><div id="subtotal" class="pill"></div></div>
    <div id="cartItems"></div>
    <div style="margin-top:8px;">
      <button class="btn secondary" onclick="hideCart()">Hide Cart</button>
    </div>
  </div>

  <div id="suggestions" class="card" style="display:none;background:#f0f9ff;border:2px solid #3b82f6;">
    <div style="font-weight:600;color:#1e40af;font-size:16px;margin-bottom:8px;">💡 Budget-Saving Recommendations</div>
    <div id="sugs"></div>
  </div>

<script>
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
    const nutr = p.nutrition ? Object.entries(p.nutrition).slice(0,3).map(([k,v]) => k+': '+v).join(', ') : '';
    const size = (p.size_value && p.size_unit) ? (p.size_value + p.size_unit) : '—';
    
    const titleCell = document.createElement('td');
    titleCell.textContent = p.title;
    
    const subcatCell = document.createElement('td');
    subcatCell.textContent = p.subcat;
    
    const priceCell = document.createElement('td');
    priceCell.textContent = '$' + fmt(p.price||0);
    
    const sizeCell = document.createElement('td');
    sizeCell.textContent = size;
    
    const nutrCell = document.createElement('td');
    nutrCell.textContent = nutr;
    
    const addCell = document.createElement('td');
    const addBtn = document.createElement('button');
    addBtn.className = 'btn';
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
  document.getElementById('cartBadge').textContent = 'Cart: ' + items + ' items';
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
    div.innerHTML = '<div class="card" style="text-align:center;padding:20px;color:#666;">Your cart is empty. Add some products to get started!</div>';
    document.getElementById('subtotal').textContent = 'Subtotal: $0.00';
  } else {
    let sum = 0;
    CART.forEach((x, i) => {
      const line = x.price * x.qty;
      sum += line;
      const size = (x.size_value && x.size_unit) ? (x.size_value + x.size_unit) : '—';
      const row = document.createElement('div');
      row.className = 'card';
      
      // Add substitution badge if item was replaced
      const badge = x.isSubstitute ? '<span style="background:#10b981;color:white;padding:2px 8px;border-radius:12px;font-size:11px;margin-left:8px;">✓ Budget-Friendly</span>' : '';
      
      row.innerHTML = `
        <div style="font-weight:600">${x.title}${badge}</div>
        <div>SubCat: ${x.subcat} | Size: ${size}</div>
        <div>Price: $${fmt(x.price)} × ${x.qty} = $${fmt(line)}</div>
        <div><button class="btn secondary" onclick="decQty(${i})">-</button>
             <button class="btn" onclick="incQty(${i})">+</button>
             <button class="btn secondary" onclick="removeItem(${i})">Remove</button></div>`;
      div.appendChild(row);
    });
    
    // Budget warning display
    const warningThreshold75 = budget * 0.75;
    let warningHtml = '';
    if (sum > budget) {
      warningHtml = `<div style="background:#fee2e2;border-left:4px solid #dc2626;padding:12px;margin:12px 0;border-radius:4px;">
        <strong style="color:#dc2626;">⚠ Over Budget!</strong><br>
        Your cart total ($${fmt(sum)}) exceeds your budget ($${fmt(budget)}) by $${fmt(sum - budget)}
      </div>`;
    } else if (sum >= warningThreshold75) {
      warningHtml = `<div style="background:#fef3c7;border-left:4px solid #f59e0b;padding:12px;margin:12px 0;border-radius:4px;">
        <strong style="color:#f59e0b;">⚡ Budget Alert</strong><br>
        You've used ${Math.round((sum/budget)*100)}% of your budget ($${fmt(sum)} of $${fmt(budget)})
      </div>`;
    }
    
    document.getElementById('subtotal').innerHTML = warningHtml + 'Subtotal: $' + fmt(sum);
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
window.addEventListener('DOMContentLoaded', function() {
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
  msg.style.cssText = 'position:fixed;top:20px;right:20px;background:#10b981;color:white;padding:16px 24px;border-radius:8px;box-shadow:0 4px 6px rgba(0,0,0,0.1);z-index:1000;';
  msg.innerHTML = `<strong>✓ Replaced!</strong><br>${originalTitle.substring(0,40)}... → ${replacementProduct.title.substring(0,40)}...`;
  document.body.appendChild(msg);
  setTimeout(() => msg.remove(), 3000);
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
    sugsDiv.innerHTML = '<div class="card">No suggestions (maybe already within budget).</div>';
  } else {
    sugsDiv.innerHTML = '<div style="margin-bottom:8px;">'+data.message+'</div>';
    data.suggestions.forEach(s => {
      const card = document.createElement('div');
      card.className = 'card';
      
      const replaceText = document.createElement('div');
      replaceText.innerHTML = `<b>Replace</b> ${s.replace} → <b>${s.with}</b>`;
      
      const savingsText = document.createElement('div');
      savingsText.textContent = `Expected Savings: $${s.expected_saving} (Similarity: ${s.similarity})`;
      
      const reasonText = document.createElement('div');
      reasonText.style.color = '#555';
      reasonText.textContent = `Reason: ${s.reason}`;
      
      const applyBtn = document.createElement('button');
      applyBtn.className = 'btn';
      applyBtn.textContent = '✓ Apply This Replacement';
      applyBtn.style.marginTop = '8px';
      applyBtn.style.background = '#10b981';
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