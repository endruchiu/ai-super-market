// Shopping Cart Application
let CART = [];
let CURRENT_CATEGORY = '';
let RECOMMENDATION_HIGHLIGHT_CATEGORY = null;

// Track which recommendation systems have suggestions for each subcategory
// Format: { subcategory: { budget: true, cf: true, hybrid: true } }
let RECOMMENDATION_DOTS = {};

// Store ML-learned feature importance
let MODEL_FEATURE_IMPORTANCE = null;

// ==================== RECOMMENDATION TRACKING SYSTEM ====================
// Store active recommendations shown to user with timestamps
// Format: { recommendationId: { timestamp, originalProduct, recommendedProduct, savings, reason, nutrition } }
let ACTIVE_RECOMMENDATIONS = {};

// Store which cart items came from AI recommendations
// Format: { cartItemTitle: { recommendationId, timestamp, originalProduct } }
let AI_RECOMMENDED_ITEMS = {};

// Track scroll depth on recommendations module
let MAX_SCROLL_DEPTH = 0;
let SCROLL_TRACKING_INITIALIZED = false;

function fmt(n) { 
  return (Math.round(n * 100) / 100).toFixed(2); 
}

// ==================== RECOMMENDATION TRACKING FUNCTIONS ====================

// Generate unique recommendation ID
function generateRecommendationId(originalProduct, recommendedProduct) {
  const timestamp = Date.now();
  const productCombo = `${originalProduct.id || originalProduct.title}_${recommendedProduct.id}`;
  return `rec_${timestamp}_${productCombo.substring(0, 20)}`;
}

// Track when recommendations are shown to user
function trackRecommendationShown(recommendationData) {
  try {
    const recId = generateRecommendationId(recommendationData.originalProduct, recommendationData.recommendedProduct);
    
    // Extract nutrition data for drift detection
    const originalNutrition = recommendationData.originalProduct.nutrition || {};
    const recommendedNutrition = recommendationData.recommendedProduct.nutrition || {};
    
    // Store in active recommendations
    ACTIVE_RECOMMENDATIONS[recId] = {
      recommendationId: recId,
      timestamp: Date.now(),
      shownAt: new Date().toISOString(),
      originalProduct: {
        id: recommendationData.originalProduct.id,
        title: recommendationData.originalProduct.title,
        price: recommendationData.originalProduct.price,
        subcat: recommendationData.originalProduct.subcat,
        nutrition: {
          protein: originalNutrition.Protein || originalNutrition.protein || 0,
          sugar: originalNutrition.Sugar || originalNutrition.sugar || 0,
          calories: originalNutrition.Calories || originalNutrition.calories || 0
        }
      },
      recommendedProduct: {
        id: recommendationData.recommendedProduct.id,
        title: recommendationData.recommendedProduct.title,
        price: recommendationData.recommendedProduct.price,
        subcat: recommendationData.recommendedProduct.subcat,
        nutrition: {
          protein: recommendedNutrition.Protein || recommendedNutrition.protein || 0,
          sugar: recommendedNutrition.Sugar || recommendedNutrition.sugar || 0,
          calories: recommendedNutrition.Calories || recommendedNutrition.calories || 0
        }
      },
      expectedSaving: recommendationData.expectedSaving,
      reason: recommendationData.reason,
      system: recommendationData.system || 'hybrid'
    };
    
    // Send to backend
    sendInteractionToBackend({
      event_type: 'recommendation_shown',
      recommendation_id: recId,
      ...ACTIVE_RECOMMENDATIONS[recId]
    });
    
    console.log('✓ Tracked recommendation shown:', recId);
    return recId;
  } catch (error) {
    console.error('Error tracking recommendation shown:', error);
    return null;
  }
}

// Track user action on recommendation (accept/dismiss)
function trackRecommendationAction(actionType, originalProduct, recommendedProduct, recId) {
  try {
    // Find the recommendation in active recommendations
    const recommendation = ACTIVE_RECOMMENDATIONS[recId];
    
    if (!recommendation) {
      console.warn('Recommendation not found in active tracking:', recId);
      return;
    }
    
    // Calculate time-to-action
    const timeToAction = Date.now() - recommendation.timestamp;
    
    // Prepare interaction data
    const interactionData = {
      event_type: `recommendation_${actionType}`,
      recommendation_id: recId,
      action_type: actionType,
      original_product: recommendation.originalProduct,
      recommended_product: recommendation.recommendedProduct,
      expected_saving: recommendation.expectedSaving,
      reason: recommendation.reason,
      shown_at: recommendation.shownAt,
      action_at: new Date().toISOString(),
      time_to_action_ms: timeToAction,
      time_to_action_seconds: Math.round(timeToAction / 1000),
      scroll_depth: MAX_SCROLL_DEPTH,
      system: recommendation.system
    };
    
    // If accepted, track the item as AI-recommended
    if (actionType === 'accept') {
      AI_RECOMMENDED_ITEMS[recommendedProduct.title] = {
        recommendationId: recId,
        timestamp: Date.now(),
        originalProduct: originalProduct.title,
        addedAt: new Date().toISOString()
      };
    }
    
    // Send to backend
    sendInteractionToBackend(interactionData);
    
    // Remove from active recommendations
    delete ACTIVE_RECOMMENDATIONS[recId];
    
    console.log(`✓ Tracked recommendation ${actionType}:`, recId, `(${timeToAction}ms)`);
  } catch (error) {
    console.error('Error tracking recommendation action:', error);
  }
}

