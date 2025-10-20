"""
Store Layout Manager - Uses ONLY actual category names from the recategorized CSV.
No made-up labels - just the real 17 categories from the data.
"""

# Store layout with 6 aisles (A-F), 6 shelves each = 36 shelves
# Using ONLY the 17 actual categories from GroceryDataset_Recategorized.csv
STORE_LAYOUT = {
    "aisles": [
        {
            "id": "A",
            "name": "Aisle A",
            "x": 50,
            "y": 50,
            "width": 120,
            "height": 600,
            "shelves": [
                {"id": "A1", "name": "Meat & Seafood", "y_offset": 0},
                {"id": "A2", "name": "Meat & Seafood", "y_offset": 100},
                {"id": "A3", "name": "Deli", "y_offset": 200},
                {"id": "A4", "name": "Breakfast", "y_offset": 300},
                {"id": "A5", "name": "Bakery & Desserts", "y_offset": 400},
                {"id": "A6", "name": "Floral", "y_offset": 500},
            ]
        },
        {
            "id": "B",
            "name": "Aisle B",
            "x": 220,
            "y": 50,
            "width": 120,
            "height": 600,
            "shelves": [
                {"id": "B1", "name": "Snacks", "y_offset": 0},
                {"id": "B2", "name": "Snacks", "y_offset": 100},
                {"id": "B3", "name": "Snacks", "y_offset": 200},
                {"id": "B4", "name": "Snacks", "y_offset": 300},
                {"id": "B5", "name": "Snacks", "y_offset": 400},
                {"id": "B6", "name": "Snacks", "y_offset": 500},
            ]
        },
        {
            "id": "C",
            "name": "Aisle C",
            "x": 390,
            "y": 50,
            "width": 120,
            "height": 600,
            "shelves": [
                {"id": "C1", "name": "Candy", "y_offset": 0},
                {"id": "C2", "name": "Candy", "y_offset": 100},
                {"id": "C3", "name": "Candy", "y_offset": 200},
                {"id": "C4", "name": "Gift Baskets", "y_offset": 300},
                {"id": "C5", "name": "Organic", "y_offset": 400},
                {"id": "C6", "name": "Kirkland Signature Grocery", "y_offset": 500},
            ]
        },
        {
            "id": "D",
            "name": "Aisle D",
            "x": 560,
            "y": 50,
            "width": 120,
            "height": 600,
            "shelves": [
                {"id": "D1", "name": "Pantry & Dry Goods", "y_offset": 0},
                {"id": "D2", "name": "Pantry & Dry Goods", "y_offset": 100},
                {"id": "D3", "name": "Pantry & Dry Goods", "y_offset": 200},
                {"id": "D4", "name": "Pantry & Dry Goods", "y_offset": 300},
                {"id": "D5", "name": "Coffee", "y_offset": 400},
                {"id": "D6", "name": "Coffee", "y_offset": 500},
            ]
        },
        {
            "id": "E",
            "name": "Aisle E",
            "x": 730,
            "y": 50,
            "width": 120,
            "height": 600,
            "shelves": [
                {"id": "E1", "name": "Beverages & Water", "y_offset": 0},
                {"id": "E2", "name": "Beverages & Water", "y_offset": 100},
                {"id": "E3", "name": "Beverages & Water", "y_offset": 200},
                {"id": "E4", "name": "Beverages & Water", "y_offset": 300},
                {"id": "E5", "name": "Beverages & Water", "y_offset": 400},
                {"id": "E6", "name": "Beverages & Water", "y_offset": 500},
            ]
        },
        {
            "id": "F",
            "name": "Aisle F",
            "x": 900,
            "y": 50,
            "width": 120,
            "height": 600,
            "shelves": [
                {"id": "F1", "name": "Cleaning Supplies", "y_offset": 0},
                {"id": "F2", "name": "Paper & Plastic Products", "y_offset": 100},
                {"id": "F3", "name": "Laundry Detergent & Supplies", "y_offset": 200},
                {"id": "F4", "name": "Household", "y_offset": 300},
                {"id": "F5", "name": "Household", "y_offset": 400},
                {"id": "F6", "name": "Gift Baskets", "y_offset": 500},
            ]
        },
    ],
    "entrance": {"x": 50, "y": 680},
    "checkout": {"x": 900, "y": 680}
}

