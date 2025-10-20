"""
Store Layout Manager - Maps products to supermarket aisles and shelves.

This module creates a virtual supermarket layout with aisles, shelves, and product locations.
Based on the recategorized product database with no duplicates.
"""

# Define store layout: aisles with shelves
# Each aisle has a letter (A-F), each shelf has a number (1-6)
STORE_LAYOUT = {
    "aisles": [
        {
            "id": "A",
            "name": "Fresh & Prepared Foods",
            "x": 50,
            "y": 50,
            "width": 120,
            "height": 600,
            "shelves": [
                {"id": "A1", "name": "Meat & Seafood", "y_offset": 0},
                {"id": "A2", "name": "Premium Meats", "y_offset": 100},
                {"id": "A3", "name": "Fresh Seafood", "y_offset": 200},
                {"id": "A4", "name": "Deli", "y_offset": 300},
                {"id": "A5", "name": "Floral", "y_offset": 400},
                {"id": "A6", "name": "Gift Baskets", "y_offset": 500},
            ]
        },
        {
            "id": "B",
            "name": "Breakfast & Snacks",
            "x": 220,
            "y": 50,
            "width": 120,
            "height": 600,
            "shelves": [
                {"id": "B1", "name": "Breakfast", "y_offset": 0},
                {"id": "B2", "name": "Bakery & Desserts", "y_offset": 100},
                {"id": "B3", "name": "Snacks", "y_offset": 200},
                {"id": "B4", "name": "Chips & Pretzels", "y_offset": 300},
                {"id": "B5", "name": "Crackers & Nuts", "y_offset": 400},
                {"id": "B6", "name": "Protein Bars", "y_offset": 500},
            ]
        },
        {
            "id": "C",
            "name": "Candy & Treats",
            "x": 390,
            "y": 50,
            "width": 120,
            "height": 600,
            "shelves": [
                {"id": "C1", "name": "More Snacks", "y_offset": 0},
                {"id": "C2", "name": "Candy", "y_offset": 100},
                {"id": "C3", "name": "Chocolate", "y_offset": 200},
                {"id": "C4", "name": "Gummies & Sweets", "y_offset": 300},
                {"id": "C5", "name": "Organic & Specialty", "y_offset": 400},
                {"id": "C6", "name": "Gift Baskets", "y_offset": 500},
            ]
        },
        {
            "id": "D",
            "name": "Pantry & Coffee",
            "x": 560,
            "y": 50,
            "width": 120,
            "height": 600,
            "shelves": [
                {"id": "D1", "name": "Pantry & Dry Goods", "y_offset": 0},
                {"id": "D2", "name": "Pasta & Rice", "y_offset": 100},
                {"id": "D3", "name": "Canned & Jarred", "y_offset": 200},
                {"id": "D4", "name": "Kirkland Signature", "y_offset": 300},
                {"id": "D5", "name": "Coffee", "y_offset": 400},
                {"id": "D6", "name": "Tea & Coffee", "y_offset": 500},
            ]
        },
        {
            "id": "E",
            "name": "Beverages",
            "x": 730,
            "y": 50,
            "width": 120,
            "height": 600,
            "shelves": [
                {"id": "E1", "name": "Beverages & Water", "y_offset": 0},
                {"id": "E2", "name": "Soft Drinks", "y_offset": 100},
                {"id": "E3", "name": "Juices", "y_offset": 200},
                {"id": "E4", "name": "Coffee Drinks", "y_offset": 300},
                {"id": "E5", "name": "Sports Drinks", "y_offset": 400},
                {"id": "E6", "name": "Specialty Beverages", "y_offset": 500},
            ]
        },
        {
            "id": "F",
            "name": "Household & Cleaning",
            "x": 900,
            "y": 50,
            "width": 120,
            "height": 600,
            "shelves": [
                {"id": "F1", "name": "Cleaning Supplies", "y_offset": 0},
                {"id": "F2", "name": "Paper & Plastic", "y_offset": 100},
                {"id": "F3", "name": "Laundry Supplies", "y_offset": 200},
                {"id": "F4", "name": "Household", "y_offset": 300},
                {"id": "F5", "name": "Storage & Organization", "y_offset": 400},
                {"id": "F6", "name": "Home Essentials", "y_offset": 500},
            ]
        },
    ],
    "entrance": {"x": 50, "y": 680},
    "checkout": {"x": 900, "y": 680}
}

