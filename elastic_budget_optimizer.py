"""
Elastic Net Feature Weight Optimizer for Budget-Saving Recommendations
Learns optimal weights for price savings, semantic similarity, health, and size features
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


class BudgetElasticNetOptimizer:
    """
    Learns optimal feature weights for budget-saving recommendations using Elastic Net.
    
    Features:
    - savings_score: Normalized price savings [0, 1]
    - similarity_score: Semantic similarity [0, 1]  
    - health_score: Nutrition improvement [0, 1]
    - size_ratio: Size comparison metric [0, 2]
    
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
            selection='random'
        )
        self.scaler = StandardScaler()
        self.feature_weights = None
        self.is_trained = False
    
    def _extract_features_from_events(self, events_df: pd.DataFrame, products_df: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray]:
        """
        Extract feature matrix and targets from user events.
        
        For each purchase, we create:
        - Positive sample: The product they bought (target=1)
        - Negative samples: Similar products they didn't buy (target=0)
        """
        X_list = []
        y_list = []
        
        # Get purchases only (action='purchase')
        purchases = events_df[events_df['action'] == 'purchase'].copy()
        
        print(f"Processing {len(purchases)} purchase events...")
        
        for idx, purchase in purchases.iterrows():
            product_id = purchase['product_id']
            
            # Find this product in products_df
            # products_df should have columns: product_id, _price_final, Sub Category, etc.
            if product_id not in products_df['product_id'].values:
                continue
            
            product_row = products_df[products_df['product_id'] == product_id].iloc[0]
            price = float(product_row.get('_price_final', 0))
            subcat = str(product_row.get('Sub Category', ''))
            
            # Positive sample: This purchase (target=1)
            # Features: [savings=0, similarity=1.0, health=0.5, size_ratio=1.0]
            # (self-comparison: no savings, perfect similarity, neutral health, same size)
            X_list.append([0.0, 1.0, 0.5, 1.0])
            y_list.append(1.0)  # User purchased this
            
            # Negative samples: Similar products in same category they didn't purchase
            same_category = products_df[
                (products_df['Sub Category'] == subcat) & 
                (products_df['product_id'] != product_id)
            ]
            
            # Sample up to 3 alternatives
            if len(same_category) > 0:
                n_samples = min(3, len(same_category))
                alternatives = same_category.sample(n=n_samples, random_state=42)
                
                for _, alt_row in alternatives.iterrows():
                    alt_price = float(alt_row.get('_price_final', 0))
                    
                    # Compute feature values
                    savings_score = max(0, min(1, (price - alt_price) / price)) if price > 0 else 0
                    similarity_score = 0.75  # Assume high similarity within same subcategory
                    health_score = 0.5  # Neutral (no nutrition data in this simplified version)
                    size_ratio = 1.0  # Assume similar size
                    
                    X_list.append([savings_score, similarity_score, health_score, size_ratio])
                    y_list.append(0.0)  # User did NOT purchase this alternative
        
        X = np.array(X_list)
        y = np.array(y_list)
        
        print(f"Created {len(X)} training samples ({sum(y)} positive, {len(y) - sum(y)} negative)")
        
        return X, y
    
    def train_from_events(self, ml_data_dir: str = 'ml_data') -> Dict:
        """
        Train Elastic Net from user event data.
        
        Args:
            ml_data_dir: Directory containing events.parquet and products data
            
        Returns:
            Training metrics dict
        """
        # Load datasets
        try:
            events_df, behavior_df, mappings = load_datasets(ml_data_dir)
            print(f"Loaded {len(events_df)} events")
        except Exception as e:
            print(f"Error loading datasets: {e}")
            print("Falling back to default weights (no training)")
            self.feature_weights = {
                'savings': 0.6,
                'similarity': 0.3,
                'health': 0.05,
                'size': 0.05
            }
            return {}
        
        # Load products dataframe
        try:
            # Load from semantic_budget cache
            from semantic_budget import ensure_index
            idx = ensure_index()
            products_df = idx['df']
            print(f"Loaded {len(products_df)} products from semantic index")
        except Exception as e:
            print(f"Error loading products: {e}")
            self.feature_weights = {
                'savings': 0.6,
                'similarity': 0.3,
                'health': 0.05,
                'size': 0.05
            }
            return {}
        
        # Extract features
        X, y = self._extract_features_from_events(events_df, products_df)
        
        if len(X) < 10:
            print("Insufficient training data (need at least 10 samples)")
            print("Using default weights")
            self.feature_weights = {
                'savings': 0.6,
                'similarity': 0.3,
                'health': 0.05,
                'size': 0.05
            }
            return {}
        
        # Split train/test
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y if len(np.unique(y)) > 1 else None
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
        
        # Normalize coefficients to sum to 1 (for interpretability)
        coeffs_positive = np.maximum(coeffs, 0)  # Only positive weights make sense
        total = coeffs_positive.sum()
        if total > 0:
            normalized_coeffs = coeffs_positive / total
        else:
            # Fallback to equal weights
            normalized_coeffs = np.array([0.25, 0.25, 0.25, 0.25])
        
        self.feature_weights = {
            'savings': float(normalized_coeffs[0]),
            'similarity': float(normalized_coeffs[1]),
            'health': float(normalized_coeffs[2]),
            'size': float(normalized_coeffs[3])
        }
        
        # Evaluate
        train_score = self.model.score(X_train_scaled, y_train)
        test_score = self.model.score(X_test_scaled, y_test)
        
        metrics = {
            'train_r2': train_score,
            'test_r2': test_score,
            'learned_weights': self.feature_weights,
            'raw_coefficients': coeffs.tolist(),
            'intercept': float(intercept),
            'n_samples': len(X),
            'n_features_nonzero': int(np.sum(coeffs != 0))
        }
        
        self.is_trained = True
        
        print(f"\n✓ Training complete!")
        print(f"  Train R²: {train_score:.4f}")
        print(f"  Test R²: {test_score:.4f}")
        print(f"  Learned feature weights:")
        for name, weight in self.feature_weights.items():
            print(f"    {name}: {weight:.4f}")
        print(f"  Non-zero features: {metrics['n_features_nonzero']}/4")
        
        return metrics
    
    def get_optimal_lambda(self) -> float:
        """
        Get the optimal lambda (weight for savings vs similarity).
        
        Returns:
            Optimal lambda value for budget recommendation scoring
        """
        if not self.is_trained or self.feature_weights is None:
            return 0.6  # Default
        
        # Lambda = savings_weight / (savings_weight + similarity_weight)
        savings = self.feature_weights.get('savings', 0.6)
        similarity = self.feature_weights.get('similarity', 0.3)
        
        total = savings + similarity
        if total > 0:
            return savings / total
        return 0.6
    
    def compute_score(self, savings_score: float, similarity_score: float, 
                     health_score: float = 0.0, size_ratio: float = 1.0) -> float:
        """
        Compute weighted score using learned Elastic Net weights.
        
        Args:
            savings_score: Normalized savings [0, 1]
            similarity_score: Semantic similarity [0, 1]
            health_score: Health improvement [0, 1]
            size_ratio: Size comparison metric
            
        Returns:
            Weighted score
        """
        if not self.is_trained or self.feature_weights is None:
            # Fallback to original formula
            return 0.6 * savings_score + 0.4 * similarity_score
        
        score = (
            self.feature_weights['savings'] * savings_score +
            self.feature_weights['similarity'] * similarity_score +
            self.feature_weights['health'] * health_score +
            self.feature_weights['size'] * (1.0 if 0.8 <= size_ratio <= 1.2 else 0.5)
        )
        
        return score
    
    def save(self, filepath: str = 'ml_data/budget_elasticnet.pkl'):
        """Save trained model and weights."""
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        
        data = {
            'model': self.model,
            'scaler': self.scaler,
            'feature_weights': self.feature_weights,
            'alpha': self.alpha,
            'l1_ratio': self.l1_ratio,
            'is_trained': self.is_trained
        }
        
        with open(filepath, 'wb') as f:
            pickle.dump(data, f)
        
        print(f"✓ Saved Elastic Net optimizer to {filepath}")
    
    @classmethod
    def load(cls, filepath: str = 'ml_data/budget_elasticnet.pkl') -> 'BudgetElasticNetOptimizer':
        """Load trained model and weights."""
        if not os.path.exists(filepath):
            print(f"No trained Elastic Net found at {filepath}, using defaults")
            return cls()
        
        with open(filepath, 'rb') as f:
            data = pickle.load(f)
        
        optimizer = cls(alpha=data['alpha'], l1_ratio=data['l1_ratio'])
        optimizer.model = data['model']
        optimizer.scaler = data['scaler']
        optimizer.feature_weights = data['feature_weights']
        optimizer.is_trained = data['is_trained']
        
        print(f"✓ Loaded Elastic Net optimizer from {filepath}")
        print(f"  Feature weights: {optimizer.feature_weights}")
        
        return optimizer


if __name__ == '__main__':
    """
    Train Elastic Net optimizer for budget recommendations.
    Run: python elastic_budget_optimizer.py
    """
    print("=" * 60)
    print("Elastic Net Budget Optimizer Training")
    print("=" * 60)
    
    # Create and train optimizer
    optimizer = BudgetElasticNetOptimizer(alpha=0.1, l1_ratio=0.5)
    
    metrics = optimizer.train_from_events('ml_data')
    
    if metrics:
        print("\n" + "=" * 60)
        print("Training Metrics:")
        print("=" * 60)
        for key, value in metrics.items():
            print(f"{key}: {value}")
    
    # Save trained optimizer
    optimizer.save()
    
    print("\n✓ Training complete! Use these learned weights in semantic_budget.py")
