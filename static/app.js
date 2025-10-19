// AI Supermarket - Virtual Shopping Experience
// State management
let cart = [];
let products = [];
let storeLayout = null;
let currentHighlightedShelf = null;
let currentRoute = null;

// Initialize on page load
window.addEventListener('DOMContentLoaded', () => {
    console.log('Page loaded, initializing supermarket...');
    loadStoreLayout();
    refreshProducts();
    updateCartBadge();
});

// ===== STORE LAYOUT & MAP =====

async function loadStoreLayout() {
    try {
        const response = await fetch('/api/store/layout');
        storeLayout = await response.json();
        renderStoreMap();
        console.log('Store layout loaded:', storeLayout);
    } catch (error) {
        console.error('Failed to load store layout:', error);
    }
}

function renderStoreMap() {
    if (!storeLayout) return;
    
    const svg = document.getElementById('storeMap');
    const existingContent = svg.querySelector('defs');
    svg.innerHTML = '';
    if (existingContent) {
        svg.appendChild(existingContent);
    }
    
    // Draw entrance marker
    const entrance = storeLayout.entrance;
    svg.innerHTML += `
        <text x="${entrance.x}" y="${entrance.y - 10}" font-size="14" font-weight="bold" fill="#059669" text-anchor="start">
            🚪 ENTRANCE
        </text>
        <circle cx="${entrance.x + 40}" cy="${entrance.y}" r="8" fill="#059669" />
    `;
    
    // Draw checkout marker
    const checkout = storeLayout.checkout;
    svg.innerHTML += `
        <text x="${checkout.x}" y="${checkout.y - 10}" font-size="14" font-weight="bold" fill="#dc2626" text-anchor="end">
            CHECKOUT 🛒
        </text>
        <circle cx="${checkout.x}" cy="${checkout.y}" r="8" fill="#dc2626" />
    `;
    
    // Draw each aisle and its shelves
    storeLayout.aisles.forEach(aisle => {
        // Draw aisle container
        const aisleGroup = document.createElementNS("http://www.w3.org/2000/svg", "g");
        aisleGroup.id = `aisle-${aisle.id}`;
        
        // Aisle background
        const aisleRect = document.createElementNS("http://www.w3.org/2000/svg", "rect");
        aisleRect.setAttribute("x", aisle.x);
        aisleRect.setAttribute("y", aisle.y);
        aisleRect.setAttribute("width", aisle.width);
        aisleRect.setAttribute("height", aisle.height);
        aisleRect.setAttribute("class", "aisle-rect");
        aisleRect.setAttribute("rx", "8");
        aisleGroup.appendChild(aisleRect);
        
        // Aisle label
        const aisleLabel = document.createElementNS("http://www.w3.org/2000/svg", "text");
        aisleLabel.setAttribute("x", aisle.x + aisle.width / 2);
        aisleLabel.setAttribute("y", aisle.y - 10);
        aisleLabel.setAttribute("text-anchor", "middle");
        aisleLabel.setAttribute("font-size", "16");
        aisleLabel.setAttribute("font-weight", "bold");
        aisleLabel.setAttribute("fill", "#4f46e5");
        aisleLabel.textContent = `AISLE ${aisle.id}`;
        aisleGroup.appendChild(aisleLabel);
        
        // Aisle name subtitle
        const aisleName = document.createElementNS("http://www.w3.org/2000/svg", "text");
        aisleName.setAttribute("x", aisle.x + aisle.width / 2);
        aisleName.setAttribute("y", aisle.y + 15);
        aisleName.setAttribute("text-anchor", "middle");
        aisleName.setAttribute("font-size", "11");
        aisleName.setAttribute("font-weight", "600");
        aisleName.setAttribute("fill", "#6366f1");
        aisleName.textContent = aisle.name;
        aisleGroup.appendChild(aisleName);
        
        // Draw shelves within the aisle
        aisle.shelves.forEach(shelf => {
            const shelfGroup = document.createElementNS("http://www.w3.org/2000/svg", "g");
            shelfGroup.id = `shelf-${shelf.id}`;
            
            const shelfY = aisle.y + shelf.y_offset + 30;
            const shelfHeight = 60;
            
            const shelfRect = document.createElementNS("http://www.w3.org/2000/svg", "rect");
            shelfRect.setAttribute("x", aisle.x + 5);
            shelfRect.setAttribute("y", shelfY);
            shelfRect.setAttribute("width", aisle.width - 10);
            shelfRect.setAttribute("height", shelfHeight);
            shelfRect.setAttribute("class", "shelf-rect");
            shelfRect.setAttribute("rx", "4");
            shelfRect.setAttribute("data-shelf-id", shelf.id);
            shelfRect.setAttribute("data-shelf-name", shelf.name);
            shelfRect.setAttribute("data-aisle-name", aisle.name);
            
            // Add hover tooltip behavior
            shelfRect.addEventListener('mouseenter', (e) => {
                const shelfName = e.target.getAttribute('data-shelf-name');
                const aisleName = e.target.getAttribute('data-aisle-name');
                document.getElementById('currentLocation').textContent = `${aisleName} - ${shelfName}`;
            });
            shelfRect.addEventListener('mouseleave', () => {
                document.getElementById('currentLocation').textContent = '';
            });
            
            shelfGroup.appendChild(shelfRect);
            
            // Shelf label
            const shelfLabel = document.createElementNS("http://www.w3.org/2000/svg", "text");
            shelfLabel.setAttribute("x", aisle.x + aisle.width / 2);
            shelfLabel.setAttribute("y", shelfY + shelfHeight / 2 + 4);
            shelfLabel.setAttribute("text-anchor", "middle");
            shelfLabel.setAttribute("font-size", "10");
            shelfLabel.setAttribute("font-weight", "600");
            shelfLabel.setAttribute("fill", "#5b21b6");
            shelfLabel.textContent = shelf.name;
            shelfGroup.appendChild(shelfLabel);
            
            aisleGroup.appendChild(shelfGroup);
        });
        
        svg.appendChild(aisleGroup);
    });
}