// Monitor scroll depth on recommendations module
function trackScrollDepth() {
  const recommendationsModule = document.getElementById('recommendationsModule');
  if (!recommendationsModule || recommendationsModule.style.display === 'none') {
    return;
  }
  
  try {
    const moduleRect = recommendationsModule.getBoundingClientRect();
    const moduleHeight = moduleRect.height;
    const viewportHeight = window.innerHeight;
    
    // Calculate visible portion of module
    const visibleTop = Math.max(0, -moduleRect.top);
    const visibleBottom = Math.min(moduleHeight, viewportHeight - moduleRect.top);
    const visibleHeight = Math.max(0, visibleBottom - visibleTop);
    
    // Calculate scroll depth percentage
    const scrollDepth = moduleHeight > 0 ? (visibleHeight / moduleHeight) * 100 : 0;
    
    // Update max scroll depth
    if (scrollDepth > MAX_SCROLL_DEPTH) {
      MAX_SCROLL_DEPTH = Math.round(scrollDepth);
    }
  } catch (error) {
    console.error('Error tracking scroll depth:', error);
  }
}

// Initialize scroll tracking for recommendations module
function initializeScrollTracking() {
  if (SCROLL_TRACKING_INITIALIZED) {
    return;
  }
  
  // Add scroll listener
  window.addEventListener('scroll', trackScrollDepth, { passive: true });
  
  // Add resize listener (affects scroll depth calculation)
  window.addEventListener('resize', trackScrollDepth, { passive: true });
  
  SCROLL_TRACKING_INITIALIZED = true;
  console.log('✓ Scroll tracking initialized for recommendations');
}

// Send interaction data to backend
async function sendInteractionToBackend(interactionData) {
  try {
    const response = await fetch('/api/analytics/track-interaction', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(interactionData)
    });
    
    if (response.ok) {
      console.log('✓ Interaction tracked:', interactionData.event_type);
    } else if (response.status === 404) {
      // Endpoint not implemented yet - silently ignore
      console.log('ℹ Analytics endpoint not available yet');
    } else {
      console.warn('Failed to track interaction:', response.status);
    }
  } catch (error) {
    // Don't break app if tracking fails
    console.warn('Tracking error (non-critical):', error.message);
  }
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
      
      // Don't auto-track passive views - only track active clicks/adds
      // trackEvent('view', p.id);
      
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
  
  // Track cart_add event for model learning
  trackEvent('cart_add', p.id);
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
    
    // Update spending progress bar
    updateSpendingProgress(sum, budget);
  }
  
  // Also update progress bar when cart is empty
  if (CART.length === 0) {
    updateSpendingProgress(0, budget);
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

function updateSpendingProgress(spent, budget) {
  const spentLabel = document.getElementById('spentLabel');
  const remainingLabel = document.getElementById('remainingLabel');
  const progressBar = document.getElementById('spendingProgress');
  
  if (!spentLabel || !remainingLabel || !progressBar) return;
  
  const remaining = budget - spent;
  const percentSpent = budget > 0 ? Math.min((spent / budget) * 100, 100) : 0;
  
  // Update labels
  spentLabel.textContent = `$${fmt(spent)} / $${fmt(budget)}`;
  
  // Update remaining label with color coding
  if (remaining >= 0) {
    remainingLabel.textContent = `$${fmt(remaining)} left`;
    remainingLabel.className = 'text-green-600 font-semibold';
  } else {
    remainingLabel.textContent = `$${fmt(Math.abs(remaining))} over`;
    remainingLabel.className = 'text-red-600 font-semibold';
  }
  
  // Update progress bar
  progressBar.style.width = percentSpent + '%';
  
  // Change color based on spending
  if (percentSpent < 75) {
    // Under 75% - green
    progressBar.className = 'h-full bg-gradient-to-r from-green-400 to-green-500 rounded-full transition-all duration-300';
  } else if (percentSpent < 100) {
    // 75-100% - yellow warning
    progressBar.className = 'h-full bg-gradient-to-r from-yellow-400 to-yellow-500 rounded-full transition-all duration-300';
  } else {
    // Over budget - red
    progressBar.className = 'h-full bg-gradient-to-r from-red-400 to-red-500 rounded-full transition-all duration-300';
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
  const item = CART[i];
  
  // Check if this was an AI-recommended item
  const aiRecommendation = AI_RECOMMENDED_ITEMS[item.title];
  
  if (aiRecommendation) {
    // Track removal of AI-recommended item
    sendInteractionToBackend({
      event_type: 'ai_recommendation_removed',
      recommendation_id: aiRecommendation.recommendationId,
      removed_product: {
        id: item.id,
        title: item.title,
        price: item.price,
        subcat: item.subcat
      },
      original_product_title: aiRecommendation.originalProduct,
      added_at: aiRecommendation.addedAt,
      removed_at: new Date().toISOString(),
      time_in_cart_ms: Date.now() - aiRecommendation.timestamp
    });
    
    console.log('✓ Tracked removal of AI-recommended item:', item.title);
    
    // Remove from AI recommendations tracking
    delete AI_RECOMMENDED_ITEMS[item.title];
  }
  
  CART.splice(i, 1);
  updateCartDisplay();
  updateBadge();
  
  // Track cart_remove event for model learning
  if (item && item.id) {
    trackEvent('cart_remove', item.id);
  }
}

function dismissRecommendation(card, recId, originalProduct, recommendedProduct) {
  // Track the dismiss action before removing
  if (recId && originalProduct && recommendedProduct) {
    trackRecommendationAction('dismiss', originalProduct, recommendedProduct, recId);
  }
  
  // Smooth fade-out animation
  card.style.transition = 'opacity 0.3s ease-out, transform 0.3s ease-out';
  card.style.opacity = '0';
  card.style.transform = 'scale(0.95)';
  
  // Remove card after animation
  setTimeout(() => {
    card.remove();
    
    // Check if there are any remaining recommendations
    const contentDiv = document.getElementById('blendedRecsContent');
    const remainingCards = contentDiv.querySelectorAll('.bg-gradient-to-br');
    
    if (remainingCards.length === 0) {
      // No more recommendations, hide the panel
      document.getElementById('blendedRecommendations').style.display = 'none';
      showToast('All recommendations dismissed', 'info');
    } else {
      showToast('Recommendation dismissed', 'success');
    }
  }, 300);
}

function showToast(message, type = 'success') {
  // Create toast notification
  const toast = document.createElement('div');
  const bgColor = type === 'success' ? 'bg-green-500' : type === 'info' ? 'bg-blue-500' : 'bg-gray-500';
  
  toast.className = `fixed bottom-6 right-6 ${bgColor} text-white px-4 py-3 rounded-lg shadow-lg flex items-center space-x-2 z-50 transition-all duration-300`;
  toast.style.opacity = '0';
  toast.style.transform = 'translateY(20px)';
  
  toast.innerHTML = 
    '<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">' +
      '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path>' +
    '</svg>' +
    '<span class="font-medium">' + message + '</span>';
  
  document.body.appendChild(toast);
  
  // Fade in
  setTimeout(() => {
    toast.style.opacity = '1';
    toast.style.transform = 'translateY(0)';
  }, 10);
  
  // Fade out and remove after 2.5 seconds
  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateY(20px)';
    setTimeout(() => toast.remove(), 300);
  }, 2500);
}

