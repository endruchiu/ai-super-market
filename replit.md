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
- **Supermarket Interface**: Split-screen layout with interactive store map (60% left) and shopping cart/recommendations (40% right).
- **Interactive Store Map**: SVG-based visualization showing 6 aisles (A-F) with labeled shelves:
    - Aisle A: Fresh Produce & Bakery
    - Aisle B: Meat, Seafood & Deli
    - Aisle C: Dairy & Frozen
    - Aisle D: Pantry & Snacks
    - Aisle E: Beverages & Drinks
    - Aisle F: Household & Paper
- **Interactive Shelf Browsing**: Users can click on any shelf to explore products in that category:
    - Displays 3-4 mock products per shelf with name, price, and "Add to Cart" button
    - Purple/indigo themed panel appears on the right side
    - Highlights the selected shelf on the map
    - Simulates the in-store experience of browsing products on a shelf
    - Products can be added directly to cart from the shelf view
- **Visual Navigation**: When recommendations are applied, the system highlights the target shelf and displays an animated route from entrance to product location.
- **Components**: Responsive header, clean product cards, budget controls, shopping cart display with quantity controls, shelf product browser, and animated success notifications.
- **Responsiveness**: Mobile-friendly layout with a flexible grid system.
- **AI Recommendation UI**:
    - **Budget-Saving**: Semantic similarity-based (Blue/Indigo theme).
    - **Personalized**: Collaborative Filtering (CF) based on purchase history (Purple/Pink theme).
    - **Hybrid AI**: 60% CF + 40% semantic similarity blend (Emerald/Teal theme).
    - Recommendations automatically trigger when the cart total exceeds the budget.

### AI & Recommendations
- **Deep Learning**: TensorFlow/Keras Collaborative Filtering model for personalized recommendations.
- **Semantic Similarity**: Sentence-transformers (`all-MiniLM-L6-v2`) for budget-saving recommendations.
- **Hybrid System**: Combines CF and semantic similarity with Elastic Net-optimized weights (default 60% CF + 40% Semantic, data-driven when trained).
- **Data Pipeline**: Extracts unified event data from user interactions (purchases, views, cart adds/removes) for CF model training.
- **Cold Start Handling**: CF model gracefully falls back to general recommendations for new users or those with limited purchase history.
- **Filtering**: Recommendations are filtered to suggest cheaper alternatives, prioritizing items within the same subcategory.
- **Dynamic Focus**: All three recommendation systems (Budget-Saving, CF, Hybrid) focus on the most recently added cart item when over budget, providing dynamic recommendations that adjust automatically as users add items.
- **Strict Category Matching**: CF and Hybrid systems enforce exact same-subcategory matching for budget replacements (e.g., protein bars → only other protein bars, NOT beef jerky).
- **Dual Recommendation Structure**:
  - **"suggestions"**: Same-category replacements only (up to 3 items) for budget-conscious shoppers
  - **"complementary_recommendations"**: Cross-category suggestions (up to 3 items) for discovery and exploration, labeled as "You might also like"
- **No Cross-Category Fallback**: Removed "related category" fallback logic to prevent confusing cross-category contamination in replacement suggestions.

### Elastic Net Enhancements
- **Budget-Saving System**: Uses ElasticNet (L1+L2 regularization) to learn optimal feature weights for savings, semantic similarity, health improvement, and size matching from user purchase behavior.
  - Features: savings_score, similarity_score, health_score, size_ratio
  - Replaces fixed lambda=0.6 with data-driven weights
  - Module: `elastic_budget_optimizer.py`
  - Integration: `semantic_budget.py` calls `_get_elastic_optimizer()` for learned weights with graceful fallback to defaults
- **CF Personalized System**: Enhanced neural network with Elastic Net regularization (L1+L2) on embedding layers.
  - L1 penalty: Feature selection and sparsity
  - L2 penalty: Weight decay to prevent overfitting
  - Modified: `train_cf_model.py` now uses `l1_l2()` regularizer instead of just `l2()`
  - Both user and product embeddings benefit from Elastic Net regularization
- **Hybrid System**: Uses ElasticNet to learn optimal blending weights for CF vs Semantic scores from user behavior.
  - Features: cf_score, semantic_score, interaction term
  - Replaces fixed 60/40 split with data-driven weights
  - Module: `elastic_hybrid_optimizer.py`
  - Integration: `blended_recommendations.py` calls `_get_hybrid_elastic_optimizer()` with logging and fallback
- **Training Pipeline**: `train_all_elasticnet.py` orchestrates training of all three optimizers with error handling and graceful degradation.
- **Production Ready**: All systems fall back to sensible defaults when no trained Elastic Net models are available, ensuring zero-downtime deployment.

### Advanced Ranking & Exploration Techniques (Research-Grade Enhancements)

#### Bayesian Personalized Ranking (BPR)
- **Algorithm**: Pairwise ranking optimization for implicit feedback scenarios (SIGIR 2009 algorithm)
- **Advantage**: Optimizes relative item order instead of absolute scores, dramatically improving Top-N recommendation quality
- **Implementation**: Triplet-based training (user, positive_item, negative_item) with BPR loss: `-log(sigmoid(score_pos - score_neg))`
- **Regularization**: Enhanced with Elastic Net (L1+L2) on embeddings for sparsity and generalization
- **Architecture**: 32-dimensional user/product embeddings with dot-product interaction
- **Training**: 
  - Module: `train_cf_bpr.py`
  - Triplet generation with negative sampling (5 negatives per positive)
  - Batch size: 2048, Learning rate: 0.001
  - Early stopping and model checkpointing
