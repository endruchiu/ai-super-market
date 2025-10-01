# Grocery Shopping & Budget Tracker

## Overview

This is a Flask web application for grocery shopping with integrated budget tracking functionality. The system allows users to browse grocery products, manage shopping carts, and track their spending against set budgets. The application uses session-based user identification and imports product data from CSV files for a comprehensive grocery catalog.

## User Preferences

Preferred communication style: Simple, everyday language.

## System Architecture

### Backend Framework
- **Flask** as the primary web framework with SQLAlchemy ORM for database operations
- **Session-based user management** using Flask sessions with UUID generation for anonymous user tracking
- **Modular model initialization** pattern where database models are dynamically initialized with the database instance

### Database Design
- **SQLAlchemy ORM** with DeclarativeBase for modern SQLAlchemy 2.x compatibility
- **Product model** with both text and parsed numeric fields for prices and ratings to maintain data integrity while enabling calculations
- **Shopping cart functionality** with session-based cart management
- **Budget tracking system** with UserBudget model for spending limits and monitoring
- **Purchase history tracking** with User, Order, OrderItem, and UserEvent models for AI-powered recommendations
- **Deterministic product IDs** using blake2b hash (Title|SubCategory) for stability across restarts with BigInteger support
- **Batch processing** for efficient data imports with commit batching every 100 records

### Data Processing
- **CSV import system** using pandas for bulk product data loading
- **Smart parsing utilities** for extracting numeric values from text fields (prices, ratings, review counts)
- **Regular expressions** for robust text parsing of currency amounts and rating formats

### Application Structure
- **Factory pattern** for model initialization allowing for flexible database configuration
- **Global model registration** making models available across the application after initialization
- **Environment-based configuration** for database URLs and secret keys
- **In-memory product catalog** using pandas DataFrame (PRODUCTS_DF) for O(1) lookups without database overhead
- **JavaScript-safe IDs** returned as strings in JSON API to avoid precision loss beyond 53 bits

### Performance Optimizations
- **Database connection pooling** with pool recycling and pre-ping health checks
- **Batch commits** during data import operations to improve performance
- **Numeric field extraction** for efficient querying and calculations
- **In-memory product storage** eliminates database queries for product lookups during browsing and checkout

## Frontend Design

### Modern UI with Tailwind CSS
- **Tailwind CSS CDN** - Utility-first CSS framework for modern, responsive design
- **Inter Font** - Professional Google Font for enhanced typography
- **Gradient Backgrounds** - Blue/indigo color scheme for visual appeal
- **Component Design**:
  - Responsive header with branded shopping cart icon
  - Clean white cards with shadows and borders
  - Smooth hover effects and transitions
  - Color-coded badges (blue for categories, green for savings)
  - Icon-enhanced buttons and alerts
  - Animated success notifications with fade effects

### UI Features
- **Budget Controls** - Styled input fields with dollar sign prefix and category dropdown
- **Product Table** - Hover effects, category pills, and gradient add buttons
- **Shopping Cart** - Item cards with quantity controls and budget warning alerts
- **Checkout Button** - One-click checkout with success notifications and cart clearing
- **AI Recommendations** - Three recommendation systems with auto-load on page load:
  - **Budget-Saving Recommendations** (Blue/Indigo) - Semantic similarity for budget-conscious replacements
  - **Personalized Recommendations** (Purple/Pink) - CF model based on purchase history
  - **Hybrid AI Recommendations** (Emerald/Teal) - 60% CF + 40% semantic similarity blend
- **Responsive Design** - Mobile-friendly layout with flexible grid system

## External Dependencies

### Python Libraries
- **Flask** - Web framework for routing and request handling
- **Flask-SQLAlchemy** - Database ORM integration
- **pandas** - CSV data processing and manipulation for product imports
- **SQLAlchemy** - Database abstraction and ORM functionality
- **sentence-transformers** - AI model for semantic product similarity (all-MiniLM-L6-v2)
- **torch** - PyTorch backend for transformer models
- **tensorflow-cpu** - Deep learning framework for collaborative filtering model
- **scikit-learn** - Machine learning utilities for data splitting and preprocessing

### Database
- **PostgreSQL** (via DATABASE_URL environment variable) - Primary data storage for products, shopping carts, and user budgets

### Data Sources
- **CSV files** - Product catalog data import from `attached_assets/GroceryDataset_with_Nutrition_1758836546999.csv` (nutrition-enhanced dataset with 1,757 products)
- **Nutritional Information** - Complete nutrition facts including calories, fat, carbs, sugar, protein, and sodium content for all products

### Infrastructure Requirements
- **Environment variables** for database connection and Flask secret key configuration
- **File system access** for CSV data import operations

## Recent Changes (October 1, 2025)