function applyReplacement(originalTitle, replacementProduct, recId) {
  console.log('Applying replacement:', originalTitle, '->', replacementProduct.title);
  
  const idx = CART.findIndex(x => x.title === originalTitle);
  if (idx === -1) {
    alert('Original item not found in cart. It may have been removed.');
    return;
  }
  
  // Get original product before removing from cart
  const originalProduct = CART[idx];
  
  // Track the accept action before applying
  if (recId) {
    trackRecommendationAction('accept', originalProduct, replacementProduct, recId);
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
      '<div class="flex items-center mb-3 bg-green-50 p-3 rounded-lg">' +
        '<div class="flex items-center space-x-2">' +
          '<svg class="w-5 h-5 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">' +
            '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>' +
          '</svg>' +
          '<span class="font-bold text-green-700">Save $' + s.expected_saving + '</span>' +
        '</div>' +
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
      
      // Refresh user stats after purchase
      const userData = localStorage.getItem('currentUser');
      if (userData) {
        const user = JSON.parse(userData);
        updateUserStats(user.email);
      }
      
      // Trigger auto-retrain after purchase
      triggerAutoRetrain();
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
        '<div class="flex items-center mb-3 bg-green-50 p-3 rounded-lg">' +
          '<div class="flex items-center space-x-2">' +
            '<svg class="w-5 h-5 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">' +
              '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>' +
            '</svg>' +
            '<span class="font-bold text-green-700">Save $' + s.expected_saving + '</span>' +
          '</div>' +
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

// Fetch ML feature importance from trained model
async function fetchFeatureImportance() {
  try {
    const res = await fetch('/api/model/feature-importance');
    const data = await res.json();
    if (data.model_available) {
      MODEL_FEATURE_IMPORTANCE = data;
    }
  } catch (error) {
    console.error('Error fetching feature importance:', error);
  }
}

// Generate smart description based on learned weights
function getModelWeightsDescription() {
  if (!MODEL_FEATURE_IMPORTANCE || !MODEL_FEATURE_IMPORTANCE.model_available) {
    return 'Combining 60% CF + 40% semantic similarity for best results';
  }
  
  const weights = MODEL_FEATURE_IMPORTANCE.key_weights;
  const training = MODEL_FEATURE_IMPORTANCE.training_info;
  
  // Deterministic check: use model_available flag and training data presence
  // This is robust against API format changes (percentages vs fractions)
  if (!training || !training.samples || training.samples === 0) {
    // Model exists but no training data yet
    return `🎓 LightGBM ML Model Active — Ready to learn from user behavior`;
  }
  
  // Build dynamic description from learned weights
  // Always show ML weights when model is trained, regardless of normalization
  const parts = [];
  if (weights.cf_score > 0) parts.push(`CF ${weights.cf_score.toFixed(0)}%`);
  if (weights.semantic_similarity > 0) parts.push(`Semantic ${weights.semantic_similarity.toFixed(0)}%`);
  if (weights.price_saving > 0) parts.push(`Price ${weights.price_saving.toFixed(0)}%`);
  if (weights.budget_pressure > 0) parts.push(`Budget ${weights.budget_pressure.toFixed(0)}%`);
  
  const description = 'ML-Optimized Weights: ' + parts.join(', ');
  const learnedFrom = `from ${training.samples} sessions`;
  
  return `${description} ${learnedFrom}`;
}

async function getBlendedRecommendations() {
  console.log('getBlendedRecommendations() called');
  const budget = parseFloat(document.getElementById('budget').value || '0');
  
  // Fetch feature importance if not already loaded
  if (!MODEL_FEATURE_IMPORTANCE) {
    await fetchFeatureImportance();
  }
  
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
      // Get dynamic ML weights description
      const weightsDesc = getModelWeightsDescription();
      
      contentDiv.innerHTML = '<div class="bg-emerald-50 border-l-4 border-emerald-500 p-4 mb-4 rounded-r-lg">' +
        '<p class="text-emerald-800 font-medium">🤖 ' + data.message + '</p>' +
        '<p class="text-emerald-600 text-sm mt-1">' + weightsDesc + '</p>' +
      '</div>';
      
      let mostRecentSubcat = null;
      
      data.suggestions.forEach(function(s) {
        if (s.replacement_product && s.replacement_product.subcat) {
          mostRecentSubcat = s.replacement_product.subcat;
          // Register green dot for Hybrid AI system
          addRecommendationDot(s.replacement_product.subcat, 'hybrid');
        }
        
        // Find original product in cart for tracking
        const originalProduct = CART.find(item => item.title === s.replace) || {
          id: null,
          title: s.replace,
          price: 0,
          subcat: '',
          nutrition: {}
        };
        
        // Track recommendation shown
        const recId = trackRecommendationShown({
          originalProduct: originalProduct,
          recommendedProduct: s.replacement_product,
          expectedSaving: s.expected_saving,
          reason: s.reason,
          system: 'hybrid'
        });
        
        // Calculate percentage savings
        const originalPrice = parseFloat(s.replace.match(/\$[\d,.]+/)?.[0]?.replace('$', '').replace(',', '') || 0);
        const replacementPrice = s.replacement_product.price || 0;
        const savingsAmount = parseFloat(s.expected_saving);
        
        // Calculate discount percentage from the cart item price
        let discountPct = 0;
        if (CART && CART.length > 0) {
          const cartItem = CART.find(item => item.title === s.replace);
          if (cartItem && cartItem.price > 0) {
            discountPct = Math.round((savingsAmount / cartItem.price) * 100);
          }
        }
        
        // Determine aisle from subcategory (matches Store Map layout exactly)
        const aisleMap = {
          // Aisle A
          'Meat & Seafood': 'A', 'Seafood': 'A', 'Poultry': 'A', 
          'Deli': 'A', 'Breakfast': 'A', 'Floral': 'A',
          // Aisle B
          'Snacks': 'B',
          // Aisle C
          'Candy': 'C', 'Gift Baskets': 'C', 'Organic': 'C', 
          'Kirkland Signature Grocery': 'C',
          // Aisle D
          'Pantry & Dry Goods': 'D', 'Coffee': 'D',
          // Aisle E
          'Beverages & Water': 'E', 'Paper & Plastic Products': 'E', 'Household': 'E',
          // Aisle F
          'Bakery & Desserts': 'F', 'Cleaning Supplies': 'F', 
          'Laundry Detergent & Supplies': 'F'
        };
        const aisle = aisleMap[s.replacement_product.subcat] || 'A';
        
        // Generate mode-based badge label from ISRec intent score
        // Use actual intent score from backend instead of keyword matching
        // Stricter thresholds for instant responsiveness to shopping behavior changes
        const intentScore = s.intent_score || 0.5;  // Default to balanced if missing
        let modeBadge = 'Smart choice: good quality and price combined';
        
        if (intentScore > 0.65) {
          // Quality mode: User prefers premium/organic products
          modeBadge = 'Same premium quality, just better pricing for you!';
        } else if (intentScore < 0.35) {
          // Economy mode: User is budget-conscious
          modeBadge = 'Huge savings alert: grab this deal now!';
        } else {
          // Balanced mode: User wants value (quality + savings)
          modeBadge = 'Smart choice: good quality and price combined';
        }
        
        const card = document.createElement('div');
        card.className = 'bg-gradient-to-br from-blue-50 to-indigo-50 border-2 border-indigo-100 rounded-xl p-4 shadow-lg hover:shadow-xl transition-all duration-300';
        
        card.innerHTML = 
          // Product comparison block (more compact)
          '<div class="bg-white rounded-lg p-3 mb-3 shadow-sm">' +
            '<div class="flex items-center justify-between gap-2">' +
              '<div class="flex items-center space-x-2 flex-1 min-w-0">' +
                // Smaller product image
                '<div class="w-14 h-14 flex-shrink-0 bg-gradient-to-br from-amber-100 to-amber-200 rounded-lg flex items-center justify-center">' +
                  '<svg class="w-7 h-7 text-amber-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">' +
                    '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4"></path>' +
                  '</svg>' +
                '</div>' +
                '<div class="flex-1 min-w-0">' +
                  '<p class="text-xs text-gray-500">Replace</p>' +
                  '<p class="text-xs text-gray-500 line-through truncate">' + s.replace.substring(0, 35) + (s.replace.length > 35 ? '...' : '') + '</p>' +
                  '<p class="text-sm font-bold text-gray-900 mt-1 truncate">' + s.with.substring(0, 35) + (s.with.length > 35 ? '...' : '') + '</p>' +
                '</div>' +
              '</div>' +
              '<div class="text-right flex-shrink-0">' +
                '<div class="flex items-center justify-end space-x-1 mb-1">' +
                  '<svg class="w-4 h-4 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">' +
                    '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 14l-7 7m0 0l-7-7m7 7V3"></path>' +
                  '</svg>' +
                  '<span class="text-xs font-semibold text-green-600">−$' + s.expected_saving + '</span>' +
                '</div>' +
                '<div class="bg-blue-600 text-white px-3 py-1 rounded-lg font-bold text-sm shadow-sm">$' + 
                  (s.replacement_product.price ? s.replacement_product.price.toFixed(2) : '0.00') + 
                '</div>' +
              '</div>' +
            '</div>' +
          '</div>' +
          
          // Evaluation badges (more compact) - Updated per user request
          '<div class="flex flex-wrap gap-1.5 mb-3">' +
            // 1. Price saving percentage badge (downward arrow for price decrease)
            '<div class="bg-green-100 border border-green-300 text-green-800 px-2.5 py-1 rounded-full text-xs font-semibold flex items-center space-x-1">' +
              '<svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">' +
                '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 17h8m0 0v-8m0 8l-8-8-4 4-6-6"></path>' +
              '</svg>' +
              '<span>' + (discountPct > 0 ? discountPct + '% OFF' : 'Save $' + s.expected_saving) + '</span>' +
            '</div>' +
            // 2. Similarity badge removed per user request
            // 3. Mode-based badge (replaces "Intent Match") - uses LLM-generated context
            '<div class="bg-purple-100 border border-purple-300 text-purple-800 px-2.5 py-1 rounded-full text-xs font-semibold flex items-center space-x-1">' +
              '<svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">' +
                '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"></path>' +
              '</svg>' +
              '<span>' + modeBadge + '</span>' +
            '</div>' +
          '</div>' +
          
          // Location indicator (more compact)
          '<div class="bg-yellow-50 border border-yellow-300 rounded-lg p-2 mb-3">' +
            '<div class="flex items-center space-x-1.5">' +
              '<svg class="w-4 h-4 text-yellow-700" fill="none" stroke="currentColor" viewBox="0 0 24 24">' +
                '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z"></path>' +
                '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 11a3 3 0 11-6 0 3 3 0 016 0z"></path>' +
              '</svg>' +
              '<span class="text-xs font-semibold text-yellow-900">📍 Located in Aisle ' + aisle + '</span>' +
            '</div>' +
          '</div>' +
          
          // Reason text (more compact)
          '<div class="text-xs text-gray-600 italic mb-3 px-1">' +
            s.reason +
          '</div>' +
          
          // Action buttons (more compact)
          '<div class="flex space-x-2">' +
            '<button class="flex-1 bg-white border-2 border-gray-300 text-gray-700 font-semibold py-2 px-3 rounded-lg hover:bg-gray-50 hover:border-gray-400 transition-all text-sm">' +
              'Maybe Later' +
            '</button>' +
            '<button class="flex-1 bg-gradient-to-r from-green-500 to-emerald-600 hover:from-green-600 hover:to-emerald-700 text-white font-bold py-2 px-3 rounded-lg transition-all transform hover:scale-105 shadow-md flex items-center justify-center space-x-1.5 text-sm">' +
              '<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">' +
                '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path>' +
              '</svg>' +
              '<span>Accept Swap</span>' +
            '</button>' +
          '</div>';
        
        // Add click handlers to buttons with tracking
        const acceptBtn = card.querySelector('button[class*="bg-gradient-to-r"]');
        acceptBtn.onclick = function() { applyReplacement(s.replace, s.replacement_product, recId); };
        
        const maybeLaterBtn = card.querySelector('button[class*="border-gray-300"]');
        maybeLaterBtn.onclick = function() { dismissRecommendation(card, recId, originalProduct, s.replacement_product); };
        
        // Store recommendation ID with card for later reference
        card.dataset.recommendationId = recId;
        
        contentDiv.appendChild(card);
      });
      
      highlightAisleForRecommendation(mostRecentSubcat);
    }
    
    document.getElementById('blendedRecommendations').style.display = 'block';
    updateRecommendationsModule();
    
    // Initialize scroll tracking for recommendations module
    initializeScrollTracking();
    
    // Reset scroll depth tracking for new recommendations
    MAX_SCROLL_DEPTH = 0;
    
    // Scroll recommendation module into view
    const recommendationsModule = document.getElementById('recommendationsModule');
    if (recommendationsModule && recommendationsModule.style.display === 'block') {
      console.log('✅ Hybrid AI recommendations displayed!');
      recommendationsModule.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      
      // Track initial scroll depth
      setTimeout(() => trackScrollDepth(), 100);
    }
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

// Handle name/email login
async function handleEmailLogin(event) {
  event.preventDefault();
  
  const name = document.getElementById('loginName').value.trim();
  const email = document.getElementById('loginEmail').value.trim();
  
  if (!name || !email) {
    showNotification('Please enter both name and email', 'error');
    return;
  }
  
  try {
    // Call backend to sign in user
    const response = await fetch('/api/user/signin', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, email })
    });
    
    const data = await response.json();
    
    if (response.ok && data.success) {
      // Store user data in localStorage
      const userData = {
        name: data.user.name,
        email: data.user.email,
        userId: data.user.id,
        signedInAt: new Date().toISOString()
      };
      
      localStorage.setItem('currentUser', JSON.stringify(userData));
      
      // Update session ID globally
      SESSION_ID = email;
      
      // Update UI
      updateUserDisplay(userData);
      
      // Hide login section, show user info
      document.getElementById('loginSection').style.display = 'none';
      
      // Reload cart and user data
      await loadUserData();
      
      showNotification(`Welcome back, ${userData.name}!`, 'success');
      
      // Clear form
      document.getElementById('loginForm').reset();
    } else {
      showNotification(data.message || 'Login failed. Please check your credentials.', 'error');
    }
  } catch (error) {
    console.error('Login error:', error);
    showNotification('Login failed. Please try again.', 'error');
  }
}

