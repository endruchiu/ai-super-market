"""
Store Layout Manager - Maps products to supermarket aisles and shelves.

This module creates a virtual supermarket layout with aisles, shelves, and product locations.
Uses mock coordinates since the dataset doesn't include physical location data.
"""

# Define store layout: aisles with shelves
# Each aisle has a letter (A-F), each shelf has a number (1-6)
STORE_LAYOUT = {
    "aisles": [
        {
            "id": "A",
            "name": "Fresh Produce & Bakery",
            "x": 50,
            "y": 50,
            "width": 120,
            "height": 600,
            "shelves": [
                {"id": "A1", "name": "Organic Produce", "y_offset": 0},
                {"id": "A2", "name": "Fresh Fruits", "y_offset": 100},
                {"id": "A3", "name": "Fresh Vegetables", "y_offset": 200},
                {"id": "A4", "name": "Bakery & Desserts", "y_offset": 300},
                {"id": "A5", "name": "Fresh Bread", "y_offset": 400},
                {"id": "A6", "name": "Cakes & Pastries", "y_offset": 500},
            ]
        },
        {
            "id": "B",
            "name": "Meat, Seafood & Deli",
            "x": 220,
            "y": 50,
            "width": 120,
            "height": 600,
            "shelves": [
                {"id": "B1", "name": "Fresh Meat", "y_offset": 0},
                {"id": "B2", "name": "Poultry", "y_offset": 100},
                {"id": "B3", "name": "Seafood", "y_offset": 200},
                {"id": "B4", "name": "Deli Counter", "y_offset": 300},
                {"id": "B5", "name": "Prepared Meats", "y_offset": 400},
                {"id": "B6", "name": "Specialty Meats", "y_offset": 500},
            ]
        },
        {
            "id": "C",
            "name": "Dairy & Frozen",
            "x": 390,
            "y": 50,
            "width": 120,
            "height": 600,
            "shelves": [
                {"id": "C1", "name": "Milk & Cream", "y_offset": 0},
                {"id": "C2", "name": "Cheese", "y_offset": 100},
                {"id": "C3", "name": "Yogurt & Eggs", "y_offset": 200},
                {"id": "C4", "name": "Frozen Meals", "y_offset": 300},
                {"id": "C5", "name": "Ice Cream", "y_offset": 400},
                {"id": "C6", "name": "Frozen Vegetables", "y_offset": 500},
            ]
        },
        {
            "id": "D",
            "name": "Pantry & Snacks",
            "x": 560,
            "y": 50,
            "width": 120,
            "height": 600,
            "shelves": [
                {"id": "D1", "name": "Canned Goods", "y_offset": 0},
                {"id": "D2", "name": "Pasta & Rice", "y_offset": 100},
                {"id": "D3", "name": "Snacks & Chips", "y_offset": 200},
                {"id": "D4", "name": "Cookies & Crackers", "y_offset": 300},
                {"id": "D5", "name": "Cereals", "y_offset": 400},
                {"id": "D6", "name": "Baking Supplies", "y_offset": 500},
            ]
        },
        {
            "id": "E",
            "name": "Beverages & Drinks",
            "x": 730,
            "y": 50,
            "width": 120,
            "height": 600,
            "shelves": [
                {"id": "E1", "name": "Water & Juices", "y_offset": 0},
                {"id": "E2", "name": "Soft Drinks", "y_offset": 100},
                {"id": "E3", "name": "Coffee & Tea", "y_offset": 200},
                {"id": "E4", "name": "Sports Drinks", "y_offset": 300},
                {"id": "E5", "name": "Wine & Beer", "y_offset": 400},
                {"id": "E6", "name": "Specialty Drinks", "y_offset": 500},
            ]
        },
        {
            "id": "F",
            "name": "Household & Paper",
            "x": 900,
            "y": 50,
            "width": 120,
            "height": 600,
            "shelves": [
                {"id": "F1", "name": "Cleaning Supplies", "y_offset": 0},
                {"id": "F2", "name": "Paper Products", "y_offset": 100},
                {"id": "F3", "name": "Plastic Bags", "y_offset": 200},
                {"id": "F4", "name": "Storage Containers", "y_offset": 300},
                {"id": "F5", "name": "Kitchen Supplies", "y_offset": 400},
                {"id": "F6", "name": "Batteries & More", "y_offset": 500},
            ]
        },
    ],
    "entrance": {"x": 50, "y": 680},
    "checkout": {"x": 900, "y": 680}
}

