# Grocery Shopping & Budget Tracker

## Overview

This Flask web application offers a complete grocery shopping experience with integrated budget tracking. It allows users to browse products, manage their shopping carts, and monitor spending against defined budgets. Key features include session-based user identification, a product catalog loaded from CSV, and an AI-powered recommendation system designed to assist users in adhering to their budget and discovering new products. The project's vision is to provide a modern, responsive, and intelligent shopping assistant.

## User Preferences

Preferred communication style: Simple, everyday language.

## System Architecture

### Backend
- **Framework**: Flask with SQLAlchemy ORM.
- **User Management**: Simplified name+email authentication for demo purposes (no password required). Session-based with email as session identifier. Creates or updates user account automatically on sign-in.
- **Database**: PostgreSQL, managed with SQLAlchemy 2.x DeclarativeBase.
- **Data Models**: Products, UserBudgets, User, Order, OrderItem, UserEvent for comprehensive tracking.
- **Product Identification**: Deterministic `blake2b` hash for stable product IDs.
- **Data Import**: Pandas-based CSV import system with batch commits.
- **Performance**: Database connection pooling, in-memory product catalog for efficient lookups.

### Frontend
- **Design System**: Modern UI using Tailwind CSS CDN and Inter Font, with a blue/indigo gradient color scheme.
- **Layout**: Two-column design (store map 60%, shopping cart 40%).
- **Store Map**: Visual aisle layout categorizing products into 6 aisles (A-F).
- **Components**: Responsive header, interactive aisle cards, product cards, budget controls, shopping cart, collapsible product browser, animated notifications.
- **Responsiveness**: Mobile-friendly layout.
- **User Panel & Sign-In**: Slide-in panel for user profile, history, and preferences. Simplified sign-in form (name + email only, no password) with localStorage for persistence. Designed for easy demo access.
- **AI Recommendation UI**: Recommendations trigger when the cart exceeds budget. Features an aisle highlighting system with pulsing orange gradient for the most recent recommendation and green dots for other recommended aisles.

### AI & Recommendations
- **Hybrid AI System**: Combines 60% Collaborative Filtering (TensorFlow/Keras) and 40% semantic similarity (Sentence-transformers) for personalized and budget-saving recommendations.
- **Data Pipeline**: Extracts unified event data from user interactions for CF model training.
- **Cold Start Handling**: Graceful fallback to general recommendations for new users.
- **Filtering**: Suggestions prioritize cheaper alternatives within the same subcategory.
- **ISRec Intent Detection System**: Analyzes recent user actions to detect "Quality" or "Economy" intent, influencing recommendations. Uses EMA smoothing for intent tracking.
- **LightGBM LambdaMART Re-Ranking**: A behavior-aware re-ranking model using 21 features (including intent, budget pressure, CF/semantic scores) to optimize recommendations.
- **Online Learning System**: Captures user interactions in real-time. Automatically retrains the LightGBM model in a background thread after every 5 purchases, with hot-reloading of new models.
- **Synthetic Training Data Generator**: Creates tailored training data with distinct behavioral patterns for demonstration purposes, ensuring visible feature importance in the UI.
- **Replenishment Recommendation System**: A comprehensive, budget-agnostic system predicting when users need to restock ALL products based on purchase patterns. Features:
  - **Dual-Mode Predictions**: (1) Personalized cycles for 2+ purchases using median intervals, (2) First-purchase predictions using CF-based similar user analysis (60%) blended with product metadata (40%)
  - **CF Validation**: Top-10 most similar users (via embedding cosine similarity) are validated to ensure they actually purchased the product 2+ times before contributing interval data
  - **Urgency-Based Ranking**: Combines days overdue, purchase frequency, category importance, and CF confidence to rank top 10 most critical items
  - **Time Buckets**: Due Now (0-3 days), Due Soon (4-7 days), Upcoming (7+ days)
  - **Conversational UI**: Natural language messages like "You probably ran out 2 days ago"
  - **Auto-Detection**: Automatically runs after every purchase to update cycles
  - **Login-Aware**: Only displays reminders for logged-in users, clears panel for guests
  - **Complete Coverage**: Includes ALL user purchases (not limited to catalog items), ensuring single-purchase products are eligible for predictions

