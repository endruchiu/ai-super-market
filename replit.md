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
- **Batch processing** for efficient data imports with commit batching every 100 records

### Data Processing
- **CSV import system** using pandas for bulk product data loading
- **Smart parsing utilities** for extracting numeric values from text fields (prices, ratings, review counts)
- **Regular expressions** for robust text parsing of currency amounts and rating formats

### Application Structure
- **Factory pattern** for model initialization allowing for flexible database configuration
- **Global model registration** making models available across the application after initialization
- **Environment-based configuration** for database URLs and secret keys

### Performance Optimizations
- **Database connection pooling** with pool recycling and pre-ping health checks
- **Batch commits** during data import operations to improve performance
- **Numeric field extraction** for efficient querying and calculations

## External Dependencies

### Python Libraries
- **Flask** - Web framework for routing and request handling
- **Flask-SQLAlchemy** - Database ORM integration
- **pandas** - CSV data processing and manipulation for product imports
- **SQLAlchemy** - Database abstraction and ORM functionality

### Database
- **PostgreSQL** (via DATABASE_URL environment variable) - Primary data storage for products, shopping carts, and user budgets

### Data Sources
- **CSV files** - Product catalog data import from `attached_assets/GroceryDataset_with_Nutrition_1758836546999.csv` (nutrition-enhanced dataset with 1,757 products)
- **Nutritional Information** - Complete nutrition facts including calories, fat, carbs, sugar, protein, and sodium content for all products

### Infrastructure Requirements
- **Environment variables** for database connection and Flask secret key configuration
- **File system access** for CSV data import operations