// User display management
function updateUserDisplay(userData) {
  const userDisplayName = document.getElementById('userDisplayName');
  const userDisplayEmail = document.getElementById('userDisplayEmail');
  const signInBtn = document.getElementById('signInBtn');
  const signOutBtn = document.getElementById('signOutBtn');
  
  if (userData) {
    userDisplayName.textContent = userData.name;
    userDisplayEmail.textContent = userData.email;
    signInBtn.style.display = 'none';
    signOutBtn.style.display = 'flex';
  } else {
    userDisplayName.textContent = 'Guest User';
    userDisplayEmail.textContent = 'Session Active';
    signInBtn.style.display = 'block';
    signOutBtn.style.display = 'none';
  }
}

function signOut() {
  // Clear user data
  localStorage.removeItem('currentUser');
  
  // Reset UI to guest user
  updateUserDisplay(null);
  
  // Show notification
  showNotification('Signed out successfully', 'info');
}

function clearSessionData() {
  if (confirm('This will clear your cart, purchase history, and sign-in data. Continue?')) {
    // Clear localStorage
    localStorage.removeItem('currentUser');
    
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
    
    // Fetch and display user stats
    updateUserStats(userData.email);
    
    // Update replenishment panel for this user
    updateReplenishmentPanel();
  } else {
    // Guest user
    displayName.textContent = 'Guest User';
    displayEmail.textContent = 'Session Active';
    signInBtn.style.display = 'flex';
    signOutBtn.style.display = 'none';
    
    // Clear user stats
    clearUserStats();
    
    // Clear replenishment panel
    clearReplenishmentPanel();
  }
}