function highlightShelf(shelfId) {
    // Clear previous highlights
    clearHighlights();
    
    // Highlight the target shelf
    const shelfRect = document.querySelector(`[data-shelf-id="${shelfId}"]`);
    if (shelfRect) {
        shelfRect.classList.add('highlighted');
        currentHighlightedShelf = shelfId;
        
        // Also highlight the parent aisle
        const aisleId = shelfId.charAt(0);
        const aisleRect = document.querySelector(`#aisle-${aisleId} .aisle-rect`);
        if (aisleRect) {
            aisleRect.classList.add('highlighted');
        }
        
        console.log(`Highlighted shelf: ${shelfId}`);
    }
}

function clearHighlights() {
    document.querySelectorAll('.highlighted').forEach(el => el.classList.remove('highlighted'));
    currentHighlightedShelf = null;
    clearRoute();
}

function showRouteToShelf(targetShelfId) {
    // Get coordinates for the target shelf
    fetch('/api/store/location', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({subcat: targetShelfId})
    })
    .then(res => res.json())
    .then(toLocation => {
        // Calculate route from entrance to target
        return fetch('/api/store/route', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                from: storeLayout.entrance,
                to: toLocation
            })
        });
    })
    .then(res => res.json())
    .then(routeData => {
        drawRoute(routeData.waypoints);
    })
    .catch(error => console.error('Route calculation failed:', error));
}

