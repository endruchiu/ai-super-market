"""
Recommendation Engine for Grocery Shopping App
Implements collaborative filtering with deep learning (Keras embeddings)
and user behavior analysis for personalized recommendations.
"""

import pandas as pd
import numpy as np
import pickle
import os
from datetime import datetime
from typing import Dict, Tuple, List
import json


def normalize_event_type(event_type: str) -> str:
    """
    Normalize event type strings to standard format.
    
    Maps:
    - 'cart', 'add_to_cart', 'cart_add' -> 'cart_add'
    - 'remove', 'remove_from_cart', 'cart_remove' -> 'cart_remove'
    - 'view', 'product_view' -> 'view'
    - 'purchase', 'buy', 'order' -> 'purchase'
    
    Args:
        event_type: Original event type string
        
    Returns:
        Normalized event type
    """
    event_type = event_type.lower().strip()
    
    # Cart add events
    if event_type in ['cart', 'add_to_cart', 'add', 'cart_add']:
        return 'cart_add'
    
    # Cart remove events
    if event_type in ['remove', 'remove_from_cart', 'cart_remove']:
        return 'cart_remove'
    
    # View events
    if event_type in ['view', 'product_view']:
        return 'view'
    
    # Purchase events
    if event_type in ['purchase', 'buy', 'order']:
        return 'purchase'
    
    # Return original if no match
    return event_type


def extract_event_dataset(db, User, Order, OrderItem, UserEvent) -> pd.DataFrame:
    """
    Extract unified event dataset from database matching screenshot format.
    
    Columns: event_time, event_type, product_id, user_id, user_session
    
    Sources:
    - Purchase events from Order/OrderItem tables
    - Interaction events from UserEvent table (view, cart add/remove)
    
    Args:
        db: SQLAlchemy database session
        User, Order, OrderItem, UserEvent: Model classes
        
    Returns:
        DataFrame with event data
    """
    events = []
    
    # Extract purchase events from orders
    print("Extracting purchase events from orders...")
    orders = db.session.query(Order).join(User).all()
    
    for order in orders:
        # Use order.order_items relationship (not order.items)
        for item in order.order_items:
            events.append({
                'event_time': order.created_at,
                'event_type': 'purchase',
                'product_id': item.product_id,
                'user_id': order.user_id,
                'user_session': order.user.session_id
            })
    
    print(f"Extracted {len(events)} purchase events from {len(orders)} orders")
    
    # Extract interaction events from user_events table
    print("Extracting interaction events...")
    user_events = db.session.query(UserEvent).join(User).filter(
        UserEvent.product_id.isnot(None)
    ).all()
    
    for ue in user_events:
        # Normalize event type
        normalized_type = normalize_event_type(ue.event_type)
        
        events.append({
            'event_time': ue.created_at,
            'event_type': normalized_type,
            'product_id': ue.product_id,
            'user_id': ue.user_id,
            'user_session': ue.user.session_id
        })
    
    print(f"Extracted {len(user_events)} interaction events")
    
    # Convert to DataFrame
    df = pd.DataFrame(events)
    
    if len(df) > 0:
        df['event_time'] = pd.to_datetime(df['event_time'])
        df = df.sort_values('event_time').reset_index(drop=True)
        
        print(f"Total events in dataset: {len(df)}")
        print(f"Unique users: {df['user_id'].nunique()}")
        print(f"Unique products: {df['product_id'].nunique()}")
        print(f"Event types: {df['event_type'].value_counts().to_dict()}")
    else:
        print(f"Total events in dataset: 0")
        print("No data available - waiting for user purchases and interactions")
    
    return df


def build_user_product_aggregation(events_df: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate events into user-product behavior matrix with implicit feedback.
    
    Computes:
    - view_count: number of view events
    - add_count: number of cart add events  
    - remove_count: number of cart remove events
    - purchase_count: number of purchases
    - implicit_score: weighted combination (views + 2*adds - 0.5*removes + 3*purchases)
    - last_event_time: most recent interaction
    
    Args:
        events_df: DataFrame from extract_event_dataset()
        
    Returns:
        DataFrame with (user_id, product_id) aggregations
    """
    print("\nBuilding user-product behavior aggregation...")
    
    if len(events_df) == 0:
        return pd.DataFrame(columns=['user_id', 'product_id', 'view_count', 
                                    'add_count', 'remove_count', 'purchase_count',
                                    'implicit_score', 'last_event_time'])
    
    # Count events by type
    agg = events_df.groupby(['user_id', 'product_id', 'event_type']).size().unstack(fill_value=0)
    
    # Ensure all columns exist
    for col in ['view', 'cart_add', 'cart_remove', 'purchase']:
        if col not in agg.columns:
            agg[col] = 0
    
    # Rename columns
    agg = agg.rename(columns={
        'view': 'view_count',
        'cart_add': 'add_count', 
        'cart_remove': 'remove_count',
        'purchase': 'purchase_count'
    }, errors='ignore')
    
    # Fill missing columns with 0
    for col in ['view_count', 'add_count', 'remove_count', 'purchase_count']:
        if col not in agg.columns:
            agg[col] = 0
    
    # Compute implicit feedback score
    # Formula: 1.0*views + 2.0*adds - 0.5*removes + 3.0*purchases
    agg['implicit_score'] = (
        1.0 * agg['view_count'] +
        2.0 * agg['add_count'] -
        0.5 * agg['remove_count'] +
        3.0 * agg['purchase_count']
    )
    
    # Clip to non-negative
    agg['implicit_score'] = agg['implicit_score'].clip(lower=0)
    
    # Add last event time
    last_events = events_df.groupby(['user_id', 'product_id'])['event_time'].max()
    agg['last_event_time'] = last_events
    
    agg = agg.reset_index()
    
    print(f"Generated {len(agg)} user-product pairs")
    print(f"Users with behavior: {agg['user_id'].nunique()}")
    print(f"Products with behavior: {agg['product_id'].nunique()}")
    print(f"Avg implicit score: {agg['implicit_score'].mean():.2f}")
    print(f"Score distribution:\n{agg['implicit_score'].describe()}")
    
    return agg


def create_id_mappings(behavior_df: pd.DataFrame) -> Tuple[Dict, Dict]:
    """
    Create dense ID mappings for users and products.
    
    Maps sparse user_id/product_id to dense indices 0..N-1 for embedding layers.
    
    Args:
        behavior_df: DataFrame from build_user_product_aggregation()
        
    Returns:
        (user_mapping, product_mapping) where each is dict of {original_id: dense_idx}
    """
    print("\nCreating ID mappings...")
    
    unique_users = sorted(behavior_df['user_id'].unique())
    unique_products = sorted(behavior_df['product_id'].unique())
    
    user_mapping = {uid: idx for idx, uid in enumerate(unique_users)}
    product_mapping = {pid: idx for idx, pid in enumerate(unique_products)}
    
    print(f"User mapping: {len(user_mapping)} users")
    print(f"Product mapping: {len(product_mapping)} products")
    
    return user_mapping, product_mapping


def save_datasets(events_df: pd.DataFrame, behavior_df: pd.DataFrame, 
                 user_mapping: Dict, product_mapping: Dict, output_dir: str = 'ml_data'):
    """
    Save datasets and mappings to disk for model training.
    
    Args:
        events_df: Event dataset
        behavior_df: User-product behavior aggregation
        user_mapping: User ID to index mapping
        product_mapping: Product ID to index mapping
        output_dir: Directory to save files
    """
    os.makedirs(output_dir, exist_ok=True)
    
    # Save DataFrames as parquet for efficient storage
    events_path = os.path.join(output_dir, 'events_unified.parquet')
    behavior_path = os.path.join(output_dir, 'user_product_behavior.parquet')
    
    events_df.to_parquet(events_path, index=False)
    behavior_df.to_parquet(behavior_path, index=False)
    
    print(f"Saved events dataset to {events_path}")
    print(f"Saved behavior dataset to {behavior_path}")
    
    # Save mappings as pickle
    mappings = {
        'user_mapping': user_mapping,
        'product_mapping': product_mapping,
        'num_users': len(user_mapping),
        'num_products': len(product_mapping),
        'created_at': datetime.now().isoformat()
    }
    
    mappings_path = os.path.join(output_dir, 'id_mappings.pkl')
    with open(mappings_path, 'wb') as f:
        pickle.dump(mappings, f)
    
    print(f"Saved ID mappings to {mappings_path}")
    
    # Also save as JSON for debugging
    json_mappings = {
        'num_users': len(user_mapping),
        'num_products': len(product_mapping),
        'created_at': mappings['created_at']
    }
    
    json_path = os.path.join(output_dir, 'id_mappings.json')
    with open(json_path, 'w') as f:
        json.dump(json_mappings, f, indent=2)
    
    print(f"Saved metadata to {json_path}")


def load_datasets(data_dir: str = 'ml_data') -> Tuple[pd.DataFrame, pd.DataFrame, Dict]:
    """
    Load saved datasets and mappings from disk.
    
    Args:
        data_dir: Directory containing saved files
        
    Returns:
        (events_df, behavior_df, mappings_dict)
    """
    events_df = pd.read_parquet(os.path.join(data_dir, 'events_unified.parquet'))
    behavior_df = pd.read_parquet(os.path.join(data_dir, 'user_product_behavior.parquet'))
    
    with open(os.path.join(data_dir, 'id_mappings.pkl'), 'rb') as f:
        mappings = pickle.load(f)
    
    return events_df, behavior_df, mappings


if __name__ == '__main__':
    """
    Standalone script to extract and prepare data for recommendation model.
    Run: python recommendation_engine.py
    """
    from main import app, db, User, Order, OrderItem, UserEvent
    
    with app.app_context():
        # Extract event dataset
        events_df = extract_event_dataset(db, User, Order, OrderItem, UserEvent)
        
        if len(events_df) == 0:
            print("\nNo events found in database. Cannot build recommendation model.")
            print("Recommendation system will fall back to semantic similarity only.")
        else:
            # Build behavior aggregation
            behavior_df = build_user_product_aggregation(events_df)
            
            # Create ID mappings
            user_mapping, product_mapping = create_id_mappings(behavior_df)
            
            # Save datasets
            save_datasets(events_df, behavior_df, user_mapping, product_mapping)
            
            print("\n✓ Data extraction complete!")
            print("Next step: Train collaborative filtering model with train_cf_model.py")
