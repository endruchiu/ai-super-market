"""
Collaborative Filtering with Bayesian Personalized Ranking (BPR)
Pairwise ranking loss for implicit feedback - optimizes item order rather than absolute scores.
Enhanced with Elastic Net regularization (L1 + L2).
"""

import numpy as np
import pandas as pd
import pickle
import os
from sklearn.model_selection import train_test_split
from datetime import datetime

# TensorFlow/Keras imports
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'
import tensorflow as tf
import tf_keras as keras
from tf_keras import layers, Model
from tf_keras.optimizers import Adam
from tf_keras.regularizers import l1_l2
from tf_keras.callbacks import EarlyStopping, ModelCheckpoint, ReduceLROnPlateau

# Local imports
from recommendation_engine import load_datasets
from evaluate_recommendations import evaluate_recommendations, print_evaluation_results


def build_bpr_model(num_users, num_products, embedding_dim=32, l1_reg=1e-6, l2_reg=1e-6):
    """
    Build BPR model with triplet architecture (user, positive_item, negative_item).
    Enhanced with Elastic Net regularization (L1 + L2).
    
    Architecture:
    - User embedding: (num_users, embedding_dim)
    - Product embedding: (num_products, embedding_dim)
    - Interaction: dot product for positive and negative items
    - Loss: BPR loss = -log(sigmoid(score_pos - score_neg))
    
    Args:
        num_users: Number of unique users
        num_products: Number of unique products
        embedding_dim: Size of embedding vectors (default 32)
        l1_reg: L1 regularization strength (default 1e-6)
        l2_reg: L2 regularization strength (default 1e-6)
        
    Returns:
        Keras Model with BPR loss
    """
    elasticnet_reg = l1_l2(l1=l1_reg, l2=l2_reg)
    
    # User input
    user_input = layers.Input(shape=(1,), name='user_input')
    user_embedding = layers.Embedding(
        input_dim=num_users,
        output_dim=embedding_dim,
        embeddings_initializer='he_normal',
        embeddings_regularizer=elasticnet_reg,
        name='user_embedding'
    )(user_input)
    user_vec = layers.Reshape((embedding_dim,))(user_embedding)
    
    # Create shared product embedding layer (used for both positive and negative items)
    product_embedding_layer = layers.Embedding(
        input_dim=num_products,
        output_dim=embedding_dim,
        embeddings_initializer='he_normal',
        embeddings_regularizer=elasticnet_reg,
        name='product_embedding'
    )
    
    # Positive item input - uses shared embedding
    pos_item_input = layers.Input(shape=(1,), name='pos_item_input')
    pos_item_embedding = product_embedding_layer(pos_item_input)
    pos_item_vec = layers.Reshape((embedding_dim,))(pos_item_embedding)
    
    # Negative item input - uses same shared embedding (weights are shared!)
    neg_item_input = layers.Input(shape=(1,), name='neg_item_input')
    neg_item_embedding = product_embedding_layer(neg_item_input)
    neg_item_vec = layers.Reshape((embedding_dim,))(neg_item_embedding)
    
    # Compute scores: user · positive_item and user · negative_item
    pos_score = layers.Dot(axes=1, name='pos_score')([user_vec, pos_item_vec])
    neg_score = layers.Dot(axes=1, name='neg_score')([user_vec, neg_item_vec])
    
    # BPR difference: score_positive - score_negative
    bpr_diff = layers.Subtract(name='bpr_diff')([pos_score, neg_score])
    
    # Output: sigmoid(diff) - we want this close to 1
    output = layers.Activation('sigmoid', name='bpr_output')(bpr_diff)
    
    model = Model(
        inputs=[user_input, pos_item_input, neg_item_input],
        outputs=output,
        name='BPR_CollaborativeFiltering'
    )
    
    return model