function drawRoute(waypoints) {
    if (!waypoints || waypoints.length < 2) return;
    
    clearRoute();
    
    const svg = document.getElementById('storeMap');
    
    // Create path string from waypoints
    let pathData = `M ${waypoints[0].x} ${waypoints[0].y}`;
    for (let i = 1; i < waypoints.length; i++) {
        pathData += ` L ${waypoints[i].x} ${waypoints[i].y}`;
    }
    
    // Draw the route line
    const routeLine = document.createElementNS("http://www.w3.org/2000/svg", "path");
    routeLine.setAttribute("d", pathData);
    routeLine.setAttribute("class", "route-line");
    routeLine.setAttribute("marker-end", "url(#arrowhead)");
    routeLine.id = "activeRoute";
    
    svg.appendChild(routeLine);
    
    // Add a pulsing marker at destination
    const dest = waypoints[waypoints.length - 1];
    const marker = document.createElementNS("http://www.w3.org/2000/svg", "circle");
    marker.setAttribute("cx", dest.x);
    marker.setAttribute("cy", dest.y);
    marker.setAttribute("r", "8");
    marker.setAttribute("class", "product-marker");
    marker.id = "destinationMarker";
    
    svg.appendChild(marker);
    
    currentRoute = waypoints;
    console.log('Route drawn with', waypoints.length, 'waypoints');
}

function clearRoute() {
    const existingRoute = document.getElementById('activeRoute');
    const existingMarker = document.getElementById('destinationMarker');
    if (existingRoute) existingRoute.remove();
    if (existingMarker) existingMarker.remove();
    currentRoute = null;
}

function resetMap() {
    clearHighlights();
    clearRoute();
    document.getElementById('currentLocation').textContent = '';
}

// ===== PRODUCT MANAGEMENT =====

async function refreshProducts() {
    const subcat = document.getElementById('subcatSel').value;
    const url = subcat ? `/api/products?subcat=${encodeURIComponent(subcat)}` : '/api/products';
    
    console.log('Fetching products from:', url);
    
    try {
        const response = await fetch(url);
        const data = await response.json();
        products = data.items;
        
        // Populate category filter if empty
        if (document.getElementById('subcatSel').options.length === 1 && data.subcats) {
            data.subcats.forEach(sc => {
                const option = document.createElement('option');
                option.value = sc;
                option.textContent = sc;
                document.getElementById('subcatSel').appendChild(option);
            });
        }
        
        renderProductBrowser();
        console.log('Loaded', products.length, 'products');
    } catch (error) {
        console.error('Failed to load products:', error);
    }
}

function renderProductBrowser() {
    const container = document.getElementById('productBrowser');
    container.innerHTML = '';
    
    if (products.length === 0) {
        container.innerHTML = '<p class="text-sm text-gray-500 text-center py-4">No products found</p>';
        return;
    }
    
    products.forEach(product => {
        const card = document.createElement('div');
        card.className = 'bg-gray-50 hover:bg-indigo-50 p-3 rounded-lg border border-gray-200 hover:border-indigo-300 transition-all cursor-pointer';
        card.onclick = () => addToCart(product);
        
        card.innerHTML = `
            <div class="flex items-start justify-between">
                <div class="flex-1 min-w-0 pr-2">
                    <p class="text-sm font-semibold text-gray-900 truncate">${product.title}</p>
                    <p class="text-xs text-indigo-600 font-medium">${product.subcat}</p>
                </div>
                <div class="text-right">
                    <p class="text-sm font-bold text-green-700">$${product.price.toFixed(2)}</p>
                    <button class="mt-1 text-xs bg-indigo-600 hover:bg-indigo-700 text-white px-2 py-1 rounded font-medium">
                        Add
                    </button>
                </div>
            </div>
        `;
        
        container.appendChild(card);
    });
}

// ===== CART MANAGEMENT =====

function addToCart(product) {
    console.log('Adding to cart:', product.title);
    
    const existing = cart.find(item => item.id === product.id);
    if (existing) {
        existing.qty++;
    } else {
        cart.push({...product, qty: 1});
    }
    
    updateCartDisplay();
    updateCartBadge();
    checkBudget();
    showNotification(`Added ${product.title} to cart`);
}

function removeFromCart(productId) {
    cart = cart.filter(item => item.id !== productId);
    updateCartDisplay();
    updateCartBadge();
    checkBudget();
}

function updateQuantity(productId, delta) {
    const item = cart.find(i => i.id === productId);
    if (item) {
        item.qty = Math.max(1, item.qty + delta);
        updateCartDisplay();
        checkBudget();
    }
}