async function updateUserStats(email) {
  try {
    const response = await fetch('/api/user/stats', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: email })
    });
    
    const data = await response.json();
    
    if (data.success) {
      // Update stats display
      document.getElementById('userTotalOrders').textContent = data.total_orders;
      document.getElementById('userTotalSpent').textContent = `$${data.total_spent.toFixed(2)}`;
      document.getElementById('userTotalItems').textContent = data.total_items;
      document.getElementById('userAvgOrder').textContent = `$${data.avg_order.toFixed(2)}`;
      
      // Update purchase history
      const historyContainer = document.getElementById('userPurchaseHistory');
      if (data.recent_orders.length > 0) {
        historyContainer.innerHTML = data.recent_orders.map(order => `
          <div class="bg-white border border-gray-200 rounded-lg p-4 hover:border-indigo-300 transition-colors">
            <div class="flex justify-between items-start mb-2">
              <div>
                <div class="text-sm font-semibold text-gray-900">Order #${order.order_id}</div>
                <div class="text-xs text-gray-500">${order.created_at}</div>
              </div>
              <div class="text-sm font-bold text-indigo-600">$${order.total_amount.toFixed(2)}</div>
            </div>
            <div class="text-xs text-gray-600">${order.item_count} item${order.item_count !== 1 ? 's' : ''}</div>
          </div>
        `).join('');
      } else {
        historyContainer.innerHTML = `
          <div class="bg-gray-50 border border-gray-200 rounded-lg p-4 text-center text-gray-500 text-sm">
            No purchase history yet. Complete a purchase to see your order history!
          </div>
        `;
      }
    }
  } catch (error) {
    console.error('Error fetching user stats:', error);
  }
}