# Map product categories to shelf locations (based on actual CSV subcategories)
CATEGORY_TO_SHELF = {
    # Aisle A - Fresh & Prepared Foods
    "Meat & Seafood": "A1",
    "Deli": "A4",
    "Floral": "A5",
    "Gift Baskets": "A6",
    
    # Aisle B - Breakfast & Snacks
    "Breakfast": "B1",
    "Bakery & Desserts": "B2",
    "Snacks": "B3",
    
    # Aisle C - Candy & Treats
    "Candy": "C2",
    "Organic": "C5",
    
    # Aisle D - Pantry & Coffee
    "Pantry & Dry Goods": "D1",
    "Kirkland Signature Grocery": "D4",
    "Coffee": "D5",
    
    # Aisle E - Beverages
    "Beverages & Water": "E1",
    
    # Aisle F - Household & Cleaning
    "Cleaning Supplies": "F1",
    "Paper & Plastic Products": "F2",
    "Laundry Detergent & Supplies": "F3",
    "Household": "F4",
}

# Reverse mapping: shelf to categories (for browsing products by shelf)
# Using EXACT subcategory names from the recategorized database
SHELF_TO_CATEGORIES = {
    "A1": ["Meat & Seafood"],
    "A2": ["Meat & Seafood"],
    "A3": ["Meat & Seafood"],
    "A4": ["Deli"],
    "A5": ["Floral"],
    "A6": ["Gift Baskets"],
    "B1": ["Breakfast"],
    "B2": ["Bakery & Desserts"],
    "B3": ["Snacks"],
    "B4": ["Snacks"],
    "B5": ["Snacks"],
    "B6": ["Snacks"],
    "C1": ["Snacks"],
    "C2": ["Candy"],
    "C3": ["Candy"],
    "C4": ["Candy"],
    "C5": ["Organic"],
    "C6": ["Gift Baskets"],
    "D1": ["Pantry & Dry Goods"],
    "D2": ["Pantry & Dry Goods"],
    "D3": ["Pantry & Dry Goods"],
    "D4": ["Kirkland Signature Grocery"],
    "D5": ["Coffee"],
    "D6": ["Coffee"],
    "E1": ["Beverages & Water"],
    "E2": ["Beverages & Water"],
    "E3": ["Beverages & Water"],
    "E4": ["Coffee", "Beverages & Water"],
    "E5": ["Beverages & Water"],
    "E6": ["Beverages & Water"],
    "F1": ["Cleaning Supplies"],
    "F2": ["Paper & Plastic Products"],
    "F3": ["Laundry Detergent & Supplies"],
    "F4": ["Household"],
    "F5": ["Household"],
    "F6": ["Household"],
}

def get_shelf_for_category(category: str) -> str:
    """
    Get the shelf location for a product category.
    Returns shelf ID (e.g., "A4") or "B3" as default (snacks aisle).
    """
    if not category:
        return "B3"  # Default to snacks
    
    # Try exact match first
    if category in CATEGORY_TO_SHELF:
        return CATEGORY_TO_SHELF[category]
    
    # Try partial match (e.g., "Bakery & Desserts" contains "Bakery")
    for cat_key, shelf_id in CATEGORY_TO_SHELF.items():
        if cat_key.lower() in category.lower() or category.lower() in cat_key.lower():
            return shelf_id
    
    # Default to snacks aisle
    return "B3"

def get_shelf_coordinates(shelf_id: str) -> dict:
    """
    Get the x, y coordinates for a shelf.
    Returns dict with x, y, aisle_name, shelf_name.
    """
    for aisle in STORE_LAYOUT["aisles"]:
        for shelf in aisle["shelves"]:
            if shelf["id"] == shelf_id:
                return {
                    "shelf_id": shelf_id,
                    "x": aisle["x"] + aisle["width"] // 2,  # Center of aisle
                    "y": aisle["y"] + shelf["y_offset"] + 50,  # Center of shelf
                    "aisle_id": aisle["id"],
                    "aisle_name": aisle["name"],
                    "shelf_name": shelf["name"]
                }
    
    # Default to entrance if not found
    return {
        "shelf_id": "ENTRANCE",
        "x": STORE_LAYOUT["entrance"]["x"],
        "y": STORE_LAYOUT["entrance"]["y"],
        "aisle_id": "ENTRANCE",
        "aisle_name": "Store Entrance",
        "shelf_name": "Entrance"
    }

def get_product_location(subcat: str) -> dict:
    """
    Get the complete location info for a product based on its subcategory.
    """
    shelf_id = get_shelf_for_category(subcat)
    return get_shelf_coordinates(shelf_id)

def calculate_simple_route(from_coords: dict, to_coords: dict) -> list:
    """
    Calculate a simple Manhattan-style route from one location to another.
    Returns list of waypoints [(x1, y1), (x2, y2), ...].
    """
    start_x, start_y = from_coords["x"], from_coords["y"]
    end_x, end_y = to_coords["x"], to_coords["y"]
    
    # Simple L-shaped route (horizontal then vertical, or vice versa)
    waypoints = [
        {"x": start_x, "y": start_y},
        {"x": end_x, "y": start_y},  # Move horizontally first
        {"x": end_x, "y": end_y}     # Then move vertically
    ]
    
    return waypoints
