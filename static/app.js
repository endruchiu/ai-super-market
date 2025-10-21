// Shopping Cart Application
let CART = [];
let CURRENT_CATEGORY = '';
let RECOMMENDATION_HIGHLIGHT_CATEGORY = null;

// Track which recommendation systems have suggestions for each subcategory
// Format: { subcategory: { budget: true, cf: true, hybrid: true } }
let RECOMMENDATION_DOTS = {};

function fmt(n) { 
  return (Math.round(n * 100) / 100).toFixed(2); 
}

function highlightAisleForRecommendation(subcategory) {
  if (!subcategory) {
    clearRecommendationHighlight();
    return;
  }
  
  RECOMMENDATION_HIGHLIGHT_CATEGORY = subcategory;
  
  const shelves = document.querySelectorAll('.aisle-shelf');
  shelves.forEach(shelf => {
    shelf.classList.remove('recommendation-highlight');
    
    if (shelf.textContent.includes(subcategory)) {
      shelf.classList.add('recommendation-highlight');
    }
  });
}

function clearRecommendationHighlight() {
  RECOMMENDATION_HIGHLIGHT_CATEGORY = null;
  
  const shelves = document.querySelectorAll('.aisle-shelf');
  shelves.forEach(shelf => {
    shelf.classList.remove('recommendation-highlight');
  });
}

// Add a recommendation dot for a specific system and subcategory
function addRecommendationDot(subcategory, system) {
  if (!subcategory || !system) return;
  
  if (!RECOMMENDATION_DOTS[subcategory]) {
    RECOMMENDATION_DOTS[subcategory] = {};
  }
  RECOMMENDATION_DOTS[subcategory][system] = true;
  
  updateRecommendationDots();
}

// Clear all recommendation dots
function clearRecommendationDots() {
  RECOMMENDATION_DOTS = {};
  updateRecommendationDots();
}

// Update the visual display of recommendation dots on all shelves
function updateRecommendationDots() {
  const shelves = document.querySelectorAll('.aisle-shelf');
  
  shelves.forEach(shelf => {
    // Remove existing dots container if present
    let dotsContainer = shelf.querySelector('.rec-dots-container');
    if (dotsContainer) {
      dotsContainer.remove();
    }
    
    // Find which subcategory this shelf represents
    const categoryText = shelf.textContent.trim();
    let matchingSubcat = null;
    
    for (const subcat in RECOMMENDATION_DOTS) {
      if (categoryText.includes(subcat)) {
        matchingSubcat = subcat;
        break;
      }
    }
    
    if (!matchingSubcat) return;
    
    const systems = RECOMMENDATION_DOTS[matchingSubcat];
    
    // Only show green dot for Hybrid AI system
    if (systems.hybrid) {
      dotsContainer = document.createElement('div');
      dotsContainer.className = 'rec-dots-container';
      dotsContainer.innerHTML = '<span class="rec-dot rec-dot-green" title="Hybrid AI"></span>';
      shelf.style.position = 'relative';
      shelf.appendChild(dotsContainer);
    }
  });
}

// Helper function: Update Recommendations Module visibility
function updateRecommendationsModule() {
  const hybrid = document.getElementById('blendedRecommendations');
  const module = document.getElementById('recommendationsModule');
  
  // Show module if hybrid recommendation section is visible
  module.style.display = hybrid.style.display === 'block' ? 'block' : 'none';
}

// New function: Filter by category (for store map)
async function filterByCategory(category) {
  CURRENT_CATEGORY = category;
  
  // Highlight selected shelf
  const shelves = document.querySelectorAll('.aisle-shelf');
  shelves.forEach(shelf => {
    shelf.classList.remove('selected');
    if (shelf.textContent.includes(category)) {
      shelf.classList.add('selected');
    }
  });
  
  // Load products for this category
  await loadProducts(category);
  
  // Show products browser
  const browser = document.getElementById('productsBrowser');
  if (browser) {
    browser.style.display = 'block';
    document.getElementById('browserToggleIcon').style.transform = 'rotate(180deg)';
  }
}

