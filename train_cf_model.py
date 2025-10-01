"""
Collaborative Filtering Model Training
Uses Keras embeddings for user-product recommendations with implicit feedback.
Based on deep_learning_keras notebook example.
"""

import numpy as np
import pandas as pd
import pickle
import os
from sklearn.model_selection import train_test_split
from datetime import datetime

# TensorFlow/Keras imports
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'  # Reduce TF logging
import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers, Model
from tensorflow.keras.optimizers import Adam
from tensorflow.keras.regularizers import l2
from tensorflow.keras.callbacks import EarlyStopping, ModelCheckpoint, ReduceLROnPlateau

# Local imports
from recommendation_engine import load_datasets


def build_cf_model(num_users, num_products, embedding_dim=32, l2_reg=1e-6):
    """
    Build collaborative filtering model with user and product embeddings.
    
    Architecture:
    - User embedding: (num_users, embedding_dim)
    - Product embedding: (num_products, embedding_dim) 
    - Interaction: dot product
    - Output: sigmoid for implicit preference score
    
    Args:
        num_users: Number of unique users
        num_products: Number of unique products
        embedding_dim: Size of embedding vectors (default 32)
        l2_reg: L2 regularization strength (default 1e-6)
        
    Returns:
        Keras Model
    """
    # User input and embedding
    user_input = layers.Input(shape=(1,), name='user_input')
    user_embedding = layers.Embedding(
        input_dim=num_users,
        output_dim=embedding_dim,
        embeddings_initializer='he_normal',
        embeddings_regularizer=l2(l2_reg),
        name='user_embedding'
    )(user_input)
    user_vec = layers.Reshape((embedding_dim,))(user_embedding)
    
    # Product input and embedding
    product_input = layers.Input(shape=(1,), name='product_input')
    product_embedding = layers.Embedding(
        input_dim=num_products,
        output_dim=embedding_dim,
        embeddings_initializer='he_normal',
        embeddings_regularizer=l2(l2_reg),
        name='product_embedding'
    )(product_input)
    product_vec = layers.Reshape((embedding_dim,))(product_embedding)
    
    # Interaction: dot product
    interaction = layers.Dot(axes=1, name='interaction')([user_vec, product_vec])
    
    # Output: sigmoid activation for implicit preference
    output = layers.Activation('sigmoid', name='preference')(interaction)
    
    # Build model
    model = Model(
        inputs=[user_input, product_input],
        outputs=output,
        name='CollaborativeFiltering'
    )
    
    return model


