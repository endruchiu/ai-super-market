// AI Supermarket - Virtual Shopping Experience
// State management
let cart = [];
let products = [];
let storeLayout = null;
let currentHighlightedShelf = null;
let currentRoute = null;
let currentShelfProducts = null;

// Mock product data for each shelf
const SHELF_PRODUCTS = {
    "A1": [
        {id: "organic-001", title: "Organic Apples", price: 4.99, shelf: "Organic Produce"},
        {id: "organic-002", title: "Organic Spinach", price: 3.49, shelf: "Organic Produce"},
        {id: "organic-003", title: "Organic Carrots", price: 2.99, shelf: "Organic Produce"},
        {id: "organic-004", title: "Organic Tomatoes", price: 5.49, shelf: "Organic Produce"}
    ],
    "A2": [
        {id: "fruit-001", title: "Fresh Strawberries", price: 6.99, shelf: "Fresh Fruits"},
        {id: "fruit-002", title: "Bananas", price: 1.99, shelf: "Fresh Fruits"},
        {id: "fruit-003", title: "Oranges", price: 4.49, shelf: "Fresh Fruits"},
        {id: "fruit-004", title: "Blueberries", price: 7.99, shelf: "Fresh Fruits"}
    ],
    "A3": [
        {id: "veg-001", title: "Broccoli", price: 2.49, shelf: "Fresh Vegetables"},
        {id: "veg-002", title: "Bell Peppers", price: 3.99, shelf: "Fresh Vegetables"},
        {id: "veg-003", title: "Lettuce", price: 2.99, shelf: "Fresh Vegetables"},
        {id: "veg-004", title: "Cucumbers", price: 1.99, shelf: "Fresh Vegetables"}
    ],
    "A4": [
        {id: "bakery-001", title: "Chocolate Croissant", price: 3.49, shelf: "Bakery & Desserts"},
        {id: "bakery-002", title: "Apple Pie", price: 12.99, shelf: "Bakery & Desserts"},
        {id: "bakery-003", title: "Cinnamon Rolls", price: 8.99, shelf: "Bakery & Desserts"},
        {id: "bakery-004", title: "Tiramisu", price: 6.49, shelf: "Bakery & Desserts"}
    ],
    "A5": [
        {id: "bread-001", title: "Sourdough Loaf", price: 5.99, shelf: "Fresh Bread"},
        {id: "bread-002", title: "Whole Wheat Bread", price: 4.49, shelf: "Fresh Bread"},
        {id: "bread-003", title: "Baguette", price: 3.99, shelf: "Fresh Bread"},
        {id: "bread-004", title: "Ciabatta Rolls", price: 4.99, shelf: "Fresh Bread"}
    ],
    "B1": [
        {id: "meat-001", title: "Ribeye Steak", price: 18.99, shelf: "Fresh Meat"},
        {id: "meat-002", title: "Ground Beef", price: 9.99, shelf: "Fresh Meat"},
        {id: "meat-003", title: "Pork Chops", price: 12.49, shelf: "Fresh Meat"},
        {id: "meat-004", title: "Lamb Shoulder", price: 16.99, shelf: "Fresh Meat"}
    ],
    "B2": [
        {id: "poultry-001", title: "Chicken Breast", price: 8.99, shelf: "Poultry"},
        {id: "poultry-002", title: "Whole Chicken", price: 11.99, shelf: "Poultry"},
        {id: "poultry-003", title: "Turkey Slices", price: 7.49, shelf: "Poultry"},
        {id: "poultry-004", title: "Duck Breast", price: 14.99, shelf: "Poultry"}
    ],
    "B3": [
        {id: "seafood-001", title: "Fresh Salmon", price: 15.99, shelf: "Seafood"},
        {id: "seafood-002", title: "Shrimp", price: 12.99, shelf: "Seafood"},
        {id: "seafood-003", title: "Tuna Steak", price: 13.49, shelf: "Seafood"},
        {id: "seafood-004", title: "Cod Fillet", price: 11.99, shelf: "Seafood"}
    ],
    "C1": [
        {id: "dairy-001", title: "Whole Milk", price: 3.99, shelf: "Milk & Cream"},
        {id: "dairy-002", title: "Heavy Cream", price: 4.49, shelf: "Milk & Cream"},
        {id: "dairy-003", title: "Almond Milk", price: 5.99, shelf: "Milk & Cream"},
        {id: "dairy-004", title: "Greek Yogurt", price: 6.49, shelf: "Milk & Cream"}
    ],
    "C2": [
        {id: "cheese-001", title: "Cheddar Cheese", price: 7.99, shelf: "Cheese"},
        {id: "cheese-002", title: "Mozzarella", price: 6.49, shelf: "Cheese"},
        {id: "cheese-003", title: "Parmesan", price: 9.99, shelf: "Cheese"},
        {id: "cheese-004", title: "Brie", price: 8.49, shelf: "Cheese"}
    ],
    "D1": [
        {id: "canned-001", title: "Tomato Soup", price: 2.49, shelf: "Canned Goods"},
        {id: "canned-002", title: "Black Beans", price: 1.99, shelf: "Canned Goods"},
        {id: "canned-003", title: "Tuna Can", price: 3.49, shelf: "Canned Goods"},
        {id: "canned-004", title: "Corn", price: 1.79, shelf: "Canned Goods"}
    ],
    "D2": [
        {id: "pasta-001", title: "Spaghetti", price: 2.99, shelf: "Pasta & Rice"},
        {id: "pasta-002", title: "Penne", price: 2.79, shelf: "Pasta & Rice"},
        {id: "pasta-003", title: "Basmati Rice", price: 8.99, shelf: "Pasta & Rice"},
        {id: "pasta-004", title: "Jasmine Rice", price: 7.49, shelf: "Pasta & Rice"}
    ],
    "D3": [
        {id: "snack-001", title: "Potato Chips", price: 3.99, shelf: "Snacks & Chips"},
        {id: "snack-002", title: "Pretzels", price: 4.49, shelf: "Snacks & Chips"},
        {id: "snack-003", title: "Trail Mix", price: 6.99, shelf: "Snacks & Chips"},
        {id: "snack-004", title: "Popcorn", price: 3.49, shelf: "Snacks & Chips"}
    ],
    "E1": [
        {id: "water-001", title: "Spring Water 24pk", price: 5.99, shelf: "Water & Juices"},
        {id: "water-002", title: "Orange Juice", price: 4.99, shelf: "Water & Juices"},
        {id: "water-003", title: "Apple Juice", price: 4.49, shelf: "Water & Juices"},
        {id: "water-004", title: "Sparkling Water", price: 6.49, shelf: "Water & Juices"}
    ],
    "E2": [
        {id: "soda-001", title: "Cola 12pk", price: 6.99, shelf: "Soft Drinks"},
        {id: "soda-002", title: "Lemon Soda", price: 5.99, shelf: "Soft Drinks"},
        {id: "soda-003", title: "Ginger Ale", price: 5.49, shelf: "Soft Drinks"},
        {id: "soda-004", title: "Root Beer", price: 6.49, shelf: "Soft Drinks"}
    ],
    "E3": [
        {id: "coffee-001", title: "Ground Coffee", price: 12.99, shelf: "Coffee & Tea"},
        {id: "coffee-002", title: "Green Tea", price: 8.99, shelf: "Coffee & Tea"},
        {id: "coffee-003", title: "Espresso Beans", price: 14.99, shelf: "Coffee & Tea"},
        {id: "coffee-004", title: "Herbal Tea", price: 7.49, shelf: "Coffee & Tea"}
    ],
    "F1": [
        {id: "clean-001", title: "All-Purpose Cleaner", price: 4.99, shelf: "Cleaning Supplies"},
        {id: "clean-002", title: "Dish Soap", price: 3.49, shelf: "Cleaning Supplies"},
        {id: "clean-003", title: "Laundry Detergent", price: 11.99, shelf: "Cleaning Supplies"},
        {id: "clean-004", title: "Glass Cleaner", price: 4.49, shelf: "Cleaning Supplies"}
    ],
    "F2": [
        {id: "paper-001", title: "Paper Towels 6pk", price: 8.99, shelf: "Paper Products"},
        {id: "paper-002", title: "Toilet Paper 12pk", price: 12.99, shelf: "Paper Products"},
        {id: "paper-003", title: "Napkins", price: 3.99, shelf: "Paper Products"},
        {id: "paper-004", title: "Tissues", price: 4.49, shelf: "Paper Products"}
    ]
};

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
            
            // Add click handler to show shelf products
            shelfRect.addEventListener('click', (e) => {
                const shelfId = e.target.getAttribute('data-shelf-id');
                const shelfName = e.target.getAttribute('data-shelf-name');
                showShelfProducts(shelfId, shelfName);
            });
            
            // Make cursor pointer on hover
            shelfRect.style.cursor = 'pointer';
            
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
    hideShelfProducts();
}