function updateCartDisplay() {
    const container = document.getElementById('cartItems');
    const subtotalEl = document.getElementById('subtotal');
    
    if (cart.length === 0) {
        container.innerHTML = '<p class="text-sm text-gray-500 text-center py-4">Cart is empty</p>';
        subtotalEl.textContent = '';
        return;
    }
    
    const total = cart.reduce((sum, item) => sum + (item.price * item.qty), 0);
    const budget = parseFloat(document.getElementById('budget').value) || 0;
    
    container.innerHTML = '';
    cart.forEach(item => {
        const div = document.createElement('div');
        div.className = 'bg-gray-50 p-2 rounded-lg border border-gray-200';
        div.innerHTML = `
            <div class="flex items-center justify-between">
                <div class="flex-1 min-w-0 pr-2">
                    <p class="text-xs font-semibold text-gray-900 truncate">${item.title}</p>
                    <p class="text-xs text-gray-600">$${item.price.toFixed(2)} × ${item.qty}</p>
                </div>
                <div class="flex items-center space-x-1">
                    <button onclick="updateQuantity('${item.id}', -1)" class="px-1.5 py-0.5 bg-gray-200 hover:bg-gray-300 rounded text-xs font-bold">−</button>
                    <button onclick="updateQuantity('${item.id}', 1)" class="px-1.5 py-0.5 bg-gray-200 hover:bg-gray-300 rounded text-xs font-bold">+</button>
                    <button onclick="removeFromCart('${item.id}')" class="px-1.5 py-0.5 bg-red-500 hover:bg-red-600 text-white rounded text-xs font-bold">×</button>
                </div>
            </div>
        `;
        container.appendChild(div);
    });
    
    const isOverBudget = budget > 0 && total > budget;
    subtotalEl.innerHTML = `
        Total: <span class="${isOverBudget ? 'text-red-600' : 'text-green-700'} font-bold">
            $${total.toFixed(2)}
        </span>
        ${budget > 0 ? ` / $${budget.toFixed(2)}` : ''}
    `;
}

function updateCartBadge() {
    const count = cart.reduce((sum, item) => sum + item.qty, 0);
    document.getElementById('cartBadge').textContent = `Cart: ${count} item${count !== 1 ? 's' : ''}`;
}

// ===== AI RECOMMENDATIONS =====

async function checkBudget() {
    const budget = parseFloat(document.getElementById('budget').value) || 0;
    const total = cart.reduce((sum, item) => sum + (item.price * item.qty), 0);
    
    // Hide all recommendation panels by default
    document.getElementById('budgetSuggestions').style.display = 'none';
    document.getElementById('cfSuggestions').style.display = 'none';
    document.getElementById('hybridSuggestions').style.display = 'none';
    
    if (budget <= 0 || total <= budget || cart.length === 0) {
        return; // No recommendations needed
    }
    
    console.log('Over budget! Fetching all recommendation systems...');
    
    // Fetch all three recommendation systems in parallel
    Promise.all([
        getBudgetRecommendations(),
        getCFRecommendations(),
        getBlendedRecommendations()
    ]);
}

async function getBudgetRecommendations() {
    const budget = parseFloat(document.getElementById('budget').value) || 0;
    
    try {
        const response = await fetch('/api/budget/recommendations', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({cart, budget})
        });
        const data = await response.json();
        
        if (data.suggestions && data.suggestions.length > 0) {
            document.getElementById('budgetSuggestions').style.display = 'block';
            renderSuggestions('budgetList', data.suggestions, 'budget');
        }
    } catch (error) {
        console.error('Failed to get budget recommendations:', error);
    }
}

async function getCFRecommendations() {
    const budget = parseFloat(document.getElementById('budget').value) || 0;
    
    try {
        const response = await fetch('/api/cf/recommendations', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({cart, budget})
        });
        const data = await response.json();
        
        if (data.suggestions && data.suggestions.length > 0) {
            document.getElementById('cfSuggestions').style.display = 'block';
            renderSuggestions('cfList', data.suggestions, 'cf');
        }
    } catch (error) {
        console.error('Failed to get CF recommendations:', error);
    }
}