### Deep Learning Recommendation System (CF Model)
- **Data Extraction Pipeline** (`recommendation_engine.py`):
  - Extracts unified event dataset from Order/OrderItem/UserEvent tables
  - Format: event_time, event_type, product_id, user_id, user_session (matches e-commerce dataset structure)
  - Event type normalization for consistent aggregation
  - Aggregates user-product behavior with implicit feedback scoring
  - Formula: 1.0*views + 2.0*cart_adds - 0.5*cart_removes + 3.0*purchases
  - Creates dense ID mappings for efficient embedding lookup
  - Persists as Parquet files with pickle mappings

- **Keras Collaborative Filtering Model** (`train_cf_model.py`):
  - Architecture: User embedding (dim=32) × Product embedding (dim=32) → Dot product → Sigmoid
  - Training: Binary cross-entropy with sample weighting and negative sampling (5:1 ratio)
  - Regularization: L2 (1e-6), early stopping, learning rate reduction
  - Evaluation: Accuracy, AUC metrics on val/test splits
  - Saves model weights, embeddings, and artifacts for fast inference
  
- **Dependencies**: Installed tensorflow-cpu, scikit-learn for deep learning pipeline

- **Evaluation Metrics** (`evaluate_recommendations.py`):
  - Precision@K: Fraction of top-K recommendations that are relevant
  - Recall@K: Fraction of relevant items in top-K recommendations
  - MAP@K (Mean Average Precision): Accounts for rank position of relevant items
  - Evaluates at K=5,10,20,50 with formatted table output
  - Tested and verified with example data

- **CF Recommendation API** (`/api/cf/recommendations`):
  - Loads trained model weights and embeddings for inference
  - Generates personalized recommendations based on user's purchase history
  - User profile: Average of product embeddings from past purchases
  - Scores all products via user-product embedding similarity
  - Returns top-K recommendations with product details
  - Gracefully handles "model not trained" state with helpful error messages

- **Blended Recommendation API** (`/api/blended/recommendations`):
  - Combines CF (60%) + Semantic similarity (40%) for hybrid recommendations
  - CF component: Uses trained model embeddings for personalized scoring
  - Semantic component: Cosine similarity between user profile and product embeddings
  - Properly normalized vectors ensure consistent [0,1] score range
  - Weighted combination: `0.6 * cf_score + 0.4 * semantic_score`
  - Returns top-K blended recommendations sorted by combined score

- **Critical Product ID Fix**:
  - Unified product ID generation across all modules (blake2b hash)
  - Fixed semantic_budget.py to use same hash as main.py and CF training
  - Ensures consistent product identification for checkout, recommendations, and CF training
  - Added hashlib import and cleared cached semantic index to regenerate with correct IDs

- **Frontend Integration** (Task 8 completed):
  - Added two new recommendation sections with auto-load on page load
  - **Personalized Recommendations** (Purple/Pink theme) - Pure CF model recommendations
  - **Hybrid AI Recommendations** (Emerald/Teal theme) - 60% CF + 40% semantic blend
  - JavaScript functions: `getCFRecommendations()` and `getBlendedRecommendations()`
  - Auto-load via DOMContentLoaded handler with 500ms delay
  - Manual refresh buttons for each section
  - Graceful "model not trained" messaging with instructions
  - Product cards display: title, category, size, nutrition, price, score
  - Functional "Add to Cart" buttons for all recommended products
  - All UI text in English as required

- **Next Steps**:
  - Train model once sufficient purchase history accumulates (need real user data)
  - Monitor recommendation quality and adjust weights if needed

### Checkout & Purchase History Implementation
- **Checkout endpoint** (`/api/checkout`) with comprehensive server-side validation:
  - Authoritative price lookups from PRODUCTS_DF (never trust client prices)
  - Quantity validation and clamping (1-1000 per item)
  - Empty cart rejection (400 error)
  - Unknown product rejection (400 error)
  - NaN price handling (defaults to 0.0)
  - Transaction management with commit/rollback
  - Generic client-safe error messages

- **Purchase history persistence**:
  - Creates/retrieves User records by session_id
  - Creates Order with validated total_amount and item_count
  - Creates OrderItem with product snapshot (title, subcat, price, quantity)
  - Creates UserEvent (event_type='purchase') for behavior tracking
  - All within single database transaction for consistency

- **Product ID system**:
  - Deterministic blake2b hash ensures stable IDs across server restarts
  - IDs returned as strings in JSON API to avoid JavaScript 53-bit precision limit
  - Server-side parsing converts string IDs back to int64 for PRODUCTS_DF lookups
  - BigInteger columns in database support 63-bit IDs without overflow
  - No foreign key constraints since products stored in-memory only

- **Frontend integration**:
  - Added "Checkout Now" button to cart UI
  - Success notification with auto-dismiss animation
  - Cart clearing after successful checkout
  - Error handling with user-friendly messages