// ===== SHELF PRODUCT BROWSING =====

async function showShelfProducts(shelfId, shelfName) {
    currentShelfProducts = shelfId;
    
    // Highlight the selected shelf
    clearHighlights();
    highlightShelf(shelfId);
    
    // Show the shelf products panel
    const panel = document.getElementById('shelfProductsPanel');
    const title = document.getElementById('shelfProductsTitle');
    const container = document.getElementById('shelfProductsList');
    
    title.textContent = `📍 ${shelfName}`;
    panel.style.display = 'block';
    container.innerHTML = '<p class="text-gray-500 text-center py-4">Loading products...</p>';
    
    try {
        // Fetch real products from the API for this shelf
        const response = await fetch(`/api/store/shelf/${shelfId}/products`);
        const data = await response.json();
        
        if (!data.items || data.items.length === 0) {
            container.innerHTML = '<p class="text-gray-500 text-center py-4">No products available for this shelf.</p>';
            console.log('No products for shelf:', shelfId);
            return;
        }
        
        // Render products
        container.innerHTML = '';
        data.items.forEach(product => {
            const card = document.createElement('div');
            card.className = 'bg-white p-3 rounded-lg border-2 border-gray-300 hover:border-indigo-500 transition-all';
            
            card.innerHTML = `
                <div class="flex items-center justify-between mb-2">
                    <h4 class="text-sm font-bold text-gray-900">${product.title}</h4>
                    <span class="text-lg font-bold text-green-700">$${product.price.toFixed(2)}</span>
                </div>
                <button onclick='addShelfProductToCart(${JSON.stringify(product).replace(/'/g, "&#39;")})' 
                        class="w-full bg-indigo-600 hover:bg-indigo-700 text-white font-semibold py-2 px-4 rounded-lg transition-all text-sm">
                    Add to Cart
                </button>
            `;
            
            container.appendChild(card);
        });
        
        console.log(`Showing ${data.items.length} products from ${shelfName}`);
    } catch (error) {
        console.error('Failed to load shelf products:', error);
        container.innerHTML = '<p class="text-red-500 text-center py-4">Failed to load products.</p>';
    }
}

