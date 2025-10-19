#!/usr/bin/env python
"""
Regenerate CF training data with current product IDs from the database.
"""
from main import app, db, User, Order, OrderItem, UserEvent
from recommendation_engine import (
    extract_event_dataset, 
    build_user_product_aggregation, 
    create_id_mappings, 
    save_datasets
)

def regenerate_data():
    """Regenerate training data within Flask app context."""
    with app.app_context():
        print('Extracting fresh event data from database...')
        events_df = extract_event_dataset(db, User, Order, OrderItem, UserEvent)
        
        print('\nBuilding user-product aggregation...')
        behavior_df = build_user_product_aggregation(events_df)
        
        print('\nCreating ID mappings...')
        user_mapping, product_mapping = create_id_mappings(behavior_df)
        
        print('\nSaving datasets...')
        save_datasets(events_df, behavior_df, user_mapping, product_mapping, output_dir='ml_data')
        
        print(f'\n✓ Training data regenerated!')
        print(f'  Events: {len(events_df)}')
        print(f'  Behavior pairs: {len(behavior_df)}')
        print(f'  Users: {len(user_mapping)}')
        print(f'  Products: {len(product_mapping)}')
        
        # Show sample product IDs to verify they match PRODUCTS_DF
        if len(product_mapping) > 0:
            print('\nSample product IDs from regenerated data:')
            for pid in list(product_mapping.keys())[:5]:
                print(f'  {pid} (type: {type(pid).__name__})')

if __name__ == '__main__':
    regenerate_data()