// New function: Reset view
function resetView() {
  CURRENT_CATEGORY = '';
  
  // Remove all selected highlights
  const shelves = document.querySelectorAll('.aisle-shelf');
  shelves.forEach(shelf => shelf.classList.remove('selected'));
  
  // Load all products
  loadProducts('');
}

// New function: Toggle products browser
function toggleProductsBrowser() {
  const browser = document.getElementById('productsBrowser');
  const icon = document.getElementById('browserToggleIcon');
  
  if (browser.style.display === 'none' || !browser.style.display) {
    browser.style.display = 'block';
    icon.style.transform = 'rotate(180deg)';
    loadProducts(CURRENT_CATEGORY);
  } else {
    browser.style.display = 'none';
    icon.style.transform = 'rotate(0deg)';
  }
}

async function loadProducts(subcat = '') {
  try {
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

    // Populate products table
    const tb = document.getElementById('prodTableBody');
    if (!tb) {
      console.error('prodTableBody not found');
      return;
    }
    tb.innerHTML = '';
    
    data.items.forEach(p => {
      const tr = document.createElement('tr');
      tr.className = 'hover:bg-gray-50 transition-colors';
      
      const nutr = p.nutrition ? Object.entries(p.nutrition).slice(0, 3).map(([k, v]) => k + ': ' + v).join(', ') : '';
      
      const titleCell = document.createElement('td');
      titleCell.className = 'px-4 py-3 text-sm font-medium text-gray-900';
      titleCell.textContent = p.title;
      
      const subcatCell = document.createElement('td');
      subcatCell.className = 'px-4 py-3 text-sm text-gray-600';
      subcatCell.innerHTML = '<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-indigo-100 text-indigo-800">' + p.subcat + '</span>';
      
      const priceCell = document.createElement('td');
      priceCell.className = 'px-4 py-3 text-sm font-bold text-green-600';
      priceCell.textContent = '$' + fmt(p.price || 0);
      
      const nutrCell = document.createElement('td');
      nutrCell.className = 'px-4 py-3 text-xs text-gray-500';
      nutrCell.textContent = nutr;
      
      const addCell = document.createElement('td');
      addCell.className = 'px-4 py-3 text-right';
      const addBtn = document.createElement('button');
      addBtn.className = 'bg-indigo-600 hover:bg-indigo-700 text-white font-semibold py-2 px-4 rounded-lg transition-all duration-200 transform hover:scale-105 shadow-md';
      addBtn.textContent = 'Add';
      addBtn.onclick = function() { addToCart(p); };
      addCell.appendChild(addBtn);
      
      tr.appendChild(titleCell);
      tr.appendChild(subcatCell);
      tr.appendChild(priceCell);
      tr.appendChild(nutrCell);
      tr.appendChild(addCell);
      
      tb.appendChild(tr);
    });
  } catch (error) {
    console.error('Error loading products:', error);
    alert('Failed to load products: ' + error.message);
  }
}

async function refreshProducts() {
  await loadProducts(CURRENT_CATEGORY);
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
  updateCartDisplay();
  console.log('Cart now has', CART.length, 'items');
}

function updateBadge() {
  const items = CART.reduce((s, x) => s + x.qty, 0);
  document.getElementById('cartBadge').innerHTML = 'Cart: <span class="font-bold">' + items + '</span> items';
}