def create_bpr_training_data(behavior_df, user_mapping, product_mapping,
                              triplets_per_user=10, test_size=0.2, val_size=0.2, random_state=42):
    """
    Create BPR training data with triplets (user, positive_item, negative_item).
    
    Args:
        behavior_df: User-product behavior aggregation
        user_mapping: User ID to index mapping
        product_mapping: Product ID to index mapping
        triplets_per_user: Number of triplets per positive interaction
        test_size: Fraction for test set
        val_size: Fraction of train for validation
        random_state: Random seed
        
    Returns:
        Training, validation, and test data for BPR
    """
    print("\nCreating BPR training data (triplets)...")
    print(f"Positive interactions: {len(behavior_df)}")
    print(f"Triplets per interaction: {triplets_per_user}")
    
    # Map to indices
    behavior_df['user_idx'] = behavior_df['user_id'].map(user_mapping)
    behavior_df['product_idx'] = behavior_df['product_id'].map(product_mapping)
    
    # Build user-item interaction set
    interaction_set = set(zip(behavior_df['user_idx'], behavior_df['product_idx']))
    
    # Group by user to get positive items
    user_positive_items = behavior_df.groupby('user_idx')['product_idx'].apply(list).to_dict()
    
    # Generate triplets
    np.random.seed(random_state)
    triplet_users = []
    triplet_pos_items = []
    triplet_neg_items = []
    triplet_weights = []
    
    num_products = len(product_mapping)
    
    print("Generating triplets...")
    for user_idx, pos_items in user_positive_items.items():
        for pos_item in pos_items:
            # Generate multiple negative samples for this positive interaction
            for _ in range(triplets_per_user):
                # Sample random negative item (not in user's positive set)
                attempts = 0
                while attempts < 100:
                    neg_item = np.random.randint(0, num_products)
                    if (user_idx, neg_item) not in interaction_set:
                        triplet_users.append(user_idx)
                        triplet_pos_items.append(pos_item)
                        triplet_neg_items.append(neg_item)
                        triplet_weights.append(1.0)
                        break
                    attempts += 1
    
    triplet_users = np.array(triplet_users)
    triplet_pos_items = np.array(triplet_pos_items)
    triplet_neg_items = np.array(triplet_neg_items)
    triplet_weights = np.array(triplet_weights)
    
    # Labels are always 1 (we want sigmoid(pos - neg) ≈ 1)
    labels = np.ones(len(triplet_users))
    
    print(f"Generated {len(triplet_users)} triplets")
    
    # Shuffle
    shuffle_idx = np.random.permutation(len(labels))
    triplet_users = triplet_users[shuffle_idx]
    triplet_pos_items = triplet_pos_items[shuffle_idx]
    triplet_neg_items = triplet_neg_items[shuffle_idx]
    labels = labels[shuffle_idx]
    triplet_weights = triplet_weights[shuffle_idx]
    
    # Split into train/val/test
    total = len(labels)
    test_split = int(total * (1 - test_size))
    val_split = int(test_split * (1 - val_size))
    
    # Train set
    X_train = [
        triplet_users[:val_split],
        triplet_pos_items[:val_split],
        triplet_neg_items[:val_split]
    ]
    y_train = labels[:val_split]
    w_train = triplet_weights[:val_split]
    
    # Validation set
    X_val = [
        triplet_users[val_split:test_split],
        triplet_pos_items[val_split:test_split],
        triplet_neg_items[val_split:test_split]
    ]
    y_val = labels[val_split:test_split]
    w_val = triplet_weights[val_split:test_split]
    
    # Test set
    X_test = [
        triplet_users[test_split:],
        triplet_pos_items[test_split:],
        triplet_neg_items[test_split:]
    ]
    y_test = labels[test_split:]
    w_test = triplet_weights[test_split:]
    
    print(f"Train: {len(y_train)}, Val: {len(y_val)}, Test: {len(y_test)}")
    
    return X_train, y_train, w_train, X_val, y_val, w_val, X_test, y_test, w_test