function clearUserStats() {
  // Reset stats to 0
  document.getElementById('userTotalOrders').textContent = '0';
  document.getElementById('userTotalSpent').textContent = '$0.00';
  document.getElementById('userTotalItems').textContent = '0';
  document.getElementById('userAvgOrder').textContent = '$0.00';
  
  // Reset purchase history
  document.getElementById('userPurchaseHistory').innerHTML = `
    <div class="bg-gray-50 border border-gray-200 rounded-lg p-4 text-center text-gray-500 text-sm">
      No purchase history yet. Complete a purchase to see your order history!
    </div>
  `;
}

function clearReplenishmentPanel() {
  // Hide all sections and show empty state
  const dueNowSection = document.getElementById('dueNowSection');
  const dueSoonSection = document.getElementById('dueSoonSection');
  const upcomingSection = document.getElementById('upcomingSection');
  const emptyState = document.getElementById('replenishEmpty');
  const statsSection = document.getElementById('replenishStats');
  
  if (emptyState) emptyState.style.display = 'block';
  if (statsSection) statsSection.style.display = 'none';
  if (dueNowSection) dueNowSection.style.display = 'none';
  if (dueSoonSection) dueSoonSection.style.display = 'none';
  if (upcomingSection) upcomingSection.style.display = 'none';
  
  // Clear the lists
  const dueNowList = document.getElementById('dueNowList');
  const dueSoonList = document.getElementById('dueSoonList');
  const upcomingList = document.getElementById('upcomingList');
  
  if (dueNowList) dueNowList.innerHTML = '';
  if (dueSoonList) dueSoonList.innerHTML = '';
  if (upcomingList) upcomingList.innerHTML = '';
}

async function loadUserData() {
  // Load user data from localStorage
  const userDataStr = localStorage.getItem('currentUser');
  
  if (userDataStr) {
    try {
      const userData = JSON.parse(userDataStr);
      updateUserDisplay(userData);
      
      // Restore backend session
      try {
        await fetch('/api/user/signin', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ name: userData.name, email: userData.email })
        });
      } catch (error) {
        console.error('Backend session restore failed:', error);
      }
    } catch (e) {
      console.error('Error loading user data:', e);
      localStorage.removeItem('currentUser');
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

// Track user events for model learning
async function trackEvent(eventType, productId) {
  try {
    const response = await fetch('/api/track-event', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        event_type: eventType,
        product_id: productId
      })
    });
    
    if (response.ok) {
      console.log(`✓ Tracked ${eventType} for product ${productId}`);
    } else if (response.status === 400) {
      // Silently ignore 400 errors (user session not ready yet)
      // Events will be tracked once user interacts with the site
      return;
    }
  } catch (error) {
    // Silently ignore errors to avoid spamming console
    return;
  }
}

// Auto-retrain model after purchases
let purchaseCount = 0;
const RETRAIN_THRESHOLD = 5; // Retrain after every 5 purchases

async function triggerAutoRetrain() {
  purchaseCount++;
  console.log(`Purchase count: ${purchaseCount}/${RETRAIN_THRESHOLD}`);
  
  if (purchaseCount >= RETRAIN_THRESHOLD) {
    purchaseCount = 0;
    
    showToast('🎓 Learning from your purchases...', 'info');
    
    try {
      const response = await fetch('/api/model/retrain', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });
      
      const data = await response.json();
      
      if (data.success) {
        console.log('✓ Model retraining started');
        setTimeout(() => {
          showToast('✨ AI model updated! Recommendations improved!', 'success');
          // Refresh feature importance display
          fetchFeatureImportance();
        }, 5000); // Show success after 5 seconds
      }
    } catch (error) {
      console.error('Auto-retrain error:', error);
    }
  }
}