# Map categories to their primary shelf location
# Using ONLY the 17 actual category names from the CSV
CATEGORY_TO_SHELF = {
    "Meat & Seafood": "A1",
    "Deli": "A3",
    "Breakfast": "A4",
    "Bakery & Desserts": "A5",
    "Floral": "A6",
    "Snacks": "B1",
    "Candy": "C1",
    "Gift Baskets": "C4",
    "Organic": "C5",
    "Kirkland Signature Grocery": "C6",
    "Pantry & Dry Goods": "D1",
    "Coffee": "D5",
    "Beverages & Water": "E1",
    "Cleaning Supplies": "F1",
    "Paper & Plastic Products": "F2",
    "Laundry Detergent & Supplies": "F3",
    "Household": "F4",
}

# Reverse mapping: shelf to categories
# Each shelf shows products from its assigned category ONLY
SHELF_TO_CATEGORIES = {
    "A1": ["Meat & Seafood"],
    "A2": ["Meat & Seafood"],
    "A3": ["Deli"],
    "A4": ["Breakfast"],
    "A5": ["Bakery & Desserts"],
    "A6": ["Floral"],
    "B1": ["Snacks"],
    "B2": ["Snacks"],
    "B3": ["Snacks"],
    "B4": ["Snacks"],
    "B5": ["Snacks"],
    "B6": ["Snacks"],
    "C1": ["Candy"],
    "C2": ["Candy"],
    "C3": ["Candy"],
    "C4": ["Gift Baskets"],
    "C5": ["Organic"],
    "C6": ["Kirkland Signature Grocery"],
    "D1": ["Pantry & Dry Goods"],
    "D2": ["Pantry & Dry Goods"],
    "D3": ["Pantry & Dry Goods"],
    "D4": ["Pantry & Dry Goods"],
    "D5": ["Coffee"],
    "D6": ["Coffee"],
    "E1": ["Beverages & Water"],
    "E2": ["Beverages & Water"],
    "E3": ["Beverages & Water"],
    "E4": ["Beverages & Water"],
    "E5": ["Beverages & Water"],
    "E6": ["Beverages & Water"],
    "F1": ["Cleaning Supplies"],
    "F2": ["Paper & Plastic Products"],
    "F3": ["Laundry Detergent & Supplies"],
    "F4": ["Household"],
    "F5": ["Household"],
    "F6": ["Gift Baskets"],
}

def get_shelf_for_category(category: str) -> str:
    """Get the primary shelf location for a category."""
    if not category:
        return "B1"  # Default to Snacks
    
    # Exact match
    if category in CATEGORY_TO_SHELF:
        return CATEGORY_TO_SHELF[category]
    
    # Default to Snacks if not found
    return "B1"

def get_shelf_coordinates(shelf_id: str) -> dict:
    """Get the x, y coordinates for a shelf."""
    for aisle in STORE_LAYOUT["aisles"]:
        for shelf in aisle["shelves"]:
            if shelf["id"] == shelf_id:
                return {
                    "shelf_id": shelf_id,
                    "x": aisle["x"] + aisle["width"] // 2,
                    "y": aisle["y"] + shelf["y_offset"] + 50,
                    "aisle_id": aisle["id"],
                    "aisle_name": aisle["name"],
                    "shelf_name": shelf["name"]
                }
    
    # Default to entrance
    return {
        "shelf_id": "ENTRANCE",
        "x": STORE_LAYOUT["entrance"]["x"],
        "y": STORE_LAYOUT["entrance"]["y"],
        "aisle_id": "ENTRANCE",
        "aisle_name": "Store Entrance",
        "shelf_name": "Entrance"
    }

def get_product_location(subcat: str) -> dict:
    """Get location for a product based on its subcategory."""
    shelf_id = get_shelf_for_category(subcat)
    return get_shelf_coordinates(shelf_id)

def calculate_simple_route(from_coords: dict, to_coords: dict) -> list:
    """Calculate Manhattan-style route between two locations."""
    start_x, start_y = from_coords["x"], from_coords["y"]
    end_x, end_y = to_coords["x"], to_coords["y"]
    
    waypoints = [
        {"x": start_x, "y": start_y},
        {"x": end_x, "y": start_y},
        {"x": end_x, "y": end_y}
    ]
    
    return waypoints
