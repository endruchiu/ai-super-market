#!/usr/bin/env python3
"""
User Behavior Simulation for Grocery Recommendation System

Generates 100 realistic user sessions with diverse behavioral patterns to populate
analytics dashboard with meaningful data demonstrating all 10 behavioral metrics.
"""

import os
import sys
import random
import hashlib
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Tuple
import pandas as pd
import numpy as np

from sqlalchemy import create_engine, Column, Integer, String, BigInteger, Text, Numeric, Boolean, DateTime, ForeignKey, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

DATABASE_URL = os.environ.get('DATABASE_URL')
if not DATABASE_URL:
    print("ERROR: DATABASE_URL environment variable not set")
    sys.exit(1)

engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)
Base = declarative_base()


class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    session_id = Column(String(255), nullable=False, unique=True)
    name = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=func.current_timestamp())


class Product(Base):
    __tablename__ = 'products'
    id = Column(Integer, primary_key=True)
    title = Column(Text, nullable=False)
    sub_category = Column(String(200), nullable=False)
    price_numeric = Column(Numeric(10, 2), nullable=True)
    calories = Column(Integer, nullable=True)
    protein_g = Column(Numeric(5, 1), nullable=True)
    sugar_g = Column(Numeric(5, 1), nullable=True)
    sodium_mg = Column(Integer, nullable=True)


class RecommendationInteraction(Base):
    __tablename__ = 'recommendation_interactions'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    recommendation_id = Column(String(100), nullable=False)
    original_product_id = Column(BigInteger, nullable=False)
    recommended_product_id = Column(BigInteger, nullable=False)
    original_product_title = Column(Text, nullable=False)
    recommended_product_title = Column(Text, nullable=False)
    expected_saving = Column(Numeric(10, 2), nullable=True)
    recommendation_reason = Column(Text, nullable=True)
    has_explanation = Column(Boolean, default=True)
    action_type = Column(String(50), nullable=False)
    shown_at = Column(DateTime, default=func.current_timestamp())
    action_at = Column(DateTime, nullable=True)
    time_to_action_seconds = Column(Integer, nullable=True)
    scroll_depth_percent = Column(Integer, nullable=True)
    original_price = Column(Numeric(10, 2), nullable=True)
    recommended_price = Column(Numeric(10, 2), nullable=True)
    original_protein = Column(Numeric(5, 1), nullable=True)
    recommended_protein = Column(Numeric(5, 1), nullable=True)
    original_sugar = Column(Numeric(5, 1), nullable=True)
    recommended_sugar = Column(Numeric(5, 1), nullable=True)
    original_calories = Column(Integer, nullable=True)
    recommended_calories = Column(Integer, nullable=True)
    removed_from_cart_at = Column(DateTime, nullable=True)
    was_removed = Column(Boolean, default=False)
    created_at = Column(DateTime, default=func.current_timestamp())


USER_PERSONAS = {
    'power_user': {
        'weight': 0.20,
        'rar_range': (70, 95),
        'acr_range': (85, 100),
        'time_to_accept_range': (2, 8),
        'scroll_depth_range': (80, 100),
        'removal_rate_range': (5, 20),
        'has_explanation_prob': 0.9,
    },
    'budget_conscious': {
        'weight': 0.25,
        'rar_range': (60, 85),
        'acr_range': (70, 90),
        'time_to_accept_range': (5, 15),
        'scroll_depth_range': (70, 95),
        'removal_rate_range': (10, 25),
        'has_explanation_prob': 0.8,
    },
    'casual_shopper': {
        'weight': 0.30,
        'rar_range': (30, 60),
        'acr_range': (40, 70),
        'time_to_accept_range': (10, 30),
        'scroll_depth_range': (40, 70),
        'removal_rate_range': (20, 40),
        'has_explanation_prob': 0.6,
    },
    'dismissive_user': {
        'weight': 0.15,
        'rar_range': (5, 30),
        'acr_range': (10, 40),
        'time_to_accept_range': (15, 60),
        'scroll_depth_range': (20, 50),
        'removal_rate_range': (40, 70),
        'has_explanation_prob': 0.4,
    },
    'explorer': {
        'weight': 0.10,
        'rar_range': (50, 75),
        'acr_range': (60, 85),
        'time_to_accept_range': (3, 12),
        'scroll_depth_range': (85, 100),
        'removal_rate_range': (15, 35),
        'has_explanation_prob': 0.75,
    }
}


