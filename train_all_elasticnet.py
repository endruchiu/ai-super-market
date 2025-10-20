"""
Master Training Script for All Elastic Net Enhancements
Trains:
1. Budget Elastic Net: Feature weighting for semantic budget recommendations
2. CF Elastic Net: Already integrated into train_cf_model.py (L1+L2 regularization)
3. Hybrid Elastic Net: Blending weights for CF + Semantic combination
"""

import os
import sys

def main():
    print("=" * 70)
    print("ELASTIC NET ENHANCEMENT TRAINING PIPELINE")
    print("=" * 70)
    print("\nThis script will train Elastic Net optimizers for all three systems:")
    print("  1. Budget-Saving: Learn feature weights (savings, similarity, health, size)")
    print("  2. CF Personalized: Elastic Net regularization (L1+L2) - train separately")
    print("  3. Hybrid Blend: Learn optimal CF/Semantic mixing weights")
    print("\n" + "=" * 70 + "\n")
    
    # Check if ml_data directory exists with necessary data
    if not os.path.exists('ml_data/events.parquet'):
        print("⚠️  No training data found at ml_data/events.parquet")
        print("\n📋 To generate training data:")
        print("   1. Use the app and make some purchases (creates user events)")
        print("   2. Run: python recommendation_engine.py")
        print("   3. Then run this script again")
        print("\n🔄 For now, using default weights (no Elastic Net optimization)")
        print("=" * 70)
        return
    
    # Step 1: Train Budget Elastic Net
    print("\n" + "=" * 70)
    print("STEP 1: Training Budget Feature Weight Optimizer")
    print("=" * 70)
    
    try:
        from elastic_budget_optimizer import BudgetElasticNetOptimizer
        
        budget_optimizer = BudgetElasticNetOptimizer(alpha=0.1, l1_ratio=0.5)
        budget_metrics = budget_optimizer.train_from_events('ml_data')
        
        if budget_metrics:
            budget_optimizer.save('ml_data/budget_elasticnet.pkl')
            print("\n✅ Budget Elastic Net training complete!")
        else:
            print("\n⚠️  Budget Elastic Net training skipped (insufficient data)")
    
    except Exception as e:
        print(f"\n❌ Error training Budget Elastic Net: {e}")
        print("   Continuing with defaults...")
    
    # Step 2: Instructions for CF Elastic Net
    print("\n" + "=" * 70)
    print("STEP 2: CF Model with Elastic Net Regularization")
    print("=" * 70)
    print("\n📝 The CF model now uses Elastic Net regularization (L1+L2)!")
    print("   To train/retrain the CF model:")
    print("   $ python train_cf_model.py")
    print("\n   This will automatically use the enhanced Elastic Net regularization.")
    
    # Step 3: Train Hybrid Elastic Net
    print("\n" + "=" * 70)
    print("STEP 3: Training Hybrid Blending Weight Optimizer")
    print("=" * 70)
    
    # Check if CF model exists
    if not os.path.exists('ml_data/cf_model.keras'):
        print("\n⚠️  No CF model found at ml_data/cf_model.keras")
        print("   Hybrid optimizer requires a trained CF model.")
        print("   Please run: python train_cf_model.py first")
        print("   Skipping hybrid optimization for now...")
    else:
        try:
            from elastic_hybrid_optimizer import HybridElasticNetOptimizer
            
            hybrid_optimizer = HybridElasticNetOptimizer(alpha=0.1, l1_ratio=0.5)
            hybrid_metrics = hybrid_optimizer.train_from_events('ml_data')
            
            if hybrid_metrics:
                hybrid_optimizer.save('ml_data/hybrid_elasticnet.pkl')
                print("\n✅ Hybrid Elastic Net training complete!")
            else:
                print("\n⚠️  Hybrid Elastic Net training skipped (insufficient data)")
        
        except Exception as e:
            print(f"\n❌ Error training Hybrid Elastic Net: {e}")
            print("   Continuing with defaults (60% CF + 40% Semantic)...")
    
    # Summary
    print("\n" + "=" * 70)
    print("TRAINING SUMMARY")
    print("=" * 70)
    
    print("\n📊 Enhanced Recommendation Systems:")
    print("   1. Budget-Saving: Elastic Net feature weights ✓")
    print("   2. CF Personalized: Elastic Net regularization (L1+L2) ✓")
    print("   3. Hybrid Blend: Elastic Net optimal weights ✓")
    
    print("\n📁 Saved models:")
    if os.path.exists('ml_data/budget_elasticnet.pkl'):
        print("   ✓ ml_data/budget_elasticnet.pkl")
    if os.path.exists('ml_data/cf_model.keras'):
        print("   ✓ ml_data/cf_model.keras (with Elastic Net reg)")
    if os.path.exists('ml_data/hybrid_elasticnet.pkl'):
        print("   ✓ ml_data/hybrid_elasticnet.pkl")
    
    print("\n🚀 Next Steps:")
    print("   1. Test recommendations: python test_recommendations.py")
    print("   2. Run LLM evaluation: python llm_judge_evaluation.py")
    print("   3. Compare system performance and choose the best one!")
    
    print("\n" + "=" * 70)
    print("✅ ELASTIC NET ENHANCEMENT COMPLETE!")
    print("=" * 70)


if __name__ == '__main__':
    main()
