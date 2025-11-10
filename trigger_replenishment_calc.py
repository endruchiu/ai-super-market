import os
import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from replenishment_engine import ReplenishmentEngine

DATABASE_URL = os.environ.get('DATABASE_URL')
engine = create_engine(DATABASE_URL)

print("📥 Loading products catalog...")
PRODUCTS_CSV = 'attached_assets/GroceryDataset_with_Nutrition_1758836546999.csv'
products_df = pd.read_csv(PRODUCTS_CSV)
print(f"✓ Loaded {len(products_df)} products")

print("🔄 Triggering replenishment cycle calculation...")

with Session(engine) as session:
    replenishment_engine = ReplenishmentEngine(session, products_df)
    
    replenish_count = replenishment_engine.identify_replenishable_products()
    print(f"✓ Identified {replenish_count} replenishable products")
    
    user_result = session.execute("SELECT id FROM users").fetchall()
    cycles_updated = 0
    
    for user in user_result:
        user_id = user[0]
        cycles = replenishment_engine.calculate_user_cycles(user_id)
        cycles_updated += cycles
    
    session.commit()
    print(f"✓ Updated {cycles_updated} replenishment cycles")

print("✅ Replenishment calculation complete!")