### Behavioral Analytics System
- **Frontend Tracking**: Comprehensive JavaScript tracking captures all recommendation interactions:
  - Recommendation shown events with timestamps and nutrition data
  - User actions (Accept Swap, Maybe Later)
  - Scroll depth monitoring on recommendation panels
  - Time-to-action calculation (milliseconds precision)
  - Cart removal tracking for AI-recommended items
  - Real nutrition attribute extraction (protein, sugar, calories, sodium) from product catalog
- **Database Models**:
  - **RecommendationInteraction**: Stores interaction data including product details, nutrition attributes (protein, sugar, calories, sodium), savings, explanations, timestamps, scroll depth, goal alignment flag, and removal flags
  - **UserGoal**: Tracks user health/nutrition goals (goal_type, goal_direction, target_value, priority)
- **Analytics Endpoints**:
  - **POST /api/analytics/track-interaction**: Receives and stores interaction data from frontend with goal alignment checking
  - **GET /api/analytics/metrics**: Computes 10 behavioral metrics:
    1. RAR (Replace Action Rate): % of recommendations accepted
    2. ACR (Action to Cart Rate): % of recommendations added to cart
    3. Time-to-Accept: Average time from shown to accept (seconds)
    4. Average Scroll Depth: Mean scroll percentage on recommendations
    5. BCR (Basket Change Rate): % of AI items later removed from cart
    6. Dismiss Rate: % of recommendations dismissed
    7. Removal Rate: % of accepted items removed from cart
    8. BDS (Behavioral Drift Score): Detects preference shifts over time (protein, sugar, calories, price)
    9. EAS (Explanation Acceptance Score): Measures effectiveness of AI explanations on acceptance rates
    10. HGAB (Health Goal Alignment Behavior): % of goal-aligned recommendations accepted
  - **POST /api/user/goals**: Saves user health/nutrition goals
  - **GET /api/user/goals**: Retrieves active user goals
  - **GET /api/analytics/llm-insights**: AI-powered insights using GPT-4o-mini to analyze all metrics and provide recommendations
  - Supports user-specific filtering and time period filtering (7d, 30d, all)
- **Health Goal System**: User interface in User Panel for setting nutrition goals (increase/decrease protein, sugar, calories, sodium) with target values and priorities
- **Analytics Dashboard**: Dedicated /analytics route with comprehensive visualizations:
  - Overview metrics: RAR, ACR, Time-to-Accept, Scroll Depth
  - Cart behavior: BCR, Dismiss Rate, Removal Rate
  - Advanced analytics: BDS with drift detection alerts, EAS with lift comparisons
  - Health goal alignment: HGAB score with alignment breakdown
  - AI-powered insights: GPT-4o-mini analysis with strengths, weaknesses, recommendations, and performance score
  - Time period and user filtering with real-time updates
  - Color-coded badges, progress bars, and responsive grid layout
- **LLM Evaluation Engine**: Uses OpenAI GPT-4o-mini for automated analysis of recommendation system performance:
  - Comprehensive prompt engineering with industry benchmarks
  - Structured JSON responses with actionable insights
  - 5-minute caching to prevent redundant API calls
  - Priority-based recommendations (High/Medium/Low)
  - Overall performance scoring (1-10 scale)

## External Dependencies

### Python Libraries
- **Flask**: Web framework.
- **Flask-SQLAlchemy**: ORM integration.
- **pandas**: Data manipulation.
- **SQLAlchemy**: Database ORM.
- **sentence-transformers**: Semantic similarity.
- **torch**: PyTorch backend.
- **tensorflow-cpu**: Deep learning framework.
- **scikit-learn**: Machine learning utilities.
- **openai**: OpenAI API client.
- **requests**: HTTP client.
- **lightgbm**: Gradient boosting framework.
- **pyarrow**: Parquet file support.

### Database
- **PostgreSQL**: Primary data storage.

### Data Sources
- **CSV files**: Product catalog (e.g., `GroceryDataset_with_Nutrition_1758836546999.csv`).

### Infrastructure
- **Environment Variables**: For configuration.
- **File System Access**: For data import.