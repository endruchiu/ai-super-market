"""
Elastic Net Blending Weight Optimizer for Hybrid Recommendations
Learns optimal weights for combining CF and Semantic similarity scores
"""

import numpy as np
import pandas as pd
from sklearn.linear_model import ElasticNet
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
import pickle
import os
from typing import Dict, Tuple, Optional

from recommendation_engine import load_datasets
from cf_inference import load_cf_model, get_cf_score_for_product
from semantic_budget import ensure_index, _encode, _GLOBAL


class HybridElasticNetOptimizer:
    """
    Learns optimal blending weights for Hybrid recommendations using Elastic Net.
    
    Features:
    - cf_score: Collaborative Filtering score [0, 1]
    - semantic_score: Content similarity score [0, 1]
    - cf_semantic_interaction: CF * Semantic (interaction term)
    
    Target: User purchase probability (implicit feedback)
    """
    
    def __init__(self, alpha=1.0, l1_ratio=0.5):
        """
        Args:
            alpha: Regularization strength (higher = more regularization)
            l1_ratio: ElasticNet mixing parameter (0=Ridge, 1=Lasso, 0.5=equal mix)
        """
        self.alpha = alpha
        self.l1_ratio = l1_ratio
        self.model = ElasticNet(
            alpha=alpha,
            l1_ratio=l1_ratio,
            random_state=42,
            max_iter=5000,
            positive=True,  # Force positive weights
            selection='random'
        )
        self.scaler = StandardScaler()
        self.cf_weight = 0.6  # Default
        self.semantic_weight = 0.4  # Default
        self.is_trained = False
    
    def _extract_hybrid_features(self, events_df: pd.DataFrame, products_df: pd.DataFrame, 
                                 cf_model, cf_artifacts, semantic_emb) -> Tuple[np.ndarray, np.ndarray]:
        """
        Extract CF and semantic features from user events.
        """
        X_list = []
        y_list = []
        
        # Get purchases only
        purchases = events_df[events_df['action'] == 'purchase'].copy()
        
        print(f"Processing {len(purchases)} purchase events for hybrid training...")
        
        # Load semantic data if not loaded
        if _GLOBAL["df"] is None:
            idx = ensure_index()
            _GLOBAL.update(idx)
        
        df = _GLOBAL["df"]
        emb = _GLOBAL["emb"]
        
        for idx, purchase in purchases.iterrows():
            user_id = purchase['user_id']
            product_id = purchase['product_id']
            
            # Get CF score for this user-product pair
            try:
                cf_score = get_cf_score_for_product(
                    user_id, product_id, cf_model, cf_artifacts
                )
            except:
                cf_score = 0.5  # Neutral score if CF fails
            
            # Get semantic score (cosine similarity to user's purchase history)
            # For purchased item, assume high semantic match
            semantic_score = 0.8
            
            # Positive sample (actual purchase)
            interaction = cf_score * semantic_score
            X_list.append([cf_score, semantic_score, interaction])
            y_list.append(1.0)
            
            # Negative samples: random products user didn't purchase
            # Sample 2 random products from same category
            if product_id in products_df['product_id'].values:
                product_row = products_df[products_df['product_id'] == product_id].iloc[0]
                subcat = str(product_row.get('Sub Category', ''))
                
                same_category = products_df[
                    (products_df['Sub Category'] == subcat) &
                    (products_df['product_id'] != product_id)
                ]
                
                if len(same_category) > 0:
                    n_samples = min(2, len(same_category))
                    alternatives = same_category.sample(n=n_samples, random_state=42)
                    
                    for _, alt_row in alternatives.iterrows():
                        alt_product_id = alt_row['product_id']
                        
                        # Get CF score for alternative
                        try:
                            alt_cf_score = get_cf_score_for_product(
                                user_id, alt_product_id, cf_model, cf_artifacts
                            )
                        except:
                            alt_cf_score = 0.3
                        
                        # Lower semantic score for alternatives
                        alt_semantic_score = 0.6
                        
                        alt_interaction = alt_cf_score * alt_semantic_score
                        X_list.append([alt_cf_score, alt_semantic_score, alt_interaction])
                        y_list.append(0.0)  # User did NOT purchase
        
        X = np.array(X_list)
        y = np.array(y_list)
        
        print(f"Created {len(X)} training samples ({sum(y)} positive, {len(y) - sum(y)} negative)")
        
        return X, y
    
    def train_from_events(self, ml_data_dir: str = 'ml_data') -> Dict:
        """
        Train Elastic Net from user event data.
        
        Returns:
            Training metrics dict
        """
        # Load CF model
        cf_model, cf_artifacts = load_cf_model(os.path.join(ml_data_dir, 'cf_model.keras'))
        if cf_model is None:
            print("No trained CF model found. Cannot train hybrid optimizer.")
            print("Please run: python train_cf_model.py first")
            return {}
        
        # Load datasets
        try:
            events_df, behavior_df, mappings = load_datasets(ml_data_dir)
            print(f"Loaded {len(events_df)} events")
        except Exception as e:
            print(f"Error loading datasets: {e}")
            return {}
        
        # Load products
        try:
            idx = ensure_index()
            products_df = idx['df']
            semantic_emb = idx['emb']
            print(f"Loaded {len(products_df)} products from semantic index")
        except Exception as e:
            print(f"Error loading products: {e}")
            return {}
        
        # Extract features
        X, y = self._extract_hybrid_features(
            events_df, products_df, cf_model, cf_artifacts, semantic_emb
        )
        
        if len(X) < 10:
            print("Insufficient training data (need at least 10 samples)")
            print("Using default weights: 60% CF + 40% Semantic")
            return {}
        
        # Split train/test
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, 
            stratify=y if len(np.unique(y)) > 1 else None
        )
        
        # Scale features
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_test_scaled = self.scaler.transform(X_test)
        
        # Train Elastic Net
        print(f"\nTraining Elastic Net (alpha={self.alpha}, l1_ratio={self.l1_ratio})...")
        self.model.fit(X_train_scaled, y_train)
        
        # Get learned coefficients
        coeffs = self.model.coef_
        intercept = self.model.intercept_
        
        # Extract CF and Semantic weights (ignore interaction term for simplicity)
        cf_coeff = max(0, coeffs[0])
        semantic_coeff = max(0, coeffs[1])
        
        # Normalize to sum to 1
        total = cf_coeff + semantic_coeff
        if total > 0:
            self.cf_weight = float(cf_coeff / total)
            self.semantic_weight = float(semantic_coeff / total)
        else:
            # Fallback
            self.cf_weight = 0.6
            self.semantic_weight = 0.4
        
        # Evaluate
        train_score = self.model.score(X_train_scaled, y_train)
        test_score = self.model.score(X_test_scaled, y_test)
        
        metrics = {
            'train_r2': train_score,
            'test_r2': test_score,
            'cf_weight': self.cf_weight,
            'semantic_weight': self.semantic_weight,
            'raw_coefficients': coeffs.tolist(),
            'intercept': float(intercept),
            'n_samples': len(X),
            'n_features_nonzero': int(np.sum(coeffs != 0))
        }
        
        self.is_trained = True
        
        print(f"\n✓ Training complete!")
        print(f"  Train R²: {train_score:.4f}")
        print(f"  Test R²: {test_score:.4f}")
        print(f"  Learned blending weights:")
        print(f"    CF: {self.cf_weight:.4f} ({self.cf_weight*100:.1f}%)")
        print(f"    Semantic: {self.semantic_weight:.4f} ({self.semantic_weight*100:.1f}%)")
        print(f"  Non-zero features: {metrics['n_features_nonzero']}/3")
        
        return metrics
    
    def get_weights(self) -> Tuple[float, float]:
        """
        Get optimal blending weights.
        
        Returns:
            (cf_weight, semantic_weight) tuple
        """
        return self.cf_weight, self.semantic_weight
    
    def compute_blended_score(self, cf_score: float, semantic_score: float) -> float:
        """
        Compute blended score using learned weights.
        
        Args:
            cf_score: Collaborative Filtering score [0, 1]
            semantic_score: Semantic similarity score [0, 1]
            
        Returns:
            Blended score
        """
        return self.cf_weight * cf_score + self.semantic_weight * semantic_score
    
    def save(self, filepath: str = 'ml_data/hybrid_elasticnet.pkl'):
        """Save trained model and weights."""
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        
        data = {
            'model': self.model,
            'scaler': self.scaler,
            'cf_weight': self.cf_weight,
            'semantic_weight': self.semantic_weight,
            'alpha': self.alpha,
            'l1_ratio': self.l1_ratio,
            'is_trained': self.is_trained
        }
        
        with open(filepath, 'wb') as f:
            pickle.dump(data, f)
        
        print(f"✓ Saved Hybrid Elastic Net optimizer to {filepath}")
    
    @classmethod
    def load(cls, filepath: str = 'ml_data/hybrid_elasticnet.pkl') -> 'HybridElasticNetOptimizer':
        """Load trained model and weights."""
        if not os.path.exists(filepath):
            print(f"No trained Elastic Net found at {filepath}, using defaults (60/40)")
            return cls()
        
        with open(filepath, 'rb') as f:
            data = pickle.load(f)
        
        optimizer = cls(alpha=data['alpha'], l1_ratio=data['l1_ratio'])
        optimizer.model = data['model']
        optimizer.scaler = data['scaler']
        optimizer.cf_weight = data['cf_weight']
        optimizer.semantic_weight = data['semantic_weight']
        optimizer.is_trained = data['is_trained']
        
        print(f"✓ Loaded Hybrid Elastic Net optimizer from {filepath}")
        print(f"  CF: {optimizer.cf_weight:.2%}, Semantic: {optimizer.semantic_weight:.2%}")
        
        return optimizer


if __name__ == '__main__':
    """
    Train Elastic Net optimizer for hybrid blending.
    Run: python elastic_hybrid_optimizer.py
    """
    print("=" * 60)
    print("Elastic Net Hybrid Blending Optimizer Training")
    print("=" * 60)
    
    # Create and train optimizer
    optimizer = HybridElasticNetOptimizer(alpha=0.1, l1_ratio=0.5)
    
    metrics = optimizer.train_from_events('ml_data')
    
    if metrics:
        print("\n" + "=" * 60)
        print("Training Metrics:")
        print("=" * 60)
        for key, value in metrics.items():
            print(f"{key}: {value}")
    
    # Save trained optimizer
    optimizer.save()
    
    print("\n✓ Training complete! Use these learned weights in blended_recommendations.py")