function hideShelfProducts() {
    const panel = document.getElementById('shelfProductsPanel');
    panel.style.display = 'none';
    currentShelfProducts = null;
}

function addShelfProductToCart(product) {
    console.log('Adding shelf product to cart:', product.title);
    
    const existing = cart.find(item => item.id === product.id);
    if (existing) {
        existing.qty++;
    } else {
        cart.push({...product, qty: 1, subcat: product.shelf});
    }
    
    updateCartDisplay();
    updateCartBadge();
    checkBudget();
    showNotification(`Added ${product.title} to cart`);
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
        container.innerHTML = '<p class="text-gray-500">Your cart is empty.</p>';
        subtotalEl.innerHTML = 'Total: $0.00';
        checkBudget();
        return;
    }
    
    const total = cart.reduce((sum, item) => sum + (item.price * item.qty), 0);
    const budget = parseFloat(document.getElementById('budget').value) || 0;
    
    container.innerHTML = '';
    cart.forEach(item => {
        const div = document.createElement('div');
        div.className = 'bg-gray-50 p-3 rounded-lg border border-gray-200';
        div.innerHTML = `
            <div class="flex items-center justify-between">
                <div class="flex-1 min-w-0 pr-2">
                    <p class="text-sm font-semibold text-gray-900 truncate">${item.title}</p>
                    <p class="text-sm text-gray-600">$${item.price.toFixed(2)} × ${item.qty}</p>
                </div>
                <div class="flex items-center space-x-1">
                    <button onclick="updateQuantity('${item.id}', -1)" class="px-2 py-1 bg-gray-200 hover:bg-gray-300 rounded text-sm font-bold">−</button>
                    <button onclick="updateQuantity('${item.id}', 1)" class="px-2 py-1 bg-gray-200 hover:bg-gray-300 rounded text-sm font-bold">+</button>
                    <button onclick="removeFromCart('${item.id}')" class="px-2 py-1 bg-red-500 hover:bg-red-600 text-white rounded text-sm font-bold">×</button>
                </div>
            </div>
        `;
        container.appendChild(div);
    });
    
    const isOverBudget = budget > 0 && total > budget;
    subtotalEl.innerHTML = `Total: <span class="${isOverBudget ? 'text-red-600' : 'text-gray-900'}">$${total.toFixed(2)}</span>`;
    checkBudget();
}

function updateCartBadge() {
    const count = cart.reduce((sum, item) => sum + item.qty, 0);
    document.getElementById('cartBadge').textContent = `Cart: ${count} item${count !== 1 ? 's' : ''}`;
}

// ===== AI RECOMMENDATIONS =====

