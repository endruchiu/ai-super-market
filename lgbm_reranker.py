"""
LightGBM Re-Ranker Integration
Behavior-aware re-ranking with intent smoothing and guardrails
"""
import pandas as pd
import numpy as np
import lightgbm as lgb
import os
from datetime import datetime
from typing import List, Dict, Any, Optional

class IntentTracker:
    """Track user intent with EMA smoothing and cooldown"""
    
    def __init__(self, alpha=0.3, cooldown_seconds=45):
        self.alpha = alpha
        self.cooldown_seconds = cooldown_seconds
        self.user_intents = {}
        self.last_mode_switch = {}
    
    def update_intent(self, user_id: str, current_intent: float) -> float:
        """
        Update intent with EMA smoothing
        intent_keep_quality_ema = 0.3 * current_intent + 0.7 * previous_ema
        """
        if user_id not in self.user_intents:
            self.user_intents[user_id] = current_intent
            return current_intent
        
        previous_ema = self.user_intents[user_id]
        new_ema = self.alpha * current_intent + (1 - self.alpha) * previous_ema
        self.user_intents[user_id] = new_ema
        
        return new_ema
    
    def can_switch_mode(self, user_id: str) -> bool:
        """Check if enough time has passed for mode switch (cooldown logic)"""
        if user_id not in self.last_mode_switch:
            return True
        
        elapsed = (datetime.now() - self.last_mode_switch[user_id]).total_seconds()
        return elapsed >= self.cooldown_seconds
    
    def record_mode_switch(self, user_id: str):
        """Record that a mode switch occurred"""
        self.last_mode_switch[user_id] = datetime.now()


class GuardrailFilter:
    """Light filtering based on quality/economy/balanced modes"""
    
    MODES = {
        'quality': {
            'min_similarity': 0.60,
            'description': 'Keep same semantic cluster, high similarity'
        },
        'economy': {
            'max_price_ratio': 1.15,
            'description': 'Same use + price cap within ±15%'
        },
        'balanced': {
            'min_similarity': 0.50,
            'max_price_ratio': 1.20,
            'description': 'Mix both quality and economy'
        }
    }
    
    @staticmethod
    def apply_filter(candidates: List[Dict], mode: str, original_item: Dict) -> List[Dict]:
        """Apply guardrail filtering based on mode"""
        
        if mode not in GuardrailFilter.MODES:
            return candidates
        
        mode_config = GuardrailFilter.MODES[mode]
        filtered = []
        
        for candidate in candidates:
            keep = True
            
            if mode == 'quality' or mode == 'balanced':
                min_sim = mode_config.get('min_similarity', 0)
                if candidate.get('semantic_sim', 0) < min_sim:
                    keep = False
            
            if mode == 'economy' or mode == 'balanced':
                max_ratio = mode_config.get('max_price_ratio', float('inf'))
                original_price = original_item.get('price', 0)
                candidate_price = candidate.get('price', 0)
                
                if original_price > 0:
                    price_ratio = candidate_price / original_price
                    if price_ratio > max_ratio:
                        keep = False
            
            if keep:
                filtered.append(candidate)
        
        return filtered