function updateCartDisplay() {
  const div = document.getElementById('cartItems');
  const totalSpan = document.getElementById('totalAmount');
  
  if (!div || !totalSpan) {
    console.error('Cart elements not found!');
    return;
  }
  
  const budget = parseFloat(document.getElementById('budget').value || '0');
  div.innerHTML = '';
  
  if (CART.length === 0) {
    div.innerHTML = '<p class="text-gray-500 text-sm text-center py-8">Your cart is empty.</p>';
    totalSpan.textContent = '$0.00';
    // Clear budget warning when cart is empty
    updateBudgetWarning(0, budget);
  } else {
    let sum = 0;
    CART.forEach(function(x, i) {
      const line = x.price * x.qty;
      sum += line;
      
      const row = document.createElement('div');
      row.className = 'bg-gray-50 border border-gray-200 rounded-lg p-3 mb-2';
      
      const badge = x.isSubstitute ? '<span class="ml-1 inline-flex items-center px-2 py-0.5 rounded-full text-xs font-bold bg-green-500 text-white">✓</span>' : '';
      
      row.innerHTML = '<div class="text-sm font-semibold text-gray-900 mb-1">' + x.title.substring(0, 50) + (x.title.length > 50 ? '...' : '') + badge + '</div>' +
        '<div class="flex items-center justify-between text-xs mb-2">' +
          '<span class="text-gray-600">' + x.subcat + '</span>' +
          '<span class="font-bold text-green-600">$' + fmt(x.price) + '</span>' +
        '</div>' +
        '<div class="flex items-center justify-between">' +
          '<div class="flex items-center space-x-1">' +
            '<button onclick="decQty(' + i + ')" class="bg-gray-400 hover:bg-gray-500 text-white font-bold w-6 h-6 rounded transition-colors text-xs">-</button>' +
            '<span class="px-2 text-sm font-semibold">' + x.qty + '</span>' +
            '<button onclick="incQty(' + i + ')" class="bg-indigo-600 hover:bg-indigo-700 text-white font-bold w-6 h-6 rounded transition-colors text-xs">+</button>' +
          '</div>' +
          '<button onclick="removeItem(' + i + ')" class="text-red-500 hover:text-red-700 text-xs font-semibold">Remove</button>' +
        '</div>';
      
      div.appendChild(row);
    });
    
    totalSpan.textContent = '$' + fmt(sum);
    
    // Update budget warning
    updateBudgetWarning(sum, budget);
  }
  
  // Auto-show all recommendation systems if over budget
  const sum = CART.reduce((s, x) => s + (x.price * x.qty), 0);
  if (sum > budget && budget > 0) {
    console.log('Over budget! Triggering Hybrid AI recommendation system...');
    setTimeout(function() { 
      getBlendedRecommendations();
    }, 100);
  } else {
    document.getElementById('blendedRecommendations').style.display = 'none';
    updateRecommendationsModule();
    clearRecommendationHighlight();
    clearRecommendationDots();
  }
}

function updateBudgetWarning(cartTotal, budget) {
  const warningDiv = document.getElementById('budgetWarning');
  if (!warningDiv || budget <= 0) {
    if (warningDiv) warningDiv.style.display = 'none';
    return;
  }
  
  const percentage = (cartTotal / budget) * 100;
  
  if (cartTotal > budget) {
    // RED WARNING - Over budget
    const overAmount = cartTotal - budget;
    warningDiv.className = 'mt-3 p-3 bg-red-50 border-l-4 border-red-500 rounded-r-lg';
    warningDiv.innerHTML = '<div class="flex items-center space-x-2">' +
      '<svg class="w-5 h-5 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">' +
        '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"></path>' +
      '</svg>' +
      '<div class="flex-1">' +
        '<p class="text-red-800 font-bold text-sm">Over Budget!</p>' +
        '<p class="text-red-600 text-xs mt-0.5">You are $' + fmt(overAmount) + ' over your $' + fmt(budget) + ' budget (' + Math.round(percentage) + '%)</p>' +
      '</div>' +
    '</div>';
    warningDiv.style.display = 'block';
  } else if (percentage >= 80) {
    // YELLOW WARNING - Approaching budget (80-100%)
    const remaining = budget - cartTotal;
    warningDiv.className = 'mt-3 p-3 bg-yellow-50 border-l-4 border-yellow-500 rounded-r-lg';
    warningDiv.innerHTML = '<div class="flex items-center space-x-2">' +
      '<svg class="w-5 h-5 text-yellow-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">' +
        '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"></path>' +
      '</svg>' +
      '<div class="flex-1">' +
        '<p class="text-yellow-800 font-bold text-sm">Approaching Budget</p>' +
        '<p class="text-yellow-600 text-xs mt-0.5">$' + fmt(remaining) + ' remaining of $' + fmt(budget) + ' budget (' + Math.round(percentage) + '%)</p>' +
      '</div>' +
    '</div>';
    warningDiv.style.display = 'block';
  } else {
    // GREEN - Within budget (< 80%)
    warningDiv.style.display = 'none';
  }
}

