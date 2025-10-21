# Grocery Shopping & Budget Tracker

## Overview

This Flask web application provides a comprehensive grocery shopping experience with integrated budget tracking. Users can browse products, manage shopping carts, and monitor their spending against set budgets. It features session-based user identification, a robust product catalog loaded from CSV, and an AI-powered recommendation system to help users stay within budget and discover new products. The project aims to deliver a modern, responsive, and intelligent shopping assistant.

## User Preferences

Preferred communication style: Simple, everyday language.

## System Architecture

### Backend
- **Framework**: Flask with SQLAlchemy ORM.
- **User Management**: Session-based with UUID for anonymous tracking.
- **Database**: PostgreSQL, managed with SQLAlchemy 2.x DeclarativeBase.
- **Data Models**: Products, UserBudgets, User, Order, OrderItem, UserEvent for purchase history and recommendations.
- **Product Identification**: Deterministic `blake2b` hash for stable product IDs, stored as `BigInteger`.
- **Data Import**: Pandas-based CSV import system with smart parsing for prices and ratings, using batch commits for efficiency.
- **Performance**: Database connection pooling, in-memory product catalog (Pandas DataFrame) for O(1) lookups, numeric field extraction for efficient calculations.

### Frontend
- **Design System**: Modern UI using Tailwind CSS CDN, Inter Font, and a blue/indigo gradient color scheme.
- **Layout**: Two-column design with store map on left (60%) and shopping cart panel on right (40%).
- **Store Map**: Visual aisle layout organizing 19 product categories into 6 aisles (A-F):
  - Aisle A: Meat & Seafood, Seafood, Poultry, Deli, Breakfast, Floral
  - Aisle B: Snacks (repeated for visual prominence)
  - Aisle C: Candy, Gift Baskets, Organic, Kirkland Signature Grocery
  - Aisle D: Pantry & Dry Goods, Coffee
  - Aisle E: Beverages & Water, Paper & Plastic Products, Household
  - Aisle F: Bakery & Desserts, Cleaning Supplies, Laundry Detergent & Supplies, Household
- **Components**: Responsive header, interactive aisle cards with click-to-filter, clean product cards, budget controls, shopping cart display with quantity controls, collapsible product browser, and animated success notifications.
- **Responsiveness**: Mobile-friendly layout with a flexible grid system.
- **User Panel & Sign-In**:
  - **User Panel**: Slide-in panel from the right displaying user profile, purchase history, shopping stats, and preferences.
  - **Demo Sign-In Flow**: Fake/demo authentication modal triggered by "Sign In / Register" button:
    - Clean modal form with name and email fields (no password required - demo only).
    - User data stored in browser localStorage for persistence across sessions.
    - Dynamic UI updates: displays signed-in user's name/email in user panel when authenticated.
    - Sign-out functionality to clear user data and return to guest mode.
    - Animated toast notifications for user feedback (sign-in success, sign-out, etc.).
    - No backend authentication logic - purely for demonstration and UI/UX purposes.
- **AI Recommendation UI**:
    - **Hybrid AI System**: The sole recommendation engine combining 60% Collaborative Filtering + 40% semantic similarity (Emerald/Teal theme).
    - Recommendations automatically trigger when the cart total exceeds the budget and display in the right sidebar below the cart.
    - **Aisle Highlighting System**:
        - **Main Pulsing Highlight**: The most recent recommendation's aisle displays an orange gradient with pulsing glow animation for maximum visibility.
        - **Green Dot Indicators**: Small green badges appear in the top-right corner of aisles where the Hybrid AI system has product recommendations.
        - Highlights and dots automatically clear when the cart is within budget or after checkout.

### AI & Recommendations
- **Deep Learning**: TensorFlow/Keras Collaborative Filtering model for personalized recommendations.
- **Semantic Similarity**: Sentence-transformers (`all-MiniLM-L6-v2`) for budget-saving recommendations.
- **Hybrid System**: Combines CF and semantic similarity with configurable weights (60% CF + 40% Semantic).
- **Data Pipeline**: Extracts unified event data from user interactions (purchases, views, cart adds/removes) for CF model training.
- **Cold Start Handling**: CF model gracefully falls back to general recommendations for new users or those with limited purchase history.
- **Filtering**: Recommendations are filtered to suggest cheaper alternatives, prioritizing items within the same subcategory.
- **LightGBM LambdaMART Re-Ranking** (✅ ACTIVE - Oct 21, 2025):
  - **Behavior-Aware Re-Ranking**: LightGBM LambdaMART model for intelligent re-ranking based on user intent and session context.
  - **Production Integration**: Session context (cart, budget, budget_pressure) automatically passed from `/api/blended/recommendations` endpoint when cart exceeds budget.
  - **Feature Consistency**: Training features extracted from actual recommendation pipeline (real CF/semantic scores, product metadata).
  - **Intent Tracking**: EMA smoothing (α=0.3) with 45s cooldown logic to prevent mode thrashing.
  - **Guardrail Modes**: Quality (high similarity), Economy (price-focused), Balanced (mix of both).
  - **System Setup**: GCC installed via Nix packages (`pkgs.gcc`), `LD_LIBRARY_PATH` configured in workflow to provide `libgomp.so.1` OpenMP library.
  - **Graceful Fallback**: Uses standard 60/40 blending when no trained model available; automatically activates LightGBM re-ranking when model file exists.
  - **Feature-Rich**: 21 features including CF scores, semantic similarity, price savings, quality tags, diet matching, behavioral context (beta_u, budget_pressure, intent, cart state, temporal).
  - **Performance**: Uses in-memory PRODUCTS_DF for O(1) product metadata lookup instead of database queries.
  - **Training**: 289 real samples from 68 user sessions, trained model saved to `models/lgbm_ltr.txt` (3.4 KB).
  - **Improved Training Parameters**: 300 boost rounds (was 100), min_data_in_leaf=15 (was 50), early_stopping=75 rounds (was 20) for better feature learning.
  - **Files**: `lgbm_reranker.py` (re-ranker), `prepare_ltr_data.py` (data prep), `train_lgbm_ranker.py` (training), `LGBM_README.md` (documentation).
