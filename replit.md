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
- **LightGBM LambdaMART Re-Ranking** (Optional, production-ready):
  - **Behavior-Aware Re-Ranking**: LightGBM LambdaMART model for intelligent re-ranking based on user intent and session context.
  - **Feature Consistency**: Training features extracted from actual recommendation pipeline (real CF/semantic scores, product metadata).
  - **Intent Tracking**: EMA smoothing (α=0.3) with 45s cooldown logic to prevent mode thrashing.
  - **Guardrail Modes**: Quality (high similarity), Economy (price-focused), Balanced (mix of both).
  - **Graceful Fallback**: When LightGBM unavailable (system dependency libgomp.so.1 missing in Replit), falls back to standard 60/40 blending.
  - **Feature-Rich**: 21 features including CF scores, semantic similarity, price savings, quality tags, diet matching, behavioral context (beta_u, budget_pressure, intent, cart state, temporal).
  - **Files**: `lgbm_reranker.py` (re-ranker), `prepare_ltr_data.py` (data prep), `train_lgbm_ranker.py` (training), `LGBM_README.md` (documentation).

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