function viewCart() {
  updateCartDisplay();
}

function hideCart() {
  // Not needed in new layout - cart is always visible
}

function incQty(i) {
  CART[i].qty += 1;
  updateCartDisplay();
  updateBadge();
}

function decQty(i) {
  CART[i].qty = Math.max(1, CART[i].qty - 1);
  updateCartDisplay();
  updateBadge();
}

function removeItem(i) {
  CART.splice(i, 1);
  updateCartDisplay();
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
  updateCartDisplay();
  
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
    clearRecommendationHighlight();
  } else {
    sugsDiv.innerHTML = '<div class="bg-indigo-50 border-l-4 border-indigo-500 p-4 mb-4 rounded-r-lg">' +
      '<p class="text-indigo-800 font-medium">' + data.message + '</p>' +
    '</div>';
    
    let mostRecentSubcat = null;
    
    data.suggestions.forEach(function(s) {
      if (s.replacement_product && s.replacement_product.subcat) {
        mostRecentSubcat = s.replacement_product.subcat;
        // Register blue dot for Budget-Saving system
        addRecommendationDot(s.replacement_product.subcat, 'budget');
      }
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
    
    highlightAisleForRecommendation(mostRecentSubcat);
  }
  
  document.getElementById('suggestions').style.display = 'block';
  updateRecommendationsModule();
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
      updateCartDisplay();
      document.getElementById('blendedRecommendations').style.display = 'none';
      updateRecommendationsModule();
      clearRecommendationHighlight();
      clearRecommendationDots();
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

async function getCFRecommendations() {
  console.log('getCFRecommendations() called');
  const budget = parseFloat(document.getElementById('budget').value || '0');
  
  try {
    const res = await fetch('/api/cf/recommendations', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ cart: CART, budget: budget })
    });
    const data = await res.json();
    console.log('CF recommendations response:', data);
    
    const contentDiv = document.getElementById('cfRecsContent');
    contentDiv.innerHTML = '';
    
    if (!data.model_available) {
      contentDiv.innerHTML = '<div class="bg-white border border-purple-200 rounded-xl p-6 text-center">' +
        '<p class="text-gray-600 font-medium mb-2">CF recommendations not yet available</p>' +
        '<p class="text-gray-500 text-sm">' + data.reason + '</p>' +
      '</div>';
      document.getElementById('cfRecommendations').style.display = 'block';
      updateRecommendationsModule();
      return;
    }
    
    if (!data.suggestions || data.suggestions.length === 0) {
      contentDiv.innerHTML = '<div class="bg-white border border-purple-200 rounded-xl p-6 text-center text-gray-500">' + (data.message || 'No CF replacements found') + '</div>';
      clearRecommendationHighlight();
    } else {
      contentDiv.innerHTML = '<div class="bg-purple-50 border-l-4 border-purple-500 p-4 mb-4 rounded-r-lg">' +
        '<p class="text-purple-800 font-medium">' + data.message + '</p>' +
      '</div>';
      
      let mostRecentSubcat = null;
      
      data.suggestions.forEach(function(s) {
        if (s.replacement_product && s.replacement_product.subcat) {
          mostRecentSubcat = s.replacement_product.subcat;
          // Register purple dot for CF system
          addRecommendationDot(s.replacement_product.subcat, 'cf');
        }
        const card = document.createElement('div');
        card.className = 'bg-white border border-purple-200 rounded-xl p-5 hover:shadow-lg transition-all';
        
        card.innerHTML = '<div class="mb-3">' +
          '<div class="flex items-center space-x-2 mb-2">' +
            '<svg class="w-5 h-5 text-purple-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">' +
              '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7h12m0 0l-4-4m4 4l-4 4m0 6H4m0 0l4 4m-4-4l4-4"></path>' +
            '</svg>' +
            '<span class="text-gray-700">Replace:</span>' +
          '</div>' +
          '<div class="ml-7">' +
            '<div class="text-sm text-gray-600 line-through">' + s.replace.substring(0, 60) + '...</div>' +
            '<div class="text-lg font-bold text-purple-900 mt-1">' + s.with.substring(0, 60) + '...</div>' +
          '</div>' +
        '</div>' +
        '<div class="flex items-center justify-between mb-3 bg-green-50 p-3 rounded-lg">' +
          '<div class="flex items-center space-x-2">' +
            '<svg class="w-5 h-5 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">' +
              '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>' +
            '</svg>' +
            '<span class="font-bold text-green-700">Save $' + s.expected_saving + '</span>' +
          '</div>' +
          '<span class="text-sm text-gray-600">Score: <span class="font-semibold">' + s.similarity + '</span></span>' +
        '</div>' +
        '<div class="text-sm text-gray-600 mb-4 italic">' +
          '<span class="font-semibold text-gray-700">Reason:</span> ' + s.reason +
        '</div>';
        
        const applyBtn = document.createElement('button');
        applyBtn.className = 'w-full bg-gradient-to-r from-purple-500 to-purple-600 hover:from-purple-600 hover:to-purple-700 text-white font-bold py-3 px-6 rounded-lg transition-all duration-200 transform hover:scale-105 shadow-md';
        applyBtn.innerHTML = '<div class="flex items-center justify-center space-x-2">' +
          '<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">' +
            '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path>' +
          '</svg>' +
          '<span>Apply This Replacement</span>' +
        '</div>';
        applyBtn.onclick = function() { applyReplacement(s.replace, s.replacement_product); };
        
        card.appendChild(applyBtn);
        contentDiv.appendChild(card);
      });
      
      highlightAisleForRecommendation(mostRecentSubcat);
    }
    
    document.getElementById('cfRecommendations').style.display = 'block';
    updateRecommendationsModule();
  } catch (error) {
    console.error('Error fetching CF recommendations:', error);
    alert('Failed to load CF recommendations: ' + error.message);
  }
}

