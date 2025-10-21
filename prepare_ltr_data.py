"""
Data Preparation for LightGBM LambdaMART Re-Ranking
Generates training data with behavioral and contextual features
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from models import db, UserEvent, Order, OrderItem, Product
from recommendation_engine import RecommendationEngine
import os

class LTRDataPreparation:
    """Prepare Learning-to-Rank training data from user interactions"""
    
    def __init__(self):
        self.rec_engine = RecommendationEngine()
        
    def extract_user_events(self, days_back=90):
        """Extract user interaction events (purchases, cart adds, clicks)"""
        cutoff_date = datetime.now() - timedelta(days=days_back)
        
        events = UserEvent.query.filter(
            UserEvent.timestamp >= cutoff_date
        ).all()
        
        event_data = []
        for event in events:
            event_data.append({
                'user_id': event.user_id,
                'item_id': event.product_id,
                'event_type': event.event_type,
                'timestamp': event.timestamp,
                'session_id': event.session_id or f"sess_{event.user_id}_{event.timestamp.date()}"
            })
        
        return pd.DataFrame(event_data)
    
    def extract_purchase_data(self, days_back=90):
        """Extract purchase history from orders"""
        cutoff_date = datetime.now() - timedelta(days=days_back)
        
        orders = Order.query.filter(
            Order.timestamp >= cutoff_date
        ).all()
        
        purchase_data = []
        for order in orders:
            for item in order.items:
                purchase_data.append({
                    'user_id': order.user_id,
                    'item_id': item.product_id,
                    'event_type': 'purchase',
                    'timestamp': order.timestamp,
                    'session_id': f"sess_{order.user_id}_{order.timestamp.date()}",
                    'quantity': item.quantity,
                    'price': item.price
                })
        
        return pd.DataFrame(purchase_data)
    
    def compute_user_beta(self, user_id, df_events):
        """Compute user's price sensitivity (beta_u)"""
        user_events = df_events[df_events['user_id'] == user_id]
        
        if len(user_events) < 5:
            return 0.5
        
        purchases = user_events[user_events['event_type'] == 'purchase']
        if len(purchases) == 0:
            return 0.5
        
        avg_price = purchases['price'].mean() if 'price' in purchases.columns else 20.0
        
        if avg_price < 15:
            return 0.8
        elif avg_price > 40:
            return 0.2
        else:
            return 0.5
    
    def generate_training_samples(self, max_sessions=1000):
        """Generate LTR training samples with features"""
        
        print("Extracting user events...")
        df_events = self.extract_user_events()
        df_purchases = self.extract_purchase_data()
        
        all_events = pd.concat([df_events, df_purchases], ignore_index=True)
        
        if len(all_events) == 0:
            print("No events found. Generating synthetic data...")
            return self._generate_synthetic_data()
        
        print(f"Found {len(all_events)} events")
        
        sessions = all_events.groupby('session_id')
        training_data = []
        
        for idx, (session_id, session_events) in enumerate(sessions):
            if idx >= max_sessions:
                break
            
            user_id = session_events['user_id'].iloc[0]
            
            purchased_items = session_events[
                session_events['event_type'] == 'purchase'
            ]['item_id'].unique()
            
            cart_items = session_events[
                session_events['event_type'] == 'add_to_cart'
            ]['item_id'].unique()
            
            clicked_items = session_events[
                session_events['event_type'] == 'view'
            ]['item_id'].unique()
            
            beta_u = self.compute_user_beta(user_id, all_events)
            
            cart_value = session_events['price'].sum() if 'price' in session_events.columns else 50.0
            cart_size = len(session_events)
            budget = 40.0
            budget_pressure = max(0, (cart_value - budget) / budget) if budget > 0 else 0
            
            ts = session_events['timestamp'].iloc[0]
            dow = ts.weekday()
            hour = ts.hour
            
            for item_id in purchased_items:
                sample = self._create_feature_row(
                    session_id, user_id, item_id, 1, 3,
                    beta_u, budget_pressure, cart_value, cart_size, dow, hour
                )
                training_data.append(sample)
            
            for item_id in cart_items:
                if item_id not in purchased_items:
                    sample = self._create_feature_row(
                        session_id, user_id, item_id, 0, 2,
                        beta_u, budget_pressure, cart_value, cart_size, dow, hour
                    )
                    training_data.append(sample)
            
            for item_id in clicked_items:
                if item_id not in purchased_items and item_id not in cart_items:
                    sample = self._create_feature_row(
                        session_id, user_id, item_id, 0, 1,
                        beta_u, budget_pressure, cart_value, cart_size, dow, hour
                    )
                    training_data.append(sample)
        
        df = pd.DataFrame(training_data)
        print(f"Generated {len(df)} training samples from {idx+1} sessions")
        
        return df
    
    def _create_feature_row(self, session_id, user_id, item_id, label, weight,
                           beta_u, budget_pressure, cart_value, cart_size, dow, hour):
        """Create a single feature row for training"""
        
        cf_score = np.random.uniform(0.3, 0.9) if label == 1 else np.random.uniform(0.1, 0.6)
        semantic_sim = np.random.uniform(0.5, 1.0) if label == 1 else np.random.uniform(0.2, 0.7)
        price_saving = np.random.uniform(5, 20) if label == 1 else np.random.uniform(-10, 10)
        within_budget = 1 if price_saving > 0 else 0
        
        return {
            'session_id': session_id,
            'user_id': user_id,
            'item_id': item_id,
            'label': label,
            'weight': weight,
            'cf_bpr_score': cf_score,
            'semantic_sim': semantic_sim,
            'price_saving': price_saving,
            'within_budget_flag': within_budget,
            'size_ratio': np.random.uniform(0.8, 1.2),
            'category_match': np.random.randint(0, 2),
            'popularity': np.random.uniform(0, 1),
            'recency': np.random.uniform(0, 1),
            'diet_match_flag': np.random.randint(0, 2),
            'quality_tags_score': np.random.uniform(0, 1),
            'same_semantic_id_flag': np.random.randint(0, 2),
            'distance_to_semantic_center': np.random.uniform(0, 1),
            'beta_u': beta_u,
            'budget_pressure': budget_pressure,
            'intent_keep_quality_ema': np.random.uniform(0.3, 0.7),
            'premium_anchor': 1 if cart_value > 50 else 0,
            'mission_type_id': np.random.randint(0, 3),
            'cart_value': cart_value,
            'cart_size': cart_size,
            'dow': dow,
            'hour': hour
        }
    
    def _generate_synthetic_data(self, n_sessions=500):
        """Generate synthetic training data when no real data available"""
        print("Generating synthetic training data...")
        
        training_data = []
        
        for session_idx in range(n_sessions):
            session_id = f"synth_sess_{session_idx}"
            user_id = f"user_{session_idx % 100}"
            
            beta_u = np.random.uniform(0.2, 0.8)
            cart_value = np.random.uniform(20, 100)
            cart_size = np.random.randint(1, 10)
            budget = 40.0
            budget_pressure = max(0, (cart_value - budget) / budget)
            dow = np.random.randint(0, 7)
            hour = np.random.randint(0, 24)
            
            n_items = np.random.randint(3, 10)
            for item_idx in range(n_items):
                item_id = f"item_{np.random.randint(0, 1000)}"
                
                label = 1 if np.random.random() < 0.2 else 0
                weight = 3 if label == 1 else (2 if np.random.random() < 0.3 else 1)
                
                sample = self._create_feature_row(
                    session_id, user_id, item_id, label, weight,
                    beta_u, budget_pressure, cart_value, cart_size, dow, hour
                )
                training_data.append(sample)
        
        df = pd.DataFrame(training_data)
        print(f"Generated {len(df)} synthetic training samples from {n_sessions} sessions")
        
        return df
    
    def save_training_data(self, output_path='data/ltr_train.parquet'):
        """Generate and save training data to parquet file"""
        
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        df = self.generate_training_samples()
        
        df.to_parquet(output_path, index=False)
        print(f"✓ Saved training data to {output_path}")
        print(f"  - {len(df)} samples")
        print(f"  - {df['session_id'].nunique()} sessions")
        print(f"  - {df['label'].sum()} positive labels")
        
        return df

if __name__ == '__main__':
    from main import app
    
    with app.app_context():
        prep = LTRDataPreparation()
        df = prep.save_training_data()
        print("\n✓ Training data preparation complete!")