def create_training_data(behavior_df, user_mapping, product_mapping, 
                        neg_ratio=5, test_size=0.2, val_size=0.2, random_state=42):
    """
    Create training data with positive samples and negative sampling.
    
    Args:
        behavior_df: User-product behavior aggregation
        user_mapping: User ID to index mapping
        product_mapping: Product ID to index mapping
        neg_ratio: Negative samples per positive (default 5)
        test_size: Fraction for test set (default 0.2)
        val_size: Fraction of train for validation (default 0.2)
        random_state: Random seed for reproducibility
        
    Returns:
        (X_train, y_train, sample_weights_train, X_val, y_val, sample_weights_val, X_test, y_test, sample_weights_test)
    """
    print("\nCreating training data...")
    print(f"Behavior pairs: {len(behavior_df)}")
    print(f"Negative sampling ratio: {neg_ratio}:1")
    
    # Map to dense indices
    behavior_df['user_idx'] = behavior_df['user_id'].map(user_mapping)
    behavior_df['product_idx'] = behavior_df['product_id'].map(product_mapping)
    
    # Normalize implicit scores to [0, 1] for sample weighting
    max_score = behavior_df['implicit_score'].max()
    if max_score > 0:
        behavior_df['score_normalized'] = behavior_df['implicit_score'] / max_score
    else:
        behavior_df['score_normalized'] = 1.0
    
    # Positive samples
    pos_user_idx = behavior_df['user_idx'].values
    pos_product_idx = behavior_df['product_idx'].values
    pos_labels = np.ones(len(behavior_df))
    pos_weights = behavior_df['score_normalized'].values
    
    # Negative sampling (uniform random)
    np.random.seed(random_state)
    num_negatives = len(behavior_df) * neg_ratio
    
    # Create user-product interaction set for fast lookup
    interaction_set = set(zip(pos_user_idx, pos_product_idx))
    
    neg_user_idx = []
    neg_product_idx = []
    
    num_users = len(user_mapping)
    num_products = len(product_mapping)
    
    print("Generating negative samples...")
    attempts = 0
    max_attempts = num_negatives * 10  # Prevent infinite loop
    
    while len(neg_user_idx) < num_negatives and attempts < max_attempts:
        # Sample random user and product
        u = np.random.randint(0, num_users)
        p = np.random.randint(0, num_products)
        
        # Only add if not an existing interaction
        if (u, p) not in interaction_set:
            neg_user_idx.append(u)
            neg_product_idx.append(p)
        
        attempts += 1
    
    neg_user_idx = np.array(neg_user_idx)
    neg_product_idx = np.array(neg_product_idx)
    neg_labels = np.zeros(len(neg_user_idx))
    neg_weights = np.ones(len(neg_user_idx)) * 0.5  # Lower weight for negatives
    
    print(f"Generated {len(neg_user_idx)} negative samples")
    
    # Combine positive and negative samples
    all_user_idx = np.concatenate([pos_user_idx, neg_user_idx])
    all_product_idx = np.concatenate([pos_product_idx, neg_product_idx])
    all_labels = np.concatenate([pos_labels, neg_labels])
    all_weights = np.concatenate([pos_weights, neg_weights])
    
    # Shuffle
    shuffle_idx = np.random.permutation(len(all_labels))
    all_user_idx = all_user_idx[shuffle_idx]
    all_product_idx = all_product_idx[shuffle_idx]
    all_labels = all_labels[shuffle_idx]
    all_weights = all_weights[shuffle_idx]
    
    print(f"Total samples: {len(all_labels)} (pos: {len(pos_labels)}, neg: {len(neg_labels)})")
    
    # Split into train/val/test
    # First split: train+val vs test
    X_trainval = [all_user_idx, all_product_idx]
    y_trainval = all_labels
    w_trainval = all_weights
    
    X_test = None
    y_test = None
    w_test = None
    
    if test_size > 0:
        split_idx = int(len(all_labels) * (1 - test_size))
        
        X_train_user = all_user_idx[:split_idx]
        X_train_product = all_product_idx[:split_idx]
        y_train = all_labels[:split_idx]
        w_train = all_weights[:split_idx]
        
        X_test_user = all_user_idx[split_idx:]
        X_test_product = all_product_idx[split_idx:]
        y_test = all_labels[split_idx:]
        w_test = all_weights[split_idx:]
        
        X_trainval = [X_train_user, X_train_product]
        y_trainval = y_train
        w_trainval = w_train
        
        X_test = [X_test_user, X_test_product]
    
    # Second split: train vs val
    X_val = None
    y_val = None
    w_val = None
    
    if val_size > 0:
        val_split_idx = int(len(y_trainval) * (1 - val_size))
        
        X_train = [X_trainval[0][:val_split_idx], X_trainval[1][:val_split_idx]]
        y_train = y_trainval[:val_split_idx]
        w_train = w_trainval[:val_split_idx]
        
        X_val = [X_trainval[0][val_split_idx:], X_trainval[1][val_split_idx:]]
        y_val = y_trainval[val_split_idx:]
        w_val = w_trainval[val_split_idx:]
    else:
        X_train = X_trainval
        y_train = y_trainval
        w_train = w_trainval
    
    print(f"Train set: {len(y_train)} samples")
    if y_val is not None:
        print(f"Val set: {len(y_val)} samples")
    if y_test is not None:
        print(f"Test set: {len(y_test)} samples")
    
    return X_train, y_train, w_train, X_val, y_val, w_val, X_test, y_test, w_test


def train_model(model, X_train, y_train, w_train, X_val=None, y_val=None, w_val=None,
                epochs=30, batch_size=2048, learning_rate=0.001):
    """
    Train the collaborative filtering model.
    
    Args:
        model: Keras model
        X_train, y_train, w_train: Training data
        X_val, y_val, w_val: Validation data (optional)
        epochs: Max epochs (default 30)
        batch_size: Batch size (default 2048)
        learning_rate: Learning rate (default 0.001)
        
    Returns:
        Training history
    """
    print("\nCompiling and training model...")
    
    # Compile model
    optimizer = Adam(learning_rate=learning_rate)
    model.compile(
        loss='binary_crossentropy',
        optimizer=optimizer,
        metrics=['accuracy', 'AUC']
    )
    
    # Print model summary
    model.summary()
    
    # Callbacks
    callbacks = []
    
    # Early stopping
    if X_val is not None:
        callbacks.append(EarlyStopping(
            monitor='val_loss',
            patience=5,
            restore_best_weights=True,
            verbose=1
        ))
    
    # Model checkpoint
    os.makedirs('ml_data/checkpoints', exist_ok=True)
    callbacks.append(ModelCheckpoint(
        'ml_data/checkpoints/cf_model_best.keras',
        monitor='val_loss' if X_val is not None else 'loss',
        save_best_only=True,
        verbose=1
    ))
    
    # Learning rate reduction
    callbacks.append(ReduceLROnPlateau(
        monitor='val_loss' if X_val is not None else 'loss',
        factor=0.5,
        patience=3,
        min_lr=1e-6,
        verbose=1
    ))
    
    # Train
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
    
    print("\n✓ Training complete!")
    
    return history