async function getBlendedRecommendations() {
  console.log('getBlendedRecommendations() called');
  const budget = parseFloat(document.getElementById('budget').value || '0');
  
  try {
    const res = await fetch('/api/blended/recommendations', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ cart: CART, budget: budget })
    });
    const data = await res.json();
    console.log('Blended recommendations response:', data);
    
    const contentDiv = document.getElementById('blendedRecsContent');
    contentDiv.innerHTML = '';
    
    if (!data.model_available) {
      contentDiv.innerHTML = '<div class="bg-white border border-emerald-200 rounded-xl p-6 text-center">' +
        '<p class="text-gray-600 font-medium mb-2">Hybrid recommendations not yet available</p>' +
        '<p class="text-gray-500 text-sm">' + data.reason + '</p>' +
      '</div>';
      document.getElementById('blendedRecommendations').style.display = 'block';
      updateRecommendationsModule();
      return;
    }
    
    if (!data.suggestions || data.suggestions.length === 0) {
      contentDiv.innerHTML = '<div class="bg-white border border-emerald-200 rounded-xl p-6 text-center text-gray-500">' + (data.message || 'No hybrid replacements found') + '</div>';
      clearRecommendationHighlight();
    } else {
      contentDiv.innerHTML = '<div class="bg-emerald-50 border-l-4 border-emerald-500 p-4 mb-4 rounded-r-lg">' +
        '<p class="text-emerald-800 font-medium">🤖 ' + data.message + '</p>' +
        '<p class="text-emerald-600 text-sm mt-1">Combining 60% CF + 40% semantic similarity for best results</p>' +
      '</div>';
      
      let mostRecentSubcat = null;
      
      data.suggestions.forEach(function(s) {
        if (s.replacement_product && s.replacement_product.subcat) {
          mostRecentSubcat = s.replacement_product.subcat;
          // Register green dot for Hybrid AI system
          addRecommendationDot(s.replacement_product.subcat, 'hybrid');
        }
        const card = document.createElement('div');
        card.className = 'bg-white border border-emerald-200 rounded-xl p-5 hover:shadow-lg transition-all';
        
        card.innerHTML = '<div class="mb-3">' +
          '<div class="flex items-center space-x-2 mb-2">' +
            '<svg class="w-5 h-5 text-emerald-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">' +
              '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7h12m0 0l-4-4m4 4l-4 4m0 6H4m0 0l4 4m-4-4l4-4"></path>' +
            '</svg>' +
            '<span class="text-gray-700">Replace:</span>' +
          '</div>' +
          '<div class="ml-7">' +
            '<div class="text-sm text-gray-600 line-through">' + s.replace.substring(0, 60) + '...</div>' +
            '<div class="text-lg font-bold text-emerald-900 mt-1">' + s.with.substring(0, 60) + '...</div>' +
          '</div>' +
        '</div>' +
        '<div class="flex items-center justify-between mb-3 bg-green-50 p-3 rounded-lg">' +
          '<div class="flex items-center space-x-2">' +
            '<svg class="w-5 h-5 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">' +
              '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>' +
            '</svg>' +
            '<span class="font-bold text-green-700">Save $' + s.expected_saving + '</span>' +
          '</div>' +
          '<span class="text-sm text-gray-600">Score: <span class="font-semibold">' + s.similarity + '</span></span>' +
        '</div>' +
        '<div class="text-sm text-gray-600 mb-4 italic">' +
          '<span class="font-semibold text-gray-700">Reason:</span> ' + s.reason +
        '</div>';
        
        const applyBtn = document.createElement('button');
        applyBtn.className = 'w-full bg-gradient-to-r from-emerald-500 to-emerald-600 hover:from-emerald-600 hover:to-emerald-700 text-white font-bold py-3 px-6 rounded-lg transition-all duration-200 transform hover:scale-105 shadow-md';
        applyBtn.innerHTML = '<div class="flex items-center justify-center space-x-2">' +
          '<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">' +
            '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path>' +
          '</svg>' +
          '<span>Apply This Replacement</span>' +
        '</div>';
        applyBtn.onclick = function() { applyReplacement(s.replace, s.replacement_product); };
        
        card.appendChild(applyBtn);
        contentDiv.appendChild(card);
      });
      
      highlightAisleForRecommendation(mostRecentSubcat);
    }
    
    document.getElementById('blendedRecommendations').style.display = 'block';
    updateRecommendationsModule();
  } catch (error) {
    console.error('Error fetching blended recommendations:', error);
    alert('Failed to load hybrid recommendations: ' + error.message);
  }
}