// Show toast notification
function showToast(message, type = 'success') {
  const toast = document.createElement('div');
  toast.className = 'fixed top-6 right-6 px-6 py-4 rounded-xl shadow-2xl z-50 transform transition-all duration-300 ease-in-out';
  toast.style.transform = 'translateX(400px)';
  
  if (type === 'success') {
    toast.className += ' bg-emerald-500 text-white';
  } else if (type === 'info') {
    toast.className += ' bg-blue-500 text-white';
  } else if (type === 'warning') {
    toast.className += ' bg-yellow-500 text-white';
  }
  
  toast.innerHTML = '<div class="flex items-center space-x-3">' +
    '<span class="text-2xl">🎓</span>' +
    '<span class="font-semibold">' + message + '</span>' +
  '</div>';
  
  document.body.appendChild(toast);
  
  setTimeout(() => {
    toast.style.transform = 'translateX(0)';
  }, 10);
  
  setTimeout(() => {
    toast.style.transform = 'translateX(400px)';
    setTimeout(() => {
      toast.remove();
    }, 300);
  }, 4000);
}

// Update ISRec Intent Monitor
async function updateISRecMonitor() {
  try {
    const response = await fetch('/api/isrec/intent');
    const data = await response.json();
    
    // Update intent score and pointer position
    const scoreElement = document.getElementById('isrecScore');
    const pointerElement = document.getElementById('isrecPointer');
    const modeElement = document.getElementById('isrecMode');
    
    if (scoreElement) {
      scoreElement.textContent = data.intent_score.toFixed(2);
    }
    
    // Move pointer (0.0 = left/0%, 0.5 = center/50%, 1.0 = right/100%)
    if (pointerElement) {
      pointerElement.style.left = (data.intent_score * 100) + '%';
    }
    
    // Update mode badge
    if (modeElement) {
      modeElement.textContent = data.mode.toUpperCase();
      modeElement.className = 'text-xs font-bold px-3 py-1 rounded-full';
      
      if (data.mode === 'quality') {
        modeElement.className += ' bg-purple-500 text-white';
      } else if (data.mode === 'economy') {
        modeElement.className += ' bg-green-500 text-white';
      } else {
        modeElement.className += ' bg-gray-200 text-gray-700';
      }
    }
    
    // Update signals
    const qualityElement = document.getElementById('qualitySignals');
    const economyElement = document.getElementById('economySignals');
    
    if (qualityElement) {
      qualityElement.textContent = data.quality_signals.toFixed(1);
    }
    if (economyElement) {
      economyElement.textContent = data.economy_signals.toFixed(1);
    }
    
    // Update recent actions
    const actionsElement = document.getElementById('recentActions');
    if (actionsElement && data.recent_actions && data.recent_actions.length > 0) {
      actionsElement.innerHTML = data.recent_actions.map(action => {
        let icon = '👁️';
        if (action.type === 'cart_add') icon = '➕';
        if (action.type === 'cart_remove') icon = '➖';
        
        return `<div class="flex items-center justify-between py-1 border-b border-gray-100">
          <div class="flex items-center space-x-2">
            <span>${icon}</span>
            <span class="text-gray-700 truncate">${action.product}</span>
          </div>
          <span class="text-gray-500 ml-2">$${action.price.toFixed(2)}</span>
        </div>`;
      }).join('');
    } else if (actionsElement) {
      actionsElement.innerHTML = '<div class="text-gray-500 text-center py-2">No activity yet</div>';
    }
    
    // Update message
    const messageElement = document.getElementById('isrecMessage');
    if (messageElement) {
      messageElement.textContent = data.message;
    }
    
  } catch (error) {
    console.error('ISRec monitor error:', error);
  }
}

// Auto-load products on page load
document.addEventListener('DOMContentLoaded', function() {
  console.log('Page loaded, auto-loading products...');
  refreshProducts();
  
  // Load user data
  loadUserData();
  
  // Add budget slider change listener
  const budgetInput = document.getElementById('budget');
  if (budgetInput) {
    budgetInput.addEventListener('input', function() {
      // Update budget value display
      const budgetValue = document.getElementById('budgetValue');
      if (budgetValue) {
        budgetValue.textContent = '$' + budgetInput.value;
      }
      
      // Update cart display and progress bar
      updateCartDisplay();
    });
  }
  
  // Start ISRec monitoring (update every 3 seconds)
  updateISRecMonitor();
  setInterval(updateISRecMonitor, 3000);
  
  // Start Replenishment monitoring (update every 10 seconds)
  updateReplenishmentPanel();
  setInterval(updateReplenishmentPanel, 10000);
});

// ==================== REPLENISHMENT SYSTEM ====================

async function updateReplenishmentPanel() {
  try {
    // Check if user is logged in - only show reminders for logged-in users
    const userDataStr = localStorage.getItem('currentUser');
    if (!userDataStr) {
      // Guest user - show empty state
      clearReplenishmentPanel();
      return;
    }
    
    const response = await fetch('/api/replenishment/due-soon?days_ahead=7');
    const data = await response.json();
    
    // Show/hide sections based on data
    const dueNowSection = document.getElementById('dueNowSection');
    const dueSoonSection = document.getElementById('dueSoonSection');
    const upcomingSection = document.getElementById('upcomingSection');
    const emptyState = document.getElementById('replenishEmpty');
    const statsSection = document.getElementById('replenishStats');
    
    const hasItems = data.due_now.length + data.due_soon.length + data.upcoming.length > 0;
    
    if (hasItems) {
      emptyState.style.display = 'none';
      statsSection.style.display = 'block';
      
      // Update stats
      const statsText = document.getElementById('replenishStatsText');
      statsText.textContent = `Tracking ${data.total_active_cycles} product${data.total_active_cycles !== 1 ? 's' : ''} for replenishment`;
      
      // Due Now
      if (data.due_now.length > 0) {
        dueNowSection.style.display = 'block';
        const dueNowList = document.getElementById('dueNowList');
        dueNowList.innerHTML = data.due_now.map(item => renderReplenishmentItem(item, 'blue')).join('');
      } else {
        dueNowSection.style.display = 'none';
      }
      
      // Due Soon
      if (data.due_soon.length > 0) {
        dueSoonSection.style.display = 'block';
        const dueSoonList = document.getElementById('dueSoonList');
        dueSoonList.innerHTML = data.due_soon.map(item => renderReplenishmentItem(item, 'orange')).join('');
      } else {
        dueSoonSection.style.display = 'none';
      }
      
      // Upcoming
      if (data.upcoming.length > 0) {
        upcomingSection.style.display = 'block';
        const upcomingList = document.getElementById('upcomingList');
        upcomingList.innerHTML = data.upcoming.map(item => `
          <div class="flex items-center justify-between py-1">
            <span class="truncate">${item.title.substring(0, 30)}...</span>
            <span class="text-gray-400 ml-2">${item.days_until_due}d</span>
          </div>
        `).join('');
      } else {
        upcomingSection.style.display = 'none';
      }
    } else {
      emptyState.style.display = 'block';
      statsSection.style.display = 'none';
      dueNowSection.style.display = 'none';
      dueSoonSection.style.display = 'none';
      upcomingSection.style.display = 'none';
    }
    
  } catch (error) {
    console.error('Replenishment panel error:', error);
  }
}