def save_model_and_artifacts(model, user_mapping, product_mapping, output_dir='ml_data'):
    """
    Save trained model and necessary artifacts for inference.
    
    Args:
        model: Trained Keras model
        user_mapping: User ID to index mapping
        product_mapping: Product ID to index mapping
        output_dir: Directory to save files
    """
    os.makedirs(output_dir, exist_ok=True)
    
    # Save model
    model_path = os.path.join(output_dir, 'cf_model.keras')
    model.save(model_path)
    print(f"\n✓ Saved model to {model_path}")
    
    # Save mappings (already saved by recommendation_engine but save again for convenience)
    artifacts = {
        'user_mapping': user_mapping,
        'product_mapping': product_mapping,
        'num_users': len(user_mapping),
        'num_products': len(product_mapping),
        'trained_at': datetime.now().isoformat()
    }
    
    artifacts_path = os.path.join(output_dir, 'cf_artifacts.pkl')
    with open(artifacts_path, 'wb') as f:
        pickle.dump(artifacts, f)
    
    print(f"✓ Saved artifacts to {artifacts_path}")
    
    # Extract embeddings for fast inference
    user_embeddings = model.get_layer('user_embedding').get_weights()[0]
    product_embeddings = model.get_layer('product_embedding').get_weights()[0]
    
    embeddings_path = os.path.join(output_dir, 'embeddings.npz')
    np.savez_compressed(
        embeddings_path,
        user_embeddings=user_embeddings,
        product_embeddings=product_embeddings
    )
    
    print(f"✓ Saved embeddings to {embeddings_path}")
    print(f"  User embeddings: {user_embeddings.shape}")
    print(f"  Product embeddings: {product_embeddings.shape}")


if __name__ == '__main__':
    """
    Main training script.
    Run: python train_cf_model.py
    
    Prerequisites:
    1. Run recommendation_engine.py to extract and prepare data
    """
    print("=" * 60)
    print("Collaborative Filtering Model Training")
    print("=" * 60)
    
    # Load datasets
    try:
        events_df, behavior_df, mappings = load_datasets('ml_data')
        print(f"\n✓ Loaded datasets from ml_data/")
        print(f"  Events: {len(events_df)} rows")
        print(f"  Behavior pairs: {len(behavior_df)} rows")
        print(f"  Users: {mappings['num_users']}")
        print(f"  Products: {mappings['num_products']}")
    except Exception as e:
        print(f"\n✗ Error loading datasets: {e}")
        print("Please run recommendation_engine.py first to extract data.")
        exit(1)
    
    # Check minimum data requirements
    if len(behavior_df) < 100:
        print("\n✗ Insufficient data for training (need at least 100 user-product pairs)")
        print("Please collect more purchase history data first.")
        exit(1)
    
    # Create training data with negative sampling
    X_train, y_train, w_train, X_val, y_val, w_val, X_test, y_test, w_test = create_training_data(
        behavior_df,
        mappings['user_mapping'],
        mappings['product_mapping'],
        neg_ratio=5,
        test_size=0.2,
        val_size=0.2,
        random_state=42
    )
    
    # Build model
    embedding_dim = 32  # Latent factors
    model = build_cf_model(
        num_users=mappings['num_users'],
        num_products=mappings['num_products'],
        embedding_dim=embedding_dim,
        l2_reg=1e-6
    )
    
    # Train model
    history = train_model(
        model,
        X_train, y_train, w_train,
        X_val, y_val, w_val,
        epochs=30,
        batch_size=2048,
        learning_rate=0.001
    )
    
    # Evaluate on test set if available
    if X_test is not None:
        print("\nEvaluating on test set...")
        test_loss, test_acc, test_auc = model.evaluate(
            X_test, y_test,
            sample_weight=w_test,
            verbose=0
        )
        print(f"Test Loss: {test_loss:.4f}")
        print(f"Test Accuracy: {test_acc:.4f}")
        print(f"Test AUC: {test_auc:.4f}")
    
    # Save model and artifacts
    save_model_and_artifacts(
        model,
        mappings['user_mapping'],
        mappings['product_mapping'],
        output_dir='ml_data'
    )
    
    print("\n" + "=" * 60)
    print("✓ Training pipeline complete!")
    print("=" * 60)
    print("\nNext steps:")
    print("1. Test recommendations with: python test_cf_recommendations.py")
    print("2. Integrate into Flask API: Update main.py with CF endpoints")