def generate_product_id(title: str, subcategory: str) -> int:
    """Generate stable product ID using blake2b hash (matches main.py logic)"""
    key = f"{title}|{subcategory}"
    hash_bytes = hashlib.blake2b(key.encode('utf-8'), digest_size=8).digest()
    return int.from_bytes(hash_bytes, 'big', signed=False) & ((1 << 63) - 1)


def load_sample_products(db_session) -> List[Dict]:
    """Load sample products from database or generate synthetic ones"""
    
    products = db_session.query(Product).limit(50).all()
    
    if products:
        product_list = []
        for p in products:
            product_list.append({
                'id': p.id,
                'title': p.title,
                'subcategory': p.sub_category,
                'price': float(p.price_numeric) if p.price_numeric else random.uniform(2, 15),
                'calories': p.calories or random.randint(50, 500),
                'protein': float(p.protein_g) if p.protein_g else round(random.uniform(1, 20), 1),
                'sugar': float(p.sugar_g) if p.sugar_g else round(random.uniform(1, 40), 1),
                'sodium': p.sodium_mg or random.randint(50, 1500),
            })
        return product_list
    
    print("No products in database, generating synthetic product samples...")
    synthetic_products = [
        {'title': 'Organic Milk 1L', 'subcategory': 'Dairy', 'price': 4.99, 'calories': 150, 'protein': 8, 'sugar': 12, 'sodium': 120},
        {'title': 'Whole Wheat Bread', 'subcategory': 'Bakery', 'price': 3.49, 'calories': 80, 'protein': 4, 'sugar': 2, 'sodium': 140},
        {'title': 'Fresh Bananas 1kg', 'subcategory': 'Produce', 'price': 2.99, 'calories': 89, 'protein': 1, 'sugar': 12, 'sodium': 1},
        {'title': 'Greek Yogurt 500g', 'subcategory': 'Dairy', 'price': 5.99, 'calories': 100, 'protein': 10, 'sugar': 7, 'sodium': 50},
        {'title': 'Brown Rice 2kg', 'subcategory': 'Grains', 'price': 6.49, 'calories': 111, 'protein': 3, 'sugar': 0, 'sodium': 5},
        {'title': 'Chicken Breast 1kg', 'subcategory': 'Meat', 'price': 12.99, 'calories': 165, 'protein': 31, 'sugar': 0, 'sodium': 74},
        {'title': 'Cheddar Cheese 500g', 'subcategory': 'Dairy', 'price': 7.99, 'calories': 403, 'protein': 25, 'sugar': 1, 'sodium': 621},
        {'title': 'Apple Juice 1L', 'subcategory': 'Beverages', 'price': 3.99, 'calories': 46, 'protein': 0, 'sugar': 10, 'sodium': 4},
        {'title': 'Pasta 500g', 'subcategory': 'Grains', 'price': 2.49, 'calories': 131, 'protein': 5, 'sugar': 2, 'sodium': 6},
        {'title': 'Tomato Sauce 680g', 'subcategory': 'Condiments', 'price': 4.49, 'calories': 70, 'protein': 2, 'sugar': 8, 'sodium': 480},
    ]
    
    for prod in synthetic_products:
        prod['id'] = generate_product_id(prod['title'], prod['subcategory'])
    
    return synthetic_products


