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
- **Components**: Responsive header, clean product cards, budget controls, shopping cart display with quantity controls, and animated success notifications.
- **Responsiveness**: Mobile-friendly layout with a flexible grid system.
- **AI Recommendation UI**:
    - **Budget-Saving**: Semantic similarity-based (Blue/Indigo theme).
    - **Personalized**: Collaborative Filtering (CF) based on purchase history (Purple/Pink theme).
    - **Hybrid AI**: 60% CF + 40% semantic similarity blend (Emerald/Teal theme).
    - Recommendations automatically trigger when the cart total exceeds the budget.

### AI & Recommendations
- **Deep Learning**: TensorFlow/Keras Collaborative Filtering model for personalized recommendations.
- **Semantic Similarity**: Sentence-transformers (`all-MiniLM-L6-v2`) for budget-saving recommendations.
- **Hybrid System**: Combines CF and semantic similarity with configurable weights (60% CF + 40% Semantic).
- **Data Pipeline**: Extracts unified event data from user interactions (purchases, views, cart adds/removes) for CF model training.
- **Cold Start Handling**: CF model gracefully falls back to general recommendations for new users or those with limited purchase history.
- **Filtering**: Recommendations are filtered to suggest cheaper alternatives, prioritizing items within the same subcategory.

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
- **tensorflow-cpu**: Deep learning framework for CF.
- **scikit-learn**: Machine learning utilities.
- **openai**: OpenAI API client for GPT-5 LLM evaluation.
- **requests**: HTTP client for API calls.

### Database
- **PostgreSQL**: Primary data storage, configured via `DATABASE_URL`.

### Data Sources
- **CSV files**: Product catalog from `attached_assets/GroceryDataset_with_Nutrition_1758836546999.csv`.

### Infrastructure
- **Environment Variables**: For database connection and Flask secret key.
- **File System Access**: For CSV data import.