class LGBMReRanker:
    """LightGBM-based recommendation re-ranker"""
    
    def __init__(self, model_path='models/lgbm_ltr.txt', use_lgbm=True):
        self.model_path = model_path
        self.use_lgbm = use_lgbm
        self.model = None
        self.intent_tracker = IntentTracker(alpha=0.3, cooldown_seconds=45)
        self.feature_cols = [
            'cf_bpr_score', 'semantic_sim', 'price_saving', 'within_budget_flag',
            'size_ratio', 'category_match', 'popularity', 'recency',
            'diet_match_flag', 'quality_tags_score', 'same_semantic_id_flag',
            'distance_to_semantic_center', 'beta_u', 'budget_pressure',
            'intent_keep_quality_ema', 'premium_anchor', 'mission_type_id',
            'cart_value', 'cart_size', 'dow', 'hour'
        ]
        
        if self.use_lgbm:
            self._load_model()
    
    def _load_model(self):
        """Load LightGBM model from file"""
        if not os.path.exists(self.model_path):
            print(f"⚠ LightGBM model not found at {self.model_path}")
            print("  Run train_lgbm_ranker.py to train the model")
            print("  Falling back to non-LightGBM ranking")
            self.use_lgbm = False
            return
        
        try:
            self.model = lgb.Booster(model_file=self.model_path)
            print(f"✓ Loaded LightGBM model from {self.model_path}")
        except Exception as e:
            print(f"⚠ Failed to load LightGBM model: {e}")
            print("  Falling back to non-LightGBM ranking")
            self.use_lgbm = False
    
    def reload_model(self):
        """
        Reload the LightGBM model from disk without restarting the application.
        Used after model retraining to hot-swap the new model.
        """
        print(f"🔄 Reloading LightGBM model from {self.model_path}...")
        self.use_lgbm = True  # Re-enable LightGBM
        self._load_model()
        if self.use_lgbm and self.model is not None:
            print("✅ Model reloaded successfully!")
            return True
        else:
            print("❌ Model reload failed")
            return False
    
    def get_feature_importance(self) -> Dict[str, float]:
        """
        Get feature importance from trained LightGBM model.
        Returns dictionary of feature names and their importance scores.
        """
        if not self.use_lgbm or self.model is None:
            return {}
        
        try:
            # Get feature importance (gain-based)
            importance = self.model.feature_importance(importance_type='gain')
            
            # Create dictionary mapping feature names to importance
            feature_importance = {}
            for i, feature_name in enumerate(self.feature_cols):
                if i < len(importance):
                    feature_importance[feature_name] = float(importance[i])
            
            # Normalize to percentages
            total_importance = sum(feature_importance.values())
            if total_importance > 0:
                feature_importance = {
                    k: (v / total_importance) * 100 
                    for k, v in feature_importance.items()
                }
            
            # Sort by importance (descending)
            feature_importance = dict(sorted(
                feature_importance.items(), 
                key=lambda x: x[1], 
                reverse=True
            ))
            
            return feature_importance
            
        except Exception as e:
            print(f"⚠ Failed to extract feature importance: {e}")
            return {}
    
    def compute_behavioral_features(self, user_id: str, session_context: Dict) -> Dict:
        """Compute behavioral and contextual features"""
        
        cart_value = session_context.get('cart_value', 0)
        cart_size = session_context.get('cart_size', 0)
        budget = session_context.get('budget', 40.0)
        
        beta_u = session_context.get('beta_u', 0.5)
        
        budget_pressure = max(0, (cart_value - budget) / budget) if budget > 0 else 0
        
        current_intent = session_context.get('current_intent', 0.5)
        intent_ema = self.intent_tracker.update_intent(user_id, current_intent)
        
        premium_anchor = 1 if cart_value > 50 else 0
        
        mission_type_id = session_context.get('mission_type', 0)
        
        now = datetime.now()
        dow = now.weekday()
        hour = now.hour
        
        return {
            'beta_u': beta_u,
            'budget_pressure': budget_pressure,
            'intent_keep_quality_ema': intent_ema,
            'premium_anchor': premium_anchor,
            'mission_type_id': mission_type_id,
            'cart_value': cart_value,
            'cart_size': cart_size,
            'dow': dow,
            'hour': hour
        }
    
    def assemble_features(self, candidate: Dict, behavioral_feats: Dict) -> Dict:
        """Assemble all features for a single candidate - MUST match training feature keys"""
        
        features = {}
        
        # Candidate features (use exact keys from blended_recommendations)
        features['cf_bpr_score'] = candidate.get('cf_score', 0.5)
        features['semantic_sim'] = candidate.get('semantic_sim', 0.5)
        features['price_saving'] = candidate.get('price_saving', 0)
        # Respect candidate's within_budget_flag, fallback to price_saving logic only if missing
        features['within_budget_flag'] = candidate.get('within_budget_flag', 
                                                        1 if candidate.get('price_saving', 0) > 0 else 0)
        features['size_ratio'] = candidate.get('size_ratio', 1.0)
        features['category_match'] = candidate.get('category_match', 0)
        features['popularity'] = candidate.get('popularity', 0.5)
        features['recency'] = candidate.get('recency', 0.5)
        features['diet_match_flag'] = candidate.get('diet_match', 0)
        features['quality_tags_score'] = candidate.get('quality_tags_score', 0.5)
        features['same_semantic_id_flag'] = candidate.get('same_semantic_cluster', 0)
        features['distance_to_semantic_center'] = candidate.get('semantic_distance', 0.5)
        
        # Add behavioral features from session context
        features.update(behavioral_feats)
        
        # Fill in any missing features with zeros
        for col in self.feature_cols:
            if col not in features:
                features[col] = 0
        
        return features
    
    def re_rank(self, session_id: str, user_id: str, candidates: List[Dict],
                session_context: Dict, guardrail_mode: str = 'balanced') -> List[Dict]:
        """
        Re-rank candidates using LightGBM with guardrail filtering
        
        Args:
            session_id: Session identifier
            user_id: User identifier
            candidates: List of candidate items with features
            session_context: Session context (cart, budget, etc.)
            guardrail_mode: 'quality', 'economy', or 'balanced'
        
        Returns:
            Re-ranked list of candidates
        """
        
        if not candidates:
            return []
        
        behavioral_feats = self.compute_behavioral_features(user_id, session_context)
        
        original_item = session_context.get('original_item', {})
        filtered_candidates = GuardrailFilter.apply_filter(
            candidates, guardrail_mode, original_item
        )
        
        if not filtered_candidates:
            filtered_candidates = candidates
        
        if not self.use_lgbm or self.model is None:
            return sorted(
                filtered_candidates,
                key=lambda x: x.get('cf_score', 0) * 0.6 + x.get('semantic_sim', 0) * 0.4,
                reverse=True
            )
        
        feature_rows = []
        for candidate in filtered_candidates:
            feats = self.assemble_features(candidate, behavioral_feats)
            feature_row = [feats[col] for col in self.feature_cols]
            feature_rows.append(feature_row)
        
        X = np.array(feature_rows)
        
        try:
            scores = self.model.predict(X)
            
            for i, candidate in enumerate(filtered_candidates):
                candidate['ltr_score'] = float(scores[i])
            
            ranked = sorted(filtered_candidates, key=lambda x: x['ltr_score'], reverse=True)
            
            return ranked
            
        except Exception as e:
            print(f"⚠ LightGBM prediction failed: {e}")
            return sorted(
                filtered_candidates,
                key=lambda x: x.get('cf_score', 0) * 0.6 + x.get('semantic_sim', 0) * 0.4,
                reverse=True
            )


# Global instance
reranker = None

def get_reranker(use_lgbm=True):
    """Get or create global reranker instance"""
    global reranker
    if reranker is None:
        reranker = LGBMReRanker(use_lgbm=use_lgbm)
    return reranker