# Map product categories to shelf locations
CATEGORY_TO_SHELF = {
    # Fresh & Bakery (Aisle A)
    "Bakery & Desserts": "A4",
    "Bakery": "A4",
    "Desserts": "A6",
    "Bread": "A5",
    "Fresh Produce": "A2",
    "Fruits": "A2",
    "Vegetables": "A3",
    "Organic": "A1",
    
    # Meat & Seafood (Aisle B)
    "Meat": "B1",
    "Meat & Seafood": "B1",
    "Seafood": "B3",
    "Poultry": "B2",
    "Deli": "B4",
    
    # Dairy & Frozen (Aisle C)
    "Dairy": "C1",
    "Milk": "C1",
    "Cheese": "C2",
    "Yogurt": "C3",
    "Eggs": "C3",
    "Frozen": "C4",
    "Ice Cream": "C5",
    "Frozen Food": "C4",
    
    # Pantry & Snacks (Aisle D)
    "Snacks": "D3",
    "Candy": "D3",
    "Candy & Chocolate": "D3",
    "Cookies": "D4",
    "Crackers": "D4",
    "Cereals": "D5",
    "Breakfast": "D5",
    "Pasta": "D2",
    "Rice": "D2",
    "Canned Goods": "D1",
    "Pantry & Dry Goods": "D1",
    "Kirkland Signature Grocery": "D2",
    "Baking": "D6",
    
    # Beverages (Aisle E)
    "Beverages": "E1",
    "Beverages & Water": "E1",
    "Water": "E1",
    "Juice": "E1",
    "Soft Drinks": "E2",
    "Soda": "E2",
    "Coffee": "E3",
    "Tea": "E3",
    "Wine": "E5",
    "Beer": "E5",
    
    # Household (Aisle F)
    "Household": "F1",
    "Cleaning": "F1",
    "Cleaning Supplies": "F1",
    "Laundry Detergent & Supplies": "F1",
    "Paper & Plastic Products": "F2",
    "Paper Products": "F2",
    "Plastic": "F3",
    "Storage": "F4",
    "Kitchen": "F5",
    "Floral": "A1",
    "Gift Baskets": "A6",
}

# Reverse mapping: shelf to categories (for looking up products)
SHELF_TO_CATEGORIES = {
    "A1": ["Organic", "Floral"],
    "A2": ["Fresh Produce", "Fruits"],
    "A3": ["Vegetables"],
    "A4": ["Bakery & Desserts", "Bakery"],
    "A5": ["Bread"],
    "A6": ["Desserts", "Gift Baskets"],
    "B1": ["Meat & Seafood", "Meat"],
    "B2": ["Poultry"],
    "B3": ["Seafood"],
    "B4": ["Deli"],
    "B5": ["Deli", "Meat & Seafood"],
    "B6": ["Deli", "Meat & Seafood"],
    "C1": ["Dairy", "Milk"],
    "C2": ["Cheese"],
    "C3": ["Yogurt", "Eggs"],
    "C4": ["Frozen", "Frozen Food"],
    "C5": ["Ice Cream"],
    "C6": ["Frozen", "Frozen Food"],
    "D1": ["Canned Goods", "Pantry & Dry Goods"],
    "D2": ["Pasta", "Rice", "Kirkland Signature Grocery", "Pantry & Dry Goods"],
    "D3": ["Snacks", "Candy"],
    "D4": ["Cookies", "Crackers", "Snacks"],
    "D5": ["Cereals", "Breakfast"],
    "D6": ["Baking", "Pantry & Dry Goods"],
    "E1": ["Beverages & Water", "Beverages", "Water", "Juice"],
    "E2": ["Soft Drinks", "Soda", "Beverages & Water"],
    "E3": ["Coffee", "Tea"],
    "E4": ["Beverages & Water", "Soft Drinks"],
    "E5": ["Wine", "Beer", "Beverages & Water"],
    "E6": ["Beverages & Water", "Coffee"],
    "F1": ["Household", "Cleaning Supplies", "Laundry Detergent & Supplies"],
    "F2": ["Paper & Plastic Products"],
    "F3": ["Paper & Plastic Products", "Plastic"],
    "F4": ["Household", "Storage"],
    "F5": ["Household", "Kitchen"],
    "F6": ["Household"],
}

def get_shelf_for_category(category: str) -> str:
    """
    Get the shelf location for a product category.
    Returns shelf ID (e.g., "A4") or "D3" as default (snacks aisle).
    """
    if not category:
        return "D3"  # Default to snacks
    
    # Try exact match first
    if category in CATEGORY_TO_SHELF:
        return CATEGORY_TO_SHELF[category]
    
    # Try partial match (e.g., "Bakery & Desserts" contains "Bakery")
    for cat_key, shelf_id in CATEGORY_TO_SHELF.items():
        if cat_key.lower() in category.lower() or category.lower() in cat_key.lower():
            return shelf_id
    
    # Default to snacks aisle
    return "D3"

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