async function checkBudget() {
    const budget = parseFloat(document.getElementById('budget').value) || 0;
    const total = cart.reduce((sum, item) => sum + (item.price * item.qty), 0);
    
    // Reset to empty state if not over budget or cart is empty
    if (budget <= 0 || total <= budget || cart.length === 0) {
        document.getElementById('budgetList').innerHTML = '<p class="text-gray-500 text-sm">No recommendations yet. Add items or exceed budget to trigger substitutions.</p>';
        document.getElementById('cfList').innerHTML = '<p class="text-gray-500 text-sm">No recommendations yet. Add items or exceed budget to trigger substitutions.</p>';
        document.getElementById('hybridList').innerHTML = '<p class="text-gray-500 text-sm">No recommendations yet. Add items or exceed budget to trigger substitutions.</p>';
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
            renderSuggestions('budgetList', data.suggestions, 'budget');
        } else {
            document.getElementById('budgetList').innerHTML = '<p class="text-gray-500 text-sm">No budget-saving alternatives found for this item.</p>';
        }
    } catch (error) {
        console.error('Failed to get budget recommendations:', error);
        document.getElementById('budgetList').innerHTML = '<p class="text-red-500 text-sm">Error loading recommendations.</p>';
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
            renderSuggestions('cfList', data.suggestions, 'cf');
        } else {
            document.getElementById('cfList').innerHTML = '<p class="text-gray-500 text-sm">No personalized alternatives found for this item.</p>';
        }
    } catch (error) {
        console.error('Failed to get CF recommendations:', error);
        document.getElementById('cfList').innerHTML = '<p class="text-red-500 text-sm">Error loading recommendations.</p>';
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
            renderSuggestions('hybridList', data.suggestions, 'hybrid');
        } else {
            document.getElementById('hybridList').innerHTML = '<p class="text-gray-500 text-sm">No hybrid alternatives found for this item.</p>';
        }
    } catch (error) {
        console.error('Failed to get blended recommendations:', error);
        document.getElementById('hybridList').innerHTML = '<p class="text-red-500 text-sm">Error loading recommendations.</p>';
    }
}

async function renderSuggestions(containerId, suggestions, type) {
    const container = document.getElementById(containerId);
    container.innerHTML = '';
    
    for (const sug of suggestions) {
        const div = document.createElement('div');
        div.className = 'bg-white p-2 rounded-lg border-2 border-gray-300 hover:border-green-500 transition-all';
        
        const replacement = sug.replacement_product;
        
        // Get shelf location for this product
        let shelfInfo = '';
        let shelfId = '';
        try {
            const response = await fetch('/api/store/location', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({subcat: replacement.subcat})
            });
            const location = await response.json();
            shelfId = location.shelf_id;
            shelfInfo = `<div class="flex items-center gap-1 mb-1">
                <svg class="w-3 h-3 text-purple-600" fill="currentColor" viewBox="0 0 20 20">
                    <path fill-rule="evenodd" d="M5.05 4.05a7 7 0 119.9 9.9L10 18.9l-4.95-4.95a7 7 0 010-9.9zM10 11a2 2 0 100-4 2 2 0 000 4z" clip-rule="evenodd"></path>
                </svg>
                <span class="text-xs text-purple-600 font-medium">${shelfId} — ${location.shelf_name}</span>
            </div>`;
        } catch (error) {
            console.error('Failed to get location for recommendation:', error);
        }
        
        div.innerHTML = `
            ${shelfInfo}
            <p class="text-xs font-semibold text-gray-900 mb-1">${replacement.title}</p>
            <p class="text-xs text-gray-600 mb-2">${sug.reason}</p>
            <div class="flex items-center justify-between gap-1">
                <span class="text-xs font-bold text-green-700">Save $${sug.expected_saving}</span>
                <div class="flex gap-1">
                    ${shelfId ? `<button onclick='highlightRecommendationShelf("${shelfId}")' 
                            class="text-xs bg-purple-600 hover:bg-purple-700 text-white px-2 py-1 rounded font-bold">
                        Highlight
                    </button>` : ''}
                    <button onclick='applyRecommendation(${JSON.stringify(sug).replace(/'/g, "&#39;")})' 
                            class="text-xs bg-green-600 hover:bg-green-700 text-white px-2 py-1 rounded font-bold">
                        Replace
                    </button>
                </div>
            </div>
        `;
        
        container.appendChild(div);
    }
}

function highlightRecommendationShelf(shelfId) {
    // Clear any existing highlights
    clearHighlights();
    clearRoute();
    
    // Highlight the recommended shelf
    highlightShelf(shelfId);
    
    // Scroll the store map into view if needed
    const storeMap = document.getElementById('storeMap');
    if (storeMap) {
        storeMap.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
    
    console.log('Highlighted recommendation shelf:', shelfId);
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
        
        // Calculate and draw route from entrance to this location
        const routeResponse = await fetch('/api/store/route', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                from: storeLayout.entrance,
                to: {x: location.x, y: location.y}
            })
        });
        const routeData = await routeResponse.json();
        drawRoute(routeData.waypoints);
        
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