// Toggle User Panel
function toggleUserPanel() {
  const panel = document.getElementById('userPanel');
  const overlay = document.getElementById('userPanelOverlay');
  
  if (panel.classList.contains('translate-x-full')) {
    // Open panel
    panel.classList.remove('translate-x-full');
    overlay.classList.remove('hidden');
    document.body.style.overflow = 'hidden'; // Prevent background scrolling
  } else {
    // Close panel
    panel.classList.add('translate-x-full');
    overlay.classList.add('hidden');
    document.body.style.overflow = ''; // Restore scrolling
  }
}

// Sign-In Modal Functions
function showSignInModal() {
  const modal = document.getElementById('signInModal');
  const overlay = document.getElementById('signInModalOverlay');
  
  modal.classList.remove('hidden', 'scale-95');
  modal.classList.add('scale-100');
  overlay.classList.remove('hidden');
  
  // Focus on name input
  setTimeout(() => {
    document.getElementById('signInName').focus();
  }, 100);
}

function hideSignInModal() {
  const modal = document.getElementById('signInModal');
  const overlay = document.getElementById('signInModalOverlay');
  
  modal.classList.add('scale-95');
  overlay.classList.add('hidden');
  
  setTimeout(() => {
    modal.classList.add('hidden');
  }, 300);
}

