import pandas as pd
from main import app, db
from models import init_models


def import_grocery_data():
    """Import grocery data from CSV file into the database"""
    
    with app.app_context():
        # Initialize models
        Product, ShoppingCart, UserBudget = init_models(db)
        
        # Clear existing data
        Product.query.delete()
        db.session.commit()
        
        # Read CSV file
        df = pd.read_csv('attached_assets/GroceryDataset_with_Nutrition_1758836546999.csv')
        
        imported_count = 0
        
        for _, row in df.iterrows():
            # Parse price and rating
            price_numeric = Product.parse_price(row.get('Price'))
            rating_numeric, review_count = Product.parse_rating(row.get('Rating'))
            
            # Parse nutritional information
            def safe_int(value):
                if pd.isna(value) or value == '' or value is None:
                    return None
                try:
                    return int(float(value))
                except (ValueError, TypeError):
                    return None
            
            def safe_float(value):
                if pd.isna(value) or value == '' or value is None:
                    return None
                try:
                    return float(value)
                except (ValueError, TypeError):
                    return None
            
            # Create product instance
            product = Product(
                sub_category=row.get('Sub Category', ''),
                price_text=row.get('Price', ''),
                price_numeric=price_numeric,
                discount=row.get('Discount', ''),
                rating_text=row.get('Rating', ''),
                rating_numeric=rating_numeric,
                review_count=review_count,
                title=row.get('Title', ''),
                currency=row.get('Currency', ''),
                feature=row.get('Feature', ''),
                description=row.get('Product Description', ''),
                # Nutritional information
                calories=safe_int(row.get('Calories')),
                fat_g=safe_float(row.get('Fat_g')),
                carbs_g=safe_float(row.get('Carbs_g')),
                sugar_g=safe_float(row.get('Sugar_g')),
                protein_g=safe_float(row.get('Protein_g')),
                sodium_mg=safe_int(row.get('Sodium_mg'))
            )
            
            db.session.add(product)
            imported_count += 1
            
            # Commit in batches for better performance
            if imported_count % 100 == 0:
                db.session.commit()
        
        # Final commit
        db.session.commit()
        
        return imported_count


if __name__ == "__main__":
    count = import_grocery_data()
    print(f"Imported {count} products successfully!")