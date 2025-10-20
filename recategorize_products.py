"""
Recategorize products into clean, logical subcategories.
Fixes duplicate products and inconsistent categorization.
"""
import pandas as pd
import numpy as np
import hashlib

def generate_product_id(title, subcat):
    """Generate deterministic product ID"""
    key = f"{title}|{subcat}"
    hash_bytes = hashlib.blake2b(key.encode('utf-8'), digest_size=8).digest()
    return int.from_bytes(hash_bytes, 'big', signed=False) & ((1 << 63) - 1)

# Category mapping rules - map problematic categories to proper ones
CATEGORY_FIXES = {
    # Remove brand-specific categories
    "Kirkland Signature Grocery": None,  # Will be reassigned based on product type
    
    # Keep only one organic category or merge with main category
    "Organic": None,  # Will be reassigned based on product type
    
    # Standardize seafood
    "Seafood": "Meat & Seafood",
    
    # Poultry goes to meat
    "Poultry": "Meat & Seafood",
}

# Product-to-category priority rules (for deduplication)
def assign_best_category(title, categories):
    """
    Given a product title and list of categories it appears in,
    return the single best category for this product.
    """
    title_lower = title.lower()
    
    # Remove categories that should be ignored
    valid_cats = [c for c in categories if c not in ["Kirkland Signature Grocery", "Organic"]]
    
    # If only one valid category remains, use it
    if len(valid_cats) == 1:
        return valid_cats[0]
    
    # Priority rules based on product type keywords
    if any(word in title_lower for word in ['cookie', 'brownie', 'cake', 'madeleine']):
        if "Bakery & Desserts" in valid_cats:
            return "Bakery & Desserts"
        if "Snacks" in valid_cats:
            return "Snacks"
    
    if any(word in title_lower for word in ['almond milk', 'beverage', 'coffee', 'tea', 'drink', 'water', 'juice']):
        if "Beverages & Water" in valid_cats:
            return "Beverages & Water"
        if "Coffee" in valid_cats:
            return "Coffee"
    
    if any(word in title_lower for word in ['meat', 'beef', 'pork', 'chicken', 'salmon', 'tuna', 'seafood', 'fish']):
        return "Meat & Seafood"
    
    if any(word in title_lower for word in ['candy', 'chocolate', 'gum']):
        if "Candy" in valid_cats:
            return "Candy"
    
    if any(word in title_lower for word in ['chip', 'popcorn', 'pretzels', 'crackers', 'nuts', 'bar']):
        if "Snacks" in valid_cats:
            return "Snacks"
    
    if any(word in title_lower for word in ['cereal', 'oatmeal', 'granola', 'breakfast']):
        if "Breakfast" in valid_cats:
            return "Breakfast"
    
    if any(word in title_lower for word in ['pasta', 'rice', 'beans', 'sauce', 'oil', 'flour']):
        if "Pantry & Dry Goods" in valid_cats:
            return "Pantry & Dry Goods"
    
    if any(word in title_lower for word in ['paper', 'napkin', 'plate', 'cup', 'towel', 'tissue']):
        if "Paper & Plastic Products" in valid_cats:
            return "Paper & Plastic Products"
    
    if any(word in title_lower for word in ['detergent', 'laundry', 'fabric']):
        if "Laundry Detergent & Supplies" in valid_cats:
            return "Laundry Detergent & Supplies"
    
    if any(word in title_lower for word in ['clean', 'soap', 'disinfect', 'wipe']):
        if "Cleaning Supplies" in valid_cats:
            return "Cleaning Supplies"
    
    if any(word in title_lower for word in ['flower', 'bouquet', 'rose', 'plant']):
        if "Floral" in valid_cats:
            return "Floral"
    
    if any(word in title_lower for word in ['gift', 'basket', 'assortment']):
        if "Gift Baskets" in valid_cats:
            return "Gift Baskets"
    
    if any(word in title_lower for word in ['deli', 'cheese', 'salami']):
        if "Deli" in valid_cats:
            return "Deli"
    
    # Default: return the first valid category
    return valid_cats[0] if valid_cats else categories[0]

def recategorize_csv(input_path, output_path):
    """Main recategorization function"""
    print(f"Loading CSV from {input_path}...")
    df = pd.read_csv(input_path)
    
    print(f"Original dataset: {len(df)} rows, {df['Title'].nunique()} unique products")
    print(f"Duplicates: {len(df) - df['Title'].nunique()}")
    
    # Step 1: For each unique product, determine the best category
    product_to_category = {}
    for title in df['Title'].unique():
        product_rows = df[df['Title'] == title]
        categories = product_rows['Sub Category'].unique().tolist()
        best_category = assign_best_category(title, categories)
        product_to_category[title] = best_category
    
    # Step 2: Create new dataframe with deduplicated products
    deduplicated_rows = []
    for title, best_cat in product_to_category.items():
        # Get all rows for this product
        product_rows = df[df['Title'] == title]
        
        # Prefer the row with the best category
        matching_rows = product_rows[product_rows['Sub Category'] == best_cat]
        if len(matching_rows) > 0:
            row = matching_rows.iloc[0].copy()
        else:
            # Fallback: take first row and update category
            row = product_rows.iloc[0].copy()
            row['Sub Category'] = best_cat
        
        deduplicated_rows.append(row)
    
    # Create new dataframe
    df_clean = pd.DataFrame(deduplicated_rows).reset_index(drop=True)
    
    print(f"\nCleaned dataset: {len(df_clean)} rows, {df_clean['Title'].nunique()} unique products")
    print(f"Removed duplicates: {len(df) - len(df_clean)}")
    
    # Show new category distribution
    print("\n=== NEW CATEGORY DISTRIBUTION ===")
    print(df_clean['Sub Category'].value_counts())
    
    # Save to new CSV
    df_clean.to_csv(output_path, index=False)
    print(f"\n✓ Saved recategorized data to {output_path}")
    
    return df_clean

if __name__ == "__main__":
    input_csv = "attached_assets/GroceryDataset_with_Nutrition_1758836546999.csv"
    output_csv = "attached_assets/GroceryDataset_Recategorized.csv"
    
    df_clean = recategorize_csv(input_csv, output_csv)
    
    # Verify no duplicates remain
    assert df_clean['Title'].is_unique, "ERROR: Duplicates still exist!"
    print("\n✓ Verification passed: All products are unique")