function handleSignIn(event) {
  event.preventDefault();
  
  const name = document.getElementById('signInName').value.trim();
  const email = document.getElementById('signInEmail').value.trim();
  
  if (!name || !email) {
    alert('Please enter both name and email.');
    return;
  }
  
  // Store user data in localStorage (demo only)
  const userData = {
    name: name,
    email: email,
    signedInAt: new Date().toISOString()
  };
  
  localStorage.setItem('demoUser', JSON.stringify(userData));
  
  // Update UI
  updateUserDisplay(userData);
  
  // Close modal
  hideSignInModal();
  
  // Show success message
  showNotification('Signed in successfully as ' + name + '!', 'success');
}

function signOut() {
  // Clear user data
  localStorage.removeItem('demoUser');
  
  // Reset UI to guest user
  updateUserDisplay(null);
  
  // Show notification
  showNotification('Signed out successfully', 'info');
}

function clearSessionData() {
  if (confirm('This will clear your cart, purchase history, and sign-in data. Continue?')) {
    // Clear localStorage
    localStorage.removeItem('demoUser');
    
    // Clear cart
    CART = [];
    updateCartDisplay();
    
    // Reset UI
    updateUserDisplay(null);
    
    showNotification('Session data cleared', 'info');
  }
}

function updateUserDisplay(userData) {
  const displayName = document.getElementById('userDisplayName');
  const displayEmail = document.getElementById('userDisplayEmail');
  const signInBtn = document.getElementById('signInBtn');
  const signOutBtn = document.getElementById('signOutBtn');
  
  if (userData) {
    // Signed in
    displayName.textContent = userData.name;
    displayEmail.textContent = userData.email;
    signInBtn.style.display = 'none';
    signOutBtn.style.display = 'flex';
  } else {
    // Guest user
    displayName.textContent = 'Guest User';
    displayEmail.textContent = 'Session Active';
    signInBtn.style.display = 'flex';
    signOutBtn.style.display = 'none';
  }
}

function loadUserData() {
  // Load user data from localStorage
  const userDataStr = localStorage.getItem('demoUser');
  
  if (userDataStr) {
    try {
      const userData = JSON.parse(userDataStr);
      updateUserDisplay(userData);
    } catch (e) {
      console.error('Error loading user data:', e);
      localStorage.removeItem('demoUser');
    }
  }
}

function showNotification(message, type = 'success') {
  // Create notification element
  const notification = document.createElement('div');
  notification.className = 'fixed top-20 right-6 z-50 px-6 py-4 rounded-lg shadow-xl transform transition-all duration-300 translate-x-0';
  
  if (type === 'success') {
    notification.className += ' bg-green-500 text-white';
  } else if (type === 'info') {
    notification.className += ' bg-blue-500 text-white';
  }
  
  notification.innerHTML = '<div class="flex items-center space-x-3">' +
    '<svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">' +
      '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path>' +
    '</svg>' +
    '<span class="font-semibold">' + message + '</span>' +
  '</div>';
  
  document.body.appendChild(notification);
  
  // Animate in
  setTimeout(() => {
    notification.style.transform = 'translateX(0)';
  }, 10);
  
  // Remove after 3 seconds
  setTimeout(() => {
    notification.style.transform = 'translateX(400px)';
    setTimeout(() => {
      document.body.removeChild(notification);
    }, 300);
  }, 3000);
}

// Auto-load products on page load
document.addEventListener('DOMContentLoaded', function() {
  console.log('Page loaded, auto-loading products...');
  refreshProducts();
  
  // Load user data
  loadUserData();
  
  // Add budget input change listener
  const budgetInput = document.getElementById('budget');
  if (budgetInput) {
    budgetInput.addEventListener('input', function() {
      updateCartDisplay();
    });
  }
});
