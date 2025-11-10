import sys
sys.path.insert(0, '.')

from main import app, db, PRODUCTS_DF
from replenishment_engine import ReplenishmentEngine

print("🔄 Calculating replenishment cycles...")

with app.app_context():
    try:
        replenishment_engine = ReplenishmentEngine(db, PRODUCTS_DF)
        
        replenish_count = replenishment_engine.identify_replenishable_products()
        print(f"✓ Identified {replenish_count} replenishable products")
        
        users = db.session.execute(db.select(db.Model.metadata.tables['users'].c.id)).fetchall()
        total_cycles = 0
        
        for user_row in users:
            user_id = user_row[0]
            cycles = replenishment_engine.calculate_user_cycles(user_id)
            if cycles > 0:
                print(f"  ✓ User {user_id}: {cycles} cycles")
                total_cycles += cycles
        
        db.session.commit()
        print(f"\n✅ Total: {total_cycles} replenishment cycles calculated")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