function renderReplenishmentItem(item, urgencyColor) {
  const urgencyClass = urgencyColor === 'blue' ? 'bg-blue-50 border-blue-200' : 'bg-orange-50 border-orange-200';
  const textClass = urgencyColor === 'blue' ? 'text-blue-700' : 'text-orange-700';
  
  // Prediction type badge
  const isPredicted = item.prediction_type === 'predicted';
  const badgeClass = isPredicted 
    ? 'bg-purple-100 text-purple-700' 
    : 'bg-green-100 text-green-700';
  const badgeText = isPredicted 
    ? `🔮 Predicted (${Math.round((item.cf_confidence || 0.3) * 100)}% confidence)` 
    : '✓ Personalized';
  
  // More conversational timing messages
  let daysText;
  if (item.days_until_due === 0) {
    daysText = 'You might run out today';
  } else if (item.days_until_due < 0) {
    const daysAgo = Math.abs(item.days_until_due);
    daysText = daysAgo === 1 
      ? 'You probably ran out yesterday' 
      : `You probably ran out ${daysAgo} days ago`;
  } else {
    daysText = item.days_until_due === 1 
      ? 'You might run out tomorrow' 
      : `You might run out in ${item.days_until_due} days`;
  }
  
  // Urgency indicator
  const urgencyScore = item.urgency_score || 0;
  let urgencyLabel = '';
  let urgencyBadge = '';
  
  if (item.days_until_due < 0) {
    urgencyLabel = `⚠️ OVERDUE (${Math.abs(item.days_until_due)}d ago)`;
    urgencyBadge = 'bg-red-500 text-white';
  } else if (item.days_until_due <= 3) {
    urgencyLabel = `⏰ DUE SOON (${item.days_until_due}d)`;
    urgencyBadge = 'bg-orange-500 text-white';
  } else if (item.days_until_due <= 7) {
    urgencyLabel = `📅 UPCOMING (${item.days_until_due}d)`;
    urgencyBadge = 'bg-blue-500 text-white';
  }
  
  return `
    <div class="p-3 ${urgencyClass} border rounded-lg">
      <div class="flex items-start justify-between mb-2">
        <div class="flex-1">
          <div class="flex items-center gap-2 mb-1">
            <div class="text-sm font-semibold text-gray-900 truncate">${item.title.substring(0, 35)}</div>
          </div>
          <div class="flex flex-wrap gap-1 mb-1">
            <span class="text-xs px-2 py-0.5 rounded ${badgeClass}">${badgeText}</span>
            ${urgencyLabel ? `<span class="text-xs px-2 py-0.5 rounded font-bold ${urgencyBadge}">${urgencyLabel}</span>` : ''}
          </div>
          <div class="text-xs text-gray-600 mt-1">
            Usually restock every ${Math.round(item.interval_days)} days
          </div>
        </div>
      </div>
      <div class="text-xs ${textClass} mb-2 italic">${daysText}</div>
      <div class="flex items-center justify-between">
        <span class="text-sm font-bold text-blue-600">$${item.price.toFixed(2)}</span>
        <div class="flex space-x-2">
          <button onclick="quickAddReplenishment('${item.product_id}')" class="text-xs bg-blue-500 hover:bg-blue-600 text-white px-3 py-1 rounded-md transition-all">
            Quick Add
          </button>
        </div>
      </div>
    </div>
  `;
}

async function quickAddReplenishment(productId) {
  try {
    // Find product in PRODUCTS array
    const product = PRODUCTS.find(p => p.id === productId);
    
    if (!product) {
      showToast('Product not found', 'error');
      return;
    }
    
    // Add to cart
    addToCart(product);
    showToast(`✓ Added ${product.title.substring(0, 30)}... to cart!`, 'success');
    
    // Update replenishment panel after adding
    setTimeout(() => updateReplenishmentPanel(), 500);
    
  } catch (error) {
    console.error('Quick-add error:', error);
    showToast('Failed to add item to cart', 'error');
  }
}

async function skipReplenishment(cycleId) {
  try {
    const response = await fetch('/api/replenishment/skip', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({cycle_id: cycleId, skip_days: 7})
    });
    
    const result = await response.json();
    
    if (result.success) {
      showToast('Reminder snoozed for 7 days', 'success');
      updateReplenishmentPanel();
    } else {
      showToast(`Failed to skip: ${result.error}`, 'error');
    }
  } catch (error) {
    console.error('Skip replenishment error:', error);
    showToast('Failed to skip reminder', 'error');
  }
}