def train_bpr_model(model, X_train, y_train, w_train, X_val=None, y_val=None, w_val=None,
                    epochs=30, batch_size=2048, learning_rate=0.001):
    """Train BPR model with binary cross-entropy on triplet differences."""
    print("\nCompiling and training BPR model...")
    
    optimizer = Adam(learning_rate=learning_rate)
    model.compile(
        loss='binary_crossentropy',  # On sigmoid(pos - neg)
        optimizer=optimizer,
        metrics=['accuracy']
    )
    
    model.summary()
    
    # Callbacks
    callbacks = []
    
    if X_val is not None:
        callbacks.append(EarlyStopping(
            monitor='val_loss',
            patience=5,
            restore_best_weights=True,
            verbose=1
        ))
    
    os.makedirs('ml_data/checkpoints', exist_ok=True)
    callbacks.append(ModelCheckpoint(
        'ml_data/checkpoints/bpr_model_best.keras',
        monitor='val_loss' if X_val is not None else 'loss',
        save_best_only=True,
        verbose=1
    ))
    
    callbacks.append(ReduceLROnPlateau(
        monitor='val_loss' if X_val is not None else 'loss',
        factor=0.5,
        patience=3,
        min_lr=1e-6,
        verbose=1
    ))
    
    validation_data = None
    if X_val is not None:
        validation_data = (X_val, y_val, w_val)
    
    history = model.fit(
        X_train,
        y_train,
        sample_weight=w_train,
        batch_size=batch_size,
        epochs=epochs,
        validation_data=validation_data,
        callbacks=callbacks,
        verbose=1
    )
    
    print("\n✓ BPR training complete!")
    return history


def save_bpr_model(model, user_mapping, product_mapping, output_dir='ml_data'):
    """Save BPR model and artifacts."""
    os.makedirs(output_dir, exist_ok=True)
    
    model_path = os.path.join(output_dir, 'bpr_model.keras')
    model.save(model_path)
    print(f"\n✓ Saved BPR model to {model_path}")
    
    artifacts = {
        'user_mapping': user_mapping,
        'product_mapping': product_mapping,
        'num_users': len(user_mapping),
        'num_products': len(product_mapping),
        'trained_at': datetime.now().isoformat(),
        'model_type': 'BPR'
    }
    
    artifacts_path = os.path.join(output_dir, 'bpr_artifacts.pkl')
    with open(artifacts_path, 'wb') as f:
        pickle.dump(artifacts, f)
    print(f"✓ Saved BPR artifacts to {artifacts_path}")
    
    # Extract embeddings
    user_embeddings = model.get_layer('user_embedding').get_weights()[0]
    product_embeddings = model.get_layer('product_embedding').get_weights()[0]
    
    embeddings_path = os.path.join(output_dir, 'bpr_embeddings.npz')
    np.savez_compressed(
        embeddings_path,
        user_embeddings=user_embeddings,
        product_embeddings=product_embeddings
    )
    print(f"✓ Saved BPR embeddings to {embeddings_path}")


if __name__ == '__main__':
    print("=" * 60)
    print("BPR (Bayesian Personalized Ranking) Training")
    print("=" * 60)
    
    try:
        events_df, behavior_df, mappings = load_datasets('ml_data')
        print(f"\n✓ Loaded datasets")
        print(f"  Users: {mappings['num_users']}")
        print(f"  Products: {mappings['num_products']}")
        print(f"  Interactions: {len(behavior_df)}")
    except Exception as e:
        print(f"\n✗ Error: {e}")
        print("Run recommendation_engine.py first")
        exit(1)
    
    if len(behavior_df) < 100:
        print("\n✗ Insufficient data (need 100+ interactions)")
        exit(1)
    
    # Create BPR triplet data
    X_train, y_train, w_train, X_val, y_val, w_val, X_test, y_test, w_test = create_bpr_training_data(
        behavior_df,
        mappings['user_mapping'],
        mappings['product_mapping'],
        triplets_per_user=5,
        test_size=0.2,
        val_size=0.2,
        random_state=42
    )
    
    # Build BPR model
    model = build_bpr_model(
        num_users=mappings['num_users'],
        num_products=mappings['num_products'],
        embedding_dim=32,
        l1_reg=1e-6,
        l2_reg=1e-6
    )
    
    # Train
    history = train_bpr_model(
        model,
        X_train, y_train, w_train,
        X_val, y_val, w_val,
        epochs=30,
        batch_size=2048,
        learning_rate=0.001
    )
    
    # Evaluate
    if X_test is not None:
        print("\nEvaluating on test set...")
        test_loss, test_acc = model.evaluate(X_test, y_test, sample_weight=w_test, verbose=0)
        print(f"Test Loss: {test_loss:.4f}")
        print(f"Test Accuracy (triplet correctness): {test_acc:.4f}")
    
    # Save
    save_bpr_model(model, mappings['user_mapping'], mappings['product_mapping'])
    
    print("\n" + "=" * 60)
    print("✓ BPR training complete!")
    print("=" * 60)