- **Files**: `train_cf_bpr.py`, `ml_data/bpr_model.keras`, `ml_data/bpr_embeddings.npz`
- **Research Foundation**: Based on Rendle et al. "BPR: Bayesian Personalized Ranking from Implicit Feedback" (UAI 2009)

#### Multi-Armed Bandits for Exploration-Exploitation
- **Algorithm**: Epsilon-greedy strategy for balancing exploration vs exploitation in recommendations
- **Purpose**: Prevents filter bubbles by discovering new products while showing known good items
- **Mechanism**:
  - **Exploration (ε)**: With probability ε (default 10%), inject random products to discover user preferences
  - **Exploitation (1-ε)**: With probability 1-ε, show high-CTR (click-through rate) products
  - **Adaptive Decay**: Epsilon decays over time (0.999 decay rate) to gradually shift from exploration to exploitation
  - **Lower Bound**: Minimum epsilon of 1% ensures continuous discovery
- **Metrics Tracked**:
  - **Impressions**: How many times each product was shown
  - **Clicks**: How many times each product was clicked/added to cart
  - **CTR**: Click-through rate with Laplace smoothing (clicks + 0.1) / (impressions + 1.0)
- **Integration**: Applies to all 3 recommendation systems (Budget-Saving, CF, Hybrid)
- **State Management**: Persistent storage in `ml_data/bandit_state.pkl` with automatic save/load
- **Module**: `bandits_exploration.py`
- **Research Foundation**: Classic reinforcement learning exploration-exploitation trade-off from multi-armed bandit literature

#### GPU-Accelerated Training
- **Framework**: TensorFlow 2.20.0 with GPU support enabled
- **Hardware**: Utilizes CUDA-compatible GPUs when available, gracefully falls back to CPU
- **Speedup**: 5-10x faster training on GPUs for neural embedding models
- **Memory Optimization**: Efficient batch processing (2048 samples/batch) to maximize GPU utilization
- **Mixed Precision**: Supports TF mixed precision for further speedup on modern GPUs (Tensor Cores)
- **Training Pipeline**: All models (CF, BPR, Elastic Net optimizers) benefit from GPU acceleration

### LLM-as-a-Judge Evaluation System
- **Methodology**: EvidentlyAI approach for scientific comparison of recommendation systems.
- **LLM Model**: OpenAI GPT-5 for automated evaluation and scoring.
- **Evaluation Types**:
  - **Pairwise Comparisons**: Direct head-to-head comparisons between systems.
  - **Criteria-Based Scoring**: Evaluates each system on 5 metrics (Relevance, Savings, Diversity, Explanation Quality, Feasibility).
- **Test Scenarios**: Budget-conscious, health-focused, and new user (cold start) scenarios.
- **Robustness**: Validates API keys upfront, detects incomplete evaluations, prevents fabricated winners when API calls fail.
- **Output**: JSON reports with evaluation status, winners, scores, and combined summaries across scenarios.
- **Files**: `llm_judge_evaluation.py`, `test_llm_evaluation.py`, `LLM_EVALUATION_README.md`.

## External Dependencies

### Python Libraries
- **Flask**: Web framework.
- **Flask-SQLAlchemy**: ORM integration.
- **pandas**: Data manipulation for CSV imports.
- **SQLAlchemy**: Database ORM.
- **sentence-transformers**: Semantic similarity.
- **torch**: PyTorch backend for transformer models.
- **tensorflow**: Deep learning framework for CF with GPU acceleration support.
- **scikit-learn**: Machine learning utilities (Elastic Net, evaluation metrics).
- **openai**: OpenAI API client for GPT-5 LLM evaluation.
- **requests**: HTTP client for API calls.

### Database
- **PostgreSQL**: Primary data storage, configured via `DATABASE_URL`.

### Data Sources
- **CSV files**: Product catalog from `attached_assets/GroceryDataset_with_Nutrition_1758836546999.csv`.

### Store Layout System
- **Module**: `store_layout.py` - Manages virtual store layout and product locations.
- **API Endpoints**:
  - `/api/store/layout`: Returns complete store structure with aisles and shelves.
  - `/api/store/location`: Maps product subcategories to shelf coordinates.
  - `/api/store/route`: Calculates Manhattan-style routes between store locations.
- **Shelf Mapping**: Products are mapped to shelves based on actual CSV subcategories:
  - Aisle F1: Cleaning Supplies
  - Aisle F2: Paper & Plastic Products
  - Aisle F3: Laundry Detergent & Supplies
  - Aisle F4-F6: Household (Items, Storage, Misc)
- **Category Accuracy**: Shelf names now match actual product subcategories in the CSV data to prevent recommendation confusion.
- **Route Visualization**: L-shaped pathfinding from entrance to target shelf with animated SVG paths and pulsing destination markers.

### Infrastructure
- **Environment Variables**: For database connection and Flask secret key.
- **File System Access**: For CSV data import.