async function getBlendedRecommendations() {
    const budget = parseFloat(document.getElementById('budget').value) || 0;
    
    try {
        const response = await fetch('/api/blended/recommendations', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({cart, budget})
        });
        const data = await response.json();
        
        if (data.suggestions && data.suggestions.length > 0) {
            document.getElementById('hybridSuggestions').style.display = 'block';
            renderSuggestions('hybridList', data.suggestions, 'hybrid');
        }
    } catch (error) {
        console.error('Failed to get blended recommendations:', error);
    }
}

function renderSuggestions(containerId, suggestions, type) {
    const container = document.getElementById(containerId);
    container.innerHTML = '';
    
    suggestions.forEach(sug => {
        const div = document.createElement('div');
        div.className = 'bg-white p-2 rounded-lg border-2 border-gray-300 hover:border-green-500 transition-all';
        
        const replacement = sug.replacement_product;
        
        div.innerHTML = `
            <p class="text-xs font-semibold text-gray-900 mb-1">${replacement.title}</p>
            <p class="text-xs text-gray-600 mb-2">${sug.reason}</p>
            <div class="flex items-center justify-between">
                <span class="text-xs font-bold text-green-700">Save $${sug.expected_saving}</span>
                <button onclick='applyRecommendation(${JSON.stringify(sug).replace(/'/g, "&#39;")})' 
                        class="text-xs bg-green-600 hover:bg-green-700 text-white px-3 py-1 rounded font-bold">
                    Replace
                </button>
            </div>
        `;
        
        container.appendChild(div);
    });
}

function applyRecommendation(suggestion) {
    const toRemove = suggestion.replace;
    const toAdd = suggestion.replacement_product;
    
    console.log('Applying recommendation:', toRemove, '->', toAdd.title);
    
    // Remove the old item
    const oldItem = cart.find(item => item.title === toRemove);
    if (oldItem) {
        removeFromCart(oldItem.id);
    }
    
    // Add the new item
    addToCart(toAdd);
    
    // Highlight the shelf where the new product is located
    highlightProductLocation(toAdd.subcat);
    
    showNotification(`Replaced with ${toAdd.title}!`);
}

async function highlightProductLocation(subcat) {
    try {
        const response = await fetch('/api/store/location', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({subcat})
        });
        const location = await response.json();
        
        console.log('Product location:', location);
        
        // Highlight the shelf
        highlightShelf(location.shelf_id);
        
        // Show route to the shelf
        showRouteToShelf(location.shelf_id);
        
    } catch (error) {
        console.error('Failed to get product location:', error);
    }
}

// ===== CHECKOUT =====

async function checkout() {
    if (cart.length === 0) {
        alert('Your cart is empty!');
        return;
    }
    
    const total = cart.reduce((sum, item) => sum + (item.price * item.qty), 0);
    
    try {
        const response = await fetch('/api/checkout', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({cart})
        });
        const result = await response.json();
        
        console.log('Checkout successful:', result);
        
        showNotification(`Purchase complete! Total: $${total.toFixed(2)}`);
        
        // Clear cart
        cart = [];
        updateCartDisplay();
        updateCartBadge();
        clearHighlights();
        
        // Hide recommendations
        document.getElementById('budgetSuggestions').style.display = 'none';
        document.getElementById('cfSuggestions').style.display = 'none';
        document.getElementById('hybridSuggestions').style.display = 'none';
        
    } catch (error) {
        console.error('Checkout failed:', error);
        alert('Checkout failed. Please try again.');
    }
}

// ===== UTILITIES =====

function showNotification(message) {
    const notif = document.getElementById('successNotif');
    const msg = document.getElementById('notifMsg');
    msg.textContent = message;
    notif.style.display = 'block';
    
    setTimeout(() => {
        notif.style.display = 'none';
    }, 3000);
}
