"""
Generate synthetic LTR training data with clear behavioral patterns
to ensure LightGBM learns meaningful feature importance
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import random

# Set random seed for reproducibility
np.random.seed(42)
random.seed(42)

# User personas with distinct behavioral patterns
PERSONAS = {
    'budget_hunter': {
        'weight': 0.30,
        'description': 'Prefers cheapest items',
        'feature_preferences': {
            'price_saving': 0.60,  # Very high weight on price
            'semantic_sim': 0.10,
            'cf_bpr_score': 0.10,
            'quality_tags_score': 0.05,
            'budget_pressure': 0.15
        }
    },
    'quality_seeker': {
        'weight': 0.30,
        'description': 'Prefers high-quality, similar items',
        'feature_preferences': {
            'price_saving': 0.05,
            'semantic_sim': 0.50,  # Very high weight on similarity
            'cf_bpr_score': 0.15,
            'quality_tags_score': 0.25,  # High weight on quality
            'budget_pressure': 0.05
        }
    },
    'cf_follower': {
        'weight': 0.20,
        'description': 'Follows collaborative filtering recommendations',
        'feature_preferences': {
            'price_saving': 0.15,
            'semantic_sim': 0.20,
            'cf_bpr_score': 0.50,  # Very high weight on CF
            'quality_tags_score': 0.10,
            'budget_pressure': 0.05
        }
    },
    'budget_pressured': {
        'weight': 0.20,
        'description': 'Behavior changes based on cart total',
        'feature_preferences': {
            'price_saving': 0.30,
            'semantic_sim': 0.15,
            'cf_bpr_score': 0.10,
            'quality_tags_score': 0.10,
            'budget_pressure': 0.35  # Very high weight on budget pressure
        }
    }
}

def generate_synthetic_samples(num_sessions=200, candidates_per_session=5):
    """Generate synthetic LTR training data with clear patterns"""
    
    samples = []
    
    for session_id in range(num_sessions):
        # Choose persona for this session
        persona_name = np.random.choice(
            list(PERSONAS.keys()),
            p=[p['weight'] for p in PERSONAS.values()]
        )
        persona = PERSONAS[persona_name]
        
        # Session context
        user_id = f"synthetic_user_{session_id % 50}"  # 50 unique users
        cart_value = np.random.uniform(20, 100)
        cart_size = np.random.randint(1, 15)
        budget = np.random.choice([30, 40, 50, 60, 80, 100])
        
        # Behavioral features
        beta_u = np.random.uniform(0.3, 0.7)
        budget_pressure = max(0, (cart_value - budget) / budget) if budget > 0 else 0
        intent_keep_quality_ema = np.random.uniform(0.3, 0.7)
        premium_anchor = 1 if cart_value > 60 else 0
        mission_type_id = np.random.randint(0, 3)
        
        # Temporal features
        base_time = datetime.now() - timedelta(days=np.random.randint(0, 30))
        dow = base_time.weekday()
        hour = np.random.randint(8, 22)
        
        # Generate candidates for this session
        for rank in range(candidates_per_session):
            # Generate feature values with some randomness
            cf_bpr_score = np.random.beta(2, 5) * 10  # 0-10 range, skewed toward lower
            semantic_sim = np.random.beta(3, 2)  # 0-1 range, skewed toward higher
            price_saving = np.random.uniform(-5, 30)  # Can be negative (more expensive)
            quality_tags_score = np.random.beta(2, 3)  # 0-1 range
            
            # Other features
            within_budget_flag = 1 if (cart_value + price_saving) <= budget else 0
            size_ratio = np.random.uniform(0.8, 1.2)
            category_match = np.random.choice([0, 1], p=[0.3, 0.7])
            popularity = np.random.beta(2, 5)
            recency = np.random.uniform(0, 1)
            diet_match_flag = np.random.choice([0, 1], p=[0.7, 0.3])
            same_semantic_id_flag = np.random.choice([0, 1], p=[0.8, 0.2])
            distance_to_semantic_center = np.random.uniform(0, 2)
            
            # Calculate click probability based on persona preferences
            feature_scores = {
                'price_saving': price_saving / 30.0,  # Normalize to 0-1
                'semantic_sim': semantic_sim,
                'cf_bpr_score': cf_bpr_score / 10.0,  # Normalize to 0-1
                'quality_tags_score': quality_tags_score,
                'budget_pressure': budget_pressure
            }
            
            # Weighted sum based on persona preferences
            click_score = sum(
                persona['feature_preferences'].get(feat, 0) * score
                for feat, score in feature_scores.items()
            )
            
            # Add some noise and convert to probability
            click_score = np.clip(click_score + np.random.normal(0, 0.1), 0, 1)
            
            # Label: 1 if clicked, 0 if skipped
            # Top-ranked items more likely to be clicked
            position_bias = (candidates_per_session - rank) / candidates_per_session
            final_probability = 0.7 * click_score + 0.3 * position_bias
            label = 1 if np.random.random() < final_probability else 0
            
            # Create sample
            sample = {
                'session_id': f"session_{session_id}",
                'user_id': user_id,
                'product_id': f"product_{session_id}_{rank}",
                'label': label,
                'weight': 1.0,
                
                # Main features
                'cf_bpr_score': cf_bpr_score,
                'semantic_sim': semantic_sim,
                'price_saving': price_saving,
                'within_budget_flag': within_budget_flag,
                'size_ratio': size_ratio,
                'category_match': category_match,
                'popularity': popularity,
                'recency': recency,
                'diet_match_flag': diet_match_flag,
                'quality_tags_score': quality_tags_score,
                'same_semantic_id_flag': same_semantic_id_flag,
                'distance_to_semantic_center': distance_to_semantic_center,
                
                # Behavioral features
                'beta_u': beta_u,
                'budget_pressure': budget_pressure,
                'intent_keep_quality_ema': intent_keep_quality_ema,
                'premium_anchor': premium_anchor,
                'mission_type_id': mission_type_id,
                'cart_value': cart_value,
                'cart_size': cart_size,
                
                # Temporal features
                'dow': dow,
                'hour': hour,
                
                # Metadata
                'persona': persona_name
            }
            
            samples.append(sample)
    
    return pd.DataFrame(samples)

def main():
    print("Generating synthetic LTR training data...")
    print("=" * 60)
    
    # Generate data
    df = generate_synthetic_samples(num_sessions=200, candidates_per_session=5)
    
    print(f"\n✓ Generated {len(df)} training samples")
    print(f"  - Sessions: {df['session_id'].nunique()}")
    print(f"  - Users: {df['user_id'].nunique()}")
    print(f"  - Positive labels: {df['label'].sum()} ({100*df['label'].mean():.1f}%)")
    
    # Show persona distribution
    print("\nPersona distribution:")
    persona_counts = df.groupby('persona')['label'].agg(['count', 'sum', 'mean'])
    for persona, row in persona_counts.iterrows():
        print(f"  {persona:20s}: {int(row['count']):4d} samples, "
              f"{int(row['sum']):3d} clicks ({100*row['mean']:.1f}%)")
    
    # Show feature statistics
    print("\nFeature value ranges:")
    key_features = ['cf_bpr_score', 'semantic_sim', 'price_saving', 'budget_pressure', 'quality_tags_score']
    for feat in key_features:
        print(f"  {feat:25s}: [{df[feat].min():7.2f}, {df[feat].max():7.2f}]  "
              f"mean={df[feat].mean():6.2f}")
    
    # Save to parquet
    output_path = 'data/ltr_train.parquet'
    df.to_parquet(output_path, index=False)
    print(f"\n✓ Saved to {output_path}")
    
    import os
    file_size_kb = os.path.getsize(output_path) / 1024
    print(f"  File size: {file_size_kb:.1f} KB")
    
    print("\n" + "=" * 60)
    print("Synthetic data generation complete!")
    print("This data has clear behavioral patterns that will")
    print("produce meaningful feature importance values.")

if __name__ == '__main__':
    main()