def select_persona() -> Tuple[str, Dict]:
    """Select a user persona based on weights"""
    personas = list(USER_PERSONAS.keys())
    weights = [USER_PERSONAS[p]['weight'] for p in personas]
    persona_name = random.choices(personas, weights=weights, k=1)[0]
    return persona_name, USER_PERSONAS[persona_name]


def generate_session_metrics(persona_config: Dict, recs_shown: int) -> Dict:
    """Generate session-level metrics based on persona"""
    
    rar_target = random.uniform(*persona_config['rar_range']) / 100
    acr_target = random.uniform(*persona_config['acr_range']) / 100
    removal_rate = random.uniform(*persona_config['removal_rate_range']) / 100
    
    accepts = max(1, int(recs_shown * rar_target))
    accepts = min(accepts, recs_shown)
    
    added_to_cart = max(1, int(accepts * acr_target))
    
    dismisses = recs_shown - accepts
    
    removed_later = int(added_to_cart * removal_rate)
    
    avg_time_to_accept = random.uniform(*persona_config['time_to_accept_range'])
    avg_scroll_depth = random.uniform(*persona_config['scroll_depth_range'])
    
    return {
        'recs_shown': recs_shown,
        'accepts': accepts,
        'dismisses': dismisses,
        'added_to_cart': added_to_cart,
        'removed_later': removed_later,
        'avg_time_to_accept': avg_time_to_accept,
        'avg_scroll_depth': avg_scroll_depth,
        'has_explanation_prob': persona_config['has_explanation_prob'],
    }


def create_user_if_needed(db_session, user_id: int) -> None:
    """Create a user if they don't exist"""
    
    existing = db_session.query(User).filter_by(id=user_id).first()
    if not existing:
        new_user = User(
            id=user_id,
            session_id=f"sim_user_{user_id}@simulation.local",
            name=f"Simulated User {user_id}",
            created_at=datetime.now() - timedelta(days=random.randint(30, 180))
        )
        db_session.add(new_user)
        db_session.flush()