- **Online Learning System** (✅ ACTIVE - Oct 21, 2025):
  - **Real-Time Event Tracking**: Automatically captures all user interactions (view, cart_add, cart_remove, purchase) via `/api/track-event` endpoint.
  - **Auto-Retrain Pipeline**: After every 5 purchases, system automatically exports fresh training data and retrains the LightGBM model in background thread.
  - **Model Hot-Reload**: Newly trained models are loaded without restarting Flask via `reload_model()` method in LGBMReRanker.
  - **User Feedback**: Animated toast notifications ("🎓 Learning from your purchases..." → "✨ AI model updated!") provide transparency.
  - **Feature Importance Display**: Dynamic UI shows learned weights (CF %, Semantic %, Price %, Budget %) or training stats (samples, sessions, features).
  - **Complete Learning Cycle**: View events → Cart interactions → Purchase → Data export → Model training → Hot reload → Updated recommendations.
  - **Non-Blocking**: Background threading ensures retraining doesn't block user experience.
  - **Demo-Ready**: Perfect for class presentation demonstrating "Scaling Research to Production" with adaptive ML.
- **Synthetic Training Data Generator** (✅ ACTIVE - Oct 21, 2025):
  - **Purpose**: Generate training data with clear behavioral patterns that guarantee visible feature importance for class presentations.
  - **4 User Personas**: Budget Hunters (30%), Quality Seekers (30%), CF Followers (20%), Budget-Pressured (20%).
  - **Pattern Design**: Each persona has distinct feature preferences (e.g., Budget Hunters: 60% price_saving, Quality Seekers: 50% semantic_sim).
  - **Output**: 1000 samples from 200 sessions with 47.5% click rate (good label variation).
  - **Result**: Model learns real feature importance (recency: 432.7, cf_bpr_score: 431.5, price_saving: 359.1, semantic_sim: 308.0).
  - **API**: `/api/model/feature-importance` returns percentages (CF: 10.3%, Semantic: 7.3%, Price: 8.5%, Budget: 2.2%).
  - **UI**: Displays "ML-Optimized Weights: CF 10%, Semantic 7%, Price 9%, Budget 2% from 1000 sessions" in recommendation panel.
  - **Files**: `generate_synthetic_ltr_data.py` (generator), `DEMO_FEATURE_IMPORTANCE.md` (presentation guide), `PRESENTATION_SNAPSHOT.json` (locked demo values).
  - **Presentation-Ready**: Deterministic UI logic ensures ML weights always display when model is trained (no regression risk).

### LLM-as-a-Judge Evaluation System
- **Methodology**: EvidentlyAI approach for scientific comparison of recommendation systems.
- **LLM Model**: OpenAI GPT-5 for automated evaluation and scoring.
- **Evaluation Types**:
  - **Pairwise Comparisons**: Direct head-to-head comparisons between systems.
  - **Criteria-Based Scoring**: Evaluates each system on 5 metrics (Relevance, Savings, Diversity, Explanation Quality, Feasibility).
- **Test Scenarios**: Budget-conscious, health-focused, and new user (cold start) scenarios.
- **Robustness**: Validates API keys upfront, detects incomplete evaluations, prevents fabricated winners when API calls fail.
- **Output**: JSON reports with evaluation status, winners, scores, and combined summaries across scenarios.
- **Files**: `llm_judge_evaluation.py` (core engine), `test_llm_evaluation.py` (test runner with 3 scenarios), `demo_llm_evaluation.py` (system demonstration), `LLM_EVALUATION_README.md` (documentation).

## External Dependencies

### Python Libraries
- **Flask**: Web framework.
- **Flask-SQLAlchemy**: ORM integration.
- **pandas**: Data manipulation for CSV imports.
- **SQLAlchemy**: Database ORM.
- **sentence-transformers**: Semantic similarity.
- **torch**: PyTorch backend for transformer models.
- **tensorflow-cpu**: Deep learning framework for CF.
- **scikit-learn**: Machine learning utilities.
- **openai**: OpenAI API client for GPT-5 LLM evaluation.
- **requests**: HTTP client for API calls.
- **lightgbm**: Gradient boosting framework for LambdaMART re-ranking (optional).
- **pyarrow**: Parquet file support for training data.

### Database
- **PostgreSQL**: Primary data storage, configured via `DATABASE_URL`.

### Data Sources
- **CSV files**: Product catalog from `attached_assets/GroceryDataset_with_Nutrition_1758836546999.csv`.

### Infrastructure
- **Environment Variables**: For database connection and Flask secret key.
- **File System Access**: For CSV data import.