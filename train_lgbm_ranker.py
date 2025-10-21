"""
LightGBM LambdaMART Ranker Training
Trains a Learning-to-Rank model with GPU→CPU fallback
"""
import pandas as pd
import numpy as np
import lightgbm as lgb
import os
import sys

class LGBMRankerTrainer:
    """Train LightGBM LambdaMART model for recommendation re-ranking"""
    
    def __init__(self, train_data_path='data/ltr_train.parquet'):
        self.train_data_path = train_data_path
        self.model = None
        self.feature_cols = [
            'cf_bpr_score', 'semantic_sim', 'price_saving', 'within_budget_flag',
            'size_ratio', 'category_match', 'popularity', 'recency',
            'diet_match_flag', 'quality_tags_score', 'same_semantic_id_flag',
            'distance_to_semantic_center', 'beta_u', 'budget_pressure',
            'intent_keep_quality_ema', 'premium_anchor', 'mission_type_id',
            'cart_value', 'cart_size', 'dow', 'hour'
        ]
    
    def load_data(self):
        """Load training data from parquet file"""
        print(f"Loading training data from {self.train_data_path}...")
        
        if not os.path.exists(self.train_data_path):
            print(f"Error: Training data not found at {self.train_data_path}")
            print("Please run prepare_ltr_data.py first to generate training data.")
            sys.exit(1)
        
        df = pd.read_parquet(self.train_data_path)
        print(f"✓ Loaded {len(df)} samples from {df['session_id'].nunique()} sessions")
        
        for col in self.feature_cols:
            if col not in df.columns:
                print(f"Warning: Missing feature '{col}', filling with 0")
                df[col] = 0
        
        return df
    
    def prepare_dataset(self, df):
        """Prepare LightGBM dataset with query groups"""
        
        df = df.sort_values('session_id')
        
        X = df[self.feature_cols].values
        y = df['label'].values
        
        query_ids = df['session_id'].values
        unique_queries, query_counts = np.unique(query_ids, return_counts=True)
        
        weights = df['weight'].values if 'weight' in df.columns else None
        
        print(f"✓ Prepared dataset:")
        print(f"  - Features: {X.shape[1]}")
        print(f"  - Samples: {X.shape[0]}")
        print(f"  - Queries (sessions): {len(unique_queries)}")
        print(f"  - Positive labels: {y.sum()} ({100*y.mean():.1f}%)")
        
        return X, y, query_counts, weights
    
    def train(self, use_gpu=True):
        """Train LightGBM LambdaMART model with GPU→CPU fallback"""
        
        df = self.load_data()
        X, y, query_counts, weights = self.prepare_dataset(df)
        
        train_data = lgb.Dataset(
            X, label=y, group=query_counts, weight=weights
        )
        
        params = {
            "objective": "lambdarank",
            "metric": "ndcg",
            "ndcg_eval_at": [5, 10],
            "learning_rate": 0.05,
            "num_leaves": 31,
            "min_data_in_leaf": 15,
            "feature_pre_filter": False,
            "device": "gpu" if use_gpu else "cpu",
            "verbose": 1,
            "force_col_wise": True,
            "min_gain_to_split": 0.0
        }
        
        print(f"\nTraining LightGBM LambdaMART (device: {params['device']})...")
        print(f"  - num_boost_round: 300 (increased for better feature learning)")
        print(f"  - min_data_in_leaf: 15 (reduced to allow finer splits)")
        print(f"  - early_stopping: 75 rounds (more patient)")
        
        try:
            self.model = lgb.train(
                params,
                train_data,
                num_boost_round=300,
                valid_sets=[train_data],
                valid_names=['train'],
                callbacks=[
                    lgb.log_evaluation(period=25),
                    lgb.early_stopping(stopping_rounds=75)
                ]
            )
            
            print(f"✓ Training completed successfully on {params['device'].upper()}")
            
        except Exception as e:
            if use_gpu:
                print(f"\n⚠ GPU training failed: {str(e)}")
                print("→ Falling back to CPU training...")
                return self.train(use_gpu=False)
            else:
                print(f"✗ Training failed: {str(e)}")
                raise
        
        return self.model
    
    def save_model(self, output_path='models/lgbm_ltr.txt'):
        """Save trained model to file"""
        
        if self.model is None:
            print("Error: No model to save. Train the model first.")
            return
        
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        self.model.save_model(output_path)
        print(f"✓ Model saved to {output_path}")
        
        print("\nFeature importance:")
        importance = self.model.feature_importance(importance_type='gain')
        feature_importance = pd.DataFrame({
            'feature': self.feature_cols,
            'importance': importance
        }).sort_values('importance', ascending=False)
        
        print(feature_importance.head(10).to_string(index=False))
    
    def evaluate(self, df_test=None):
        """Evaluate model performance"""
        
        if self.model is None:
            print("Error: No model to evaluate. Train the model first.")
            return
        
        if df_test is None:
            print("Using training data for evaluation (for demonstration)")
            df_test = self.load_data()
        
        X, y, query_counts, _ = self.prepare_dataset(df_test)
        
        predictions = self.model.predict(X)
        
        print("\n✓ Model Evaluation:")
        print(f"  - Mean prediction score: {predictions.mean():.4f}")
        print(f"  - Prediction range: [{predictions.min():.4f}, {predictions.max():.4f}]")
        
        positive_preds = predictions[y == 1]
        negative_preds = predictions[y == 0]
        
        if len(positive_preds) > 0 and len(negative_preds) > 0:
            print(f"  - Avg score for positive labels: {positive_preds.mean():.4f}")
            print(f"  - Avg score for negative labels: {negative_preds.mean():.4f}")
            print(f"  - Separation: {positive_preds.mean() - negative_preds.mean():.4f}")

def main():
    """Main training pipeline"""
    
    print("=" * 60)
    print("LightGBM LambdaMART Re-Ranker Training")
    print("=" * 60 + "\n")
    
    trainer = LGBMRankerTrainer()
    
    trainer.train(use_gpu=True)
    
    trainer.save_model()
    
    trainer.evaluate()
    
    print("\n" + "=" * 60)
    print("✓ Training complete! Model ready for production.")
    print("=" * 60)

if __name__ == '__main__':
    main()