def simulate_session(session_id: int, user_id: int, products: List[Dict], db_session) -> None:
    """Simulate a complete user session with recommendations"""
    
    persona_name, persona_config = select_persona()
    
    recs_shown = random.randint(1, 10)
    
    metrics = generate_session_metrics(persona_config, recs_shown)
    
    create_user_if_needed(db_session, user_id)
    
    session_start = datetime.now() - timedelta(days=random.randint(0, 30))
    
    interactions = []
    accept_count = 0
    dismiss_count = 0
    removal_count = 0
    
    for rec_idx in range(recs_shown):
        original = random.choice(products)
        recommended = random.choice([p for p in products if p['id'] != original['id']])
        
        price_diff = original['price'] - recommended['price']
        saving = max(0, price_diff)
        
        has_explanation = random.random() < metrics['has_explanation_prob']
        
        # Determine if this will be accepted or dismissed
        will_accept = accept_count < metrics['accepts']
        if will_accept:
            accept_count += 1
        else:
            dismiss_count += 1
        
        shown_at = session_start + timedelta(seconds=rec_idx * random.uniform(2, 10))
        
        scroll_depth = int(random.gauss(metrics['avg_scroll_depth'], 10))
        scroll_depth = max(0, min(100, scroll_depth))
        
        reasons = [
            f"Save ${saving:.2f} with healthier alternative",
            f"Better nutrition profile - lower sugar",
            f"Popular substitute in your category",
            f"Budget-friendly option - ${saving:.2f} cheaper",
            f"Similar product with better value",
        ]
        
        # Create base data for both shown and action events
        base_data = {
            'user_id': user_id,
            'recommendation_id': f"sim_{session_id}_{rec_idx}",
            'original_product_id': original['id'],
            'recommended_product_id': recommended['id'],
            'original_product_title': original['title'],
            'recommended_product_title': recommended['title'],
            'expected_saving': Decimal(str(round(saving, 2))),
            'recommendation_reason': random.choice(reasons) if has_explanation else None,
            'has_explanation': has_explanation,
            'shown_at': shown_at,
            'scroll_depth_percent': scroll_depth,
            'original_price': Decimal(str(original['price'])),
            'recommended_price': Decimal(str(recommended['price'])),
            'original_protein': Decimal(str(original['protein'])),
            'recommended_protein': Decimal(str(recommended['protein'])),
            'original_sugar': Decimal(str(original['sugar'])),
            'recommended_sugar': Decimal(str(recommended['sugar'])),
            'original_calories': original['calories'],
            'recommended_calories': recommended['calories'],
        }
        
        # 1. Create SHOWN event (exposure tracking)
        shown_event = RecommendationInteraction(
            action_type='shown',
            action_at=None,
            time_to_action_seconds=None,
            removed_from_cart_at=None,
            was_removed=False,
            **base_data
        )
        interactions.append(shown_event)
        
        # 2. Create ACTION event (accept or dismiss)
        action_type = 'accept' if will_accept else 'dismiss'
        
        if action_type == 'accept':
            time_to_action = int(random.gauss(metrics['avg_time_to_accept'], 3))
            time_to_action = max(1, time_to_action)
        else:
            time_to_action = int(random.uniform(1, 5))
        
        action_at = shown_at + timedelta(seconds=time_to_action)
        
        # Determine if this accepted item will be removed later
        will_remove = (action_type == 'accept' and removal_count < metrics['removed_later'])
        if will_remove:
            removal_count += 1
            was_removed = True
            removed_at = action_at + timedelta(minutes=random.randint(1, 30))
        else:
            was_removed = False
            removed_at = None
        
        action_event = RecommendationInteraction(
            action_type=action_type,
            action_at=action_at,
            time_to_action_seconds=time_to_action,
            removed_from_cart_at=removed_at,
            was_removed=was_removed,
            **base_data
        )
        interactions.append(action_event)
    
    db_session.bulk_save_objects(interactions)
    
    print(f"  Session {session_id} [{persona_name}]: {recs_shown} recs, {accept_count} accepts, "
          f"{dismiss_count} dismisses, {metrics['removed_later']} removed")


def main():
    print("=" * 70)
    print("User Behavior Simulation for Grocery Recommendation System")
    print("=" * 70)
    print(f"\nGenerating 100 realistic user sessions...\n")
    
    db_session = Session()
    
    try:
        print("Loading product catalog...")
        products = load_sample_products(db_session)
        print(f"✓ Loaded {len(products)} products\n")
        
        print("Generating user sessions with diverse behavioral patterns:\n")
        
        user_pool = list(range(1, 31))
        
        for session_id in range(1, 101):
            user_id = random.choice(user_pool)
            
            simulate_session(session_id, user_id, products, db_session)
            
            if session_id % 20 == 0:
                db_session.commit()
                print(f"\n  ✓ Committed batch {session_id // 20}\n")
        
        db_session.commit()
        
        print("\n" + "=" * 70)
        print("✓ Simulation Complete!")
        print("=" * 70)
        
        total = db_session.query(func.count(RecommendationInteraction.id)).scalar()
        accepts = db_session.query(func.count(RecommendationInteraction.id)).filter(
            RecommendationInteraction.action_type == 'accept'
        ).scalar()
        dismisses = db_session.query(func.count(RecommendationInteraction.id)).filter(
            RecommendationInteraction.action_type == 'dismiss'
        ).scalar()
        
        print(f"\nGenerated Statistics:")
        print(f"  Total Interactions: {total}")
        print(f"  Accepts: {accepts} ({accepts/total*100:.1f}%)")
        print(f"  Dismisses: {dismisses} ({dismisses/total*100:.1f}%)")
        print(f"\n✓ Data ready for analytics dashboard at /analytics")
        print("=" * 70)
        
    except Exception as e:
        print(f"\n✗ Error during simulation: {e}")
        db_session.rollback()
        raise
    finally:
        db_session.close()


if __name__ == "__main__":
    main()
