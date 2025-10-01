// Shopping Cart Application
let CART = [];

function fmt(n) { 
  return (Math.round(n * 100) / 100).toFixed(2); 
}

async function refreshProducts() {
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

    // Fill subcat select once
    const sel = document.getElementById('subcatSel');
    if (sel.options.length <= 1) {
      data.subcats.forEach(s => {
        const o = document.createElement('option');
        o.value = s;
        o.textContent = s;
        sel.appendChild(o);
      });
    }

    // Populate products table
    const tb = document.querySelector('#prodTable tbody');
    tb.innerHTML = '';
    
    data.items.forEach(p => {
      const tr = document.createElement('tr');
      tr.className = 'hover:bg-gray-50 transition-colors';
      
      const nutr = p.nutrition ? Object.entries(p.nutrition).slice(0, 3).map(([k, v]) => k + ': ' + v).join(', ') : '';
      const size = (p.size_value && p.size_unit) ? (p.size_value + p.size_unit) : '—';
      
      const titleCell = document.createElement('td');
      titleCell.className = 'px-6 py-4 text-sm font-medium text-gray-900';
      titleCell.textContent = p.title;
      
      const subcatCell = document.createElement('td');
      subcatCell.className = 'px-6 py-4 text-sm text-gray-600';
      subcatCell.innerHTML = '<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">' + p.subcat + '</span>';
      
      const priceCell = document.createElement('td');
      priceCell.className = 'px-6 py-4 text-sm font-bold text-green-600';
      priceCell.textContent = '$' + fmt(p.price || 0);
      
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
      addBtn.onclick = function() { addToCart(p); };
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

function addToCart(p) {
  console.log('Adding to cart:', p.title);
  const idx = CART.findIndex(x => x.title === p.title && x.subcat === p.subcat);
  if (idx >= 0) {
    CART[idx].qty += 1;
  } else {
    const item = Object.assign({}, p);
    item.qty = 1;
    CART.push(item);
  }
  updateBadge();
  console.log('Cart now has', CART.length, 'items');
}

function updateBadge() {
  const items = CART.reduce((s, x) => s + x.qty, 0);
  document.getElementById('cartBadge').innerHTML = 'Cart: <span class="font-bold">' + items + '</span> items';
}

function viewCart() {
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
    CART.forEach(function(x, i) {
      const line = x.price * x.qty;
      sum += line;
      const size = (x.size_value && x.size_unit) ? (x.size_value + x.size_unit) : '—';
      const row = document.createElement('div');
      row.className = 'bg-gray-50 border border-gray-200 rounded-xl p-4 hover:shadow-md transition-all';
      
      const badge = x.isSubstitute ? '<span class="ml-2 inline-flex items-center px-3 py-1 rounded-full text-xs font-bold bg-green-500 text-white">Budget-Friendly</span>' : '';
      
      row.innerHTML = '<div class="font-semibold text-gray-900 mb-2">' + x.title + badge + '</div>' +
        '<div class="text-sm text-gray-600 mb-2">' +
          '<span class="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">' + x.subcat + '</span>' +
          '<span class="ml-2 text-gray-500">Size: ' + size + '</span>' +
        '</div>' +
        '<div class="flex items-center justify-between">' +
          '<div class="text-sm">' +
            '<span class="font-bold text-green-600">$' + fmt(x.price) + '</span> ' +
            '<span class="text-gray-500">× ' + x.qty + ' = </span>' +
            '<span class="font-bold text-gray-900">$' + fmt(line) + '</span>' +
          '</div>' +
          '<div class="flex items-center space-x-2">' +
            '<button onclick="decQty(' + i + ')" class="bg-gray-500 hover:bg-gray-600 text-white font-bold w-8 h-8 rounded-lg transition-colors">-</button>' +
            '<button onclick="incQty(' + i + ')" class="bg-indigo-600 hover:bg-indigo-700 text-white font-bold w-8 h-8 rounded-lg transition-colors">+</button>' +
            '<button onclick="removeItem(' + i + ')" class="bg-red-500 hover:bg-red-600 text-white font-semibold px-4 py-2 rounded-lg transition-colors">Remove</button>' +
          '</div>' +
        '</div>';
      
      div.appendChild(row);
    });
    
    // Budget warning display
    const warningThreshold75 = budget * 0.75;
    let warningHtml = '';
    
    if (sum > budget) {
      warningHtml = '<div class="bg-red-50 border-l-4 border-red-500 p-4 mb-4 rounded-lg">' +
        '<div class="flex items-center">' +
          '<svg class="w-5 h-5 text-red-500 mr-2" fill="currentColor" viewBox="0 0 20 20">' +
            '<path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd"/>' +
          '</svg>' +
          '<span class="font-bold text-red-700">Over Budget!</span>' +
        '</div>' +
        '<p class="text-red-600 text-sm mt-1">Your cart total ($' + fmt(sum) + ') exceeds your budget ($' + fmt(budget) + ') by $' + fmt(sum - budget) + '</p>' +
      '</div>';
    } else if (sum >= warningThreshold75) {
      warningHtml = '<div class="bg-yellow-50 border-l-4 border-yellow-500 p-4 mb-4 rounded-lg">' +
        '<div class="flex items-center">' +
          '<svg class="w-5 h-5 text-yellow-500 mr-2" fill="currentColor" viewBox="0 0 20 20">' +
            '<path fill-rule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clip-rule="evenodd"/>' +
          '</svg>' +
          '<span class="font-bold text-yellow-700">Budget Alert</span>' +
        '</div>' +
        '<p class="text-yellow-600 text-sm mt-1">You have used ' + Math.round((sum / budget) * 100) + '% of your budget ($' + fmt(sum) + ' of $' + fmt(budget) + ')</p>' +
      '</div>';
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
  const sum = CART.reduce((s, x) => s + (x.price * x.qty), 0);
  if (sum > budget && budget > 0) {
    console.log('Over budget, auto-showing suggestions...');
    setTimeout(function() { getSuggestions(); }, 100);
  } else {
    document.getElementById('suggestions').style.display = 'none';
  }
}

function hideCart() {
  document.getElementById('cartPanel').style.display = 'none';
}

function incQty(i) {
  CART[i].qty += 1;
  viewCart();
  updateBadge();
}

function decQty(i) {
  CART[i].qty = Math.max(1, CART[i].qty - 1);
  viewCart();
  updateBadge();
}

function removeItem(i) {
  CART.splice(i, 1);
  viewCart();
  updateBadge();
}

function applyReplacement(originalTitle, replacementProduct) {
  console.log('Applying replacement:', originalTitle, '->', replacementProduct.title);
  
  const idx = CART.findIndex(x => x.title === originalTitle);
  if (idx === -1) {
    alert('Original item not found in cart. It may have been removed.');
    return;
  }
  
  CART.splice(idx, 1);
  replacementProduct.isSubstitute = true;
  replacementProduct.replacedItem = originalTitle;
  CART.push(replacementProduct);
  
  updateBadge();
  viewCart();
  
  const msg = document.createElement('div');
  msg.className = 'fixed top-6 right-6 bg-green-500 text-white px-6 py-4 rounded-xl shadow-2xl z-50 transform transition-all duration-300 ease-in-out';
  msg.innerHTML = '<div class="flex items-center space-x-3">' +
    '<svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">' +
      '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path>' +
    '</svg>' +
    '<div>' +
      '<div class="font-bold">Replacement Applied!</div>' +
      '<div class="text-sm text-green-100 mt-1">' + originalTitle.substring(0, 35) + '... → ' + replacementProduct.title.substring(0, 35) + '...</div>' +
    '</div>' +
  '</div>';
  
  document.body.appendChild(msg);
  setTimeout(function() {
    msg.style.opacity = '0';
    msg.style.transform = 'translateY(-20px)';
    setTimeout(function() { msg.remove(); }, 300);
  }, 3000);
}

async function getSuggestions() {
  const budget = parseFloat(document.getElementById('budget').value || '0');
  if (!CART.length) {
    alert('Cart is empty');
    return;
  }
  
  const res = await fetch('/api/budget/recommendations', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ cart: CART, budget: budget })
  });
  
  const data = await res.json();
  const sugsDiv = document.getElementById('sugs');
  sugsDiv.innerHTML = '';
  
  if (!data.suggestions || !data.suggestions.length) {
    sugsDiv.innerHTML = '<div class="bg-white border border-indigo-200 rounded-xl p-6 text-center text-gray-500">No suggestions available - you are within budget!</div>';
  } else {
    sugsDiv.innerHTML = '<div class="bg-indigo-50 border-l-4 border-indigo-500 p-4 mb-4 rounded-r-lg">' +
      '<p class="text-indigo-800 font-medium">' + data.message + '</p>' +
    '</div>';
    
    data.suggestions.forEach(function(s) {
      const card = document.createElement('div');
      card.className = 'bg-white border border-indigo-200 rounded-xl p-5 hover:shadow-lg transition-all';
      
      card.innerHTML = '<div class="mb-3">' +
        '<div class="flex items-center space-x-2 mb-2">' +
          '<svg class="w-5 h-5 text-indigo-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">' +
            '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7h12m0 0l-4-4m4 4l-4 4m0 6H4m0 0l4 4m-4-4l4-4"></path>' +
          '</svg>' +
          '<span class="text-gray-700">Replace:</span>' +
        '</div>' +
        '<div class="ml-7">' +
          '<div class="text-sm text-gray-600 line-through">' + s.replace.substring(0, 60) + '...</div>' +
          '<div class="text-lg font-bold text-indigo-900 mt-1">' + s.with.substring(0, 60) + '...</div>' +
        '</div>' +
      '</div>' +
      '<div class="flex items-center justify-between mb-3 bg-green-50 p-3 rounded-lg">' +
        '<div class="flex items-center space-x-2">' +
          '<svg class="w-5 h-5 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">' +
            '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>' +
          '</svg>' +
          '<span class="font-bold text-green-700">Save $' + s.expected_saving + '</span>' +
        '</div>' +
        '<span class="text-sm text-gray-600">Similarity: <span class="font-semibold">' + s.similarity + '</span></span>' +
      '</div>' +
      '<div class="text-sm text-gray-600 mb-4 italic">' +
        '<span class="font-semibold text-gray-700">Reason:</span> ' + s.reason +
      '</div>';
      
      const applyBtn = document.createElement('button');
      applyBtn.className = 'w-full bg-gradient-to-r from-green-500 to-green-600 hover:from-green-600 hover:to-green-700 text-white font-bold py-3 px-6 rounded-lg transition-all duration-200 transform hover:scale-105 shadow-md';
      applyBtn.innerHTML = '<div class="flex items-center justify-center space-x-2">' +
        '<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">' +
          '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path>' +
        '</svg>' +
        '<span>Apply This Replacement</span>' +
      '</div>';
      applyBtn.onclick = function() { applyReplacement(s.replace, s.replacement_product); };
      
      card.appendChild(applyBtn);
      sugsDiv.appendChild(card);
    });
  }
  
  document.getElementById('suggestions').style.display = 'block';
}

async function checkout() {
  if (CART.length === 0) {
    alert('Your cart is empty!');
    return;
  }
  
  const checkoutBtn = document.getElementById('checkoutBtn');
  checkoutBtn.disabled = true;
  checkoutBtn.innerHTML = '<span>Processing...</span>';
  
  try {
    const res = await fetch('/api/checkout', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ cart: CART })
    });
    
    const data = await res.json();
    
    if (data.success) {
      const successMsg = document.createElement('div');
      successMsg.className = 'fixed top-6 right-6 bg-green-500 text-white px-6 py-4 rounded-xl shadow-2xl z-50 transform transition-all duration-300 ease-in-out';
      successMsg.innerHTML = '<div class="flex items-center space-x-3">' +
        '<svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">' +
          '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path>' +
        '</svg>' +
        '<div>' +
          '<div class="font-bold">Order Completed!</div>' +
          '<div class="text-sm text-green-100 mt-1">Order #' + data.order_id + ' - $' + fmt(data.total_amount) + ' (' + data.item_count + ' items)</div>' +
        '</div>' +
      '</div>';
      
      document.body.appendChild(successMsg);
      setTimeout(function() {
        successMsg.style.opacity = '0';
        successMsg.style.transform = 'translateY(-20px)';
        setTimeout(function() { successMsg.remove(); }, 300);
      }, 4000);
      
      CART = [];
      updateBadge();
      hideCart();
      document.getElementById('suggestions').style.display = 'none';
    } else {
      alert('Checkout failed: ' + (data.error || 'Unknown error'));
    }
  } catch (error) {
    console.error('Checkout error:', error);
    alert('Checkout failed: ' + error.message);
  } finally {
    checkoutBtn.disabled = false;
    checkoutBtn.innerHTML = '<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">' +
      '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path>' +
    '</svg>' +
    '<span>Complete Purchase</span>';
  }
}

// Auto-load products on page load
document.addEventListener('DOMContentLoaded', function() {
  console.log('Page loaded, auto-loading products...');
  refreshProducts();
});
