# Food Storage Database

A unified semantic search database for food storage information, built with ChromaDB and sentence transformers.

## Overview

This project unifies two CSV files (`products.csv` and `food_storage.csv`) into a single vector database for semantic search. The database stores comprehensive food storage information including:

- Storage durations (converted to days)
- Multiple storage methods (pantry, refrigerator, freezer)
- Cooking states (raw, cooked, canned, etc.)
- Packaging information
- Production methods (homemade, commercial, etc.)
- Preparation details

## Features

- **Semantic Search**: Find relevant food storage information using natural language queries
- **Multi-Collection Design**: Separate collections for products and food storage data
- **Comprehensive Metadata**: Extract and store detailed metadata from food descriptions
- **Normalized Durations**: All storage times converted to days for consistency
- **Persistent Storage**: Database persists to disk for repeated use

## Installation

```bash
pip install chromadb sentence-transformers pandas numpy
```

## Usage

### 1. Create the Database

Run the unification script to process the CSV files and create the database:

```bash
python unify_food_database.py
```

This will:
- Load and process `products.csv` and `food_storage.csv`
- Extract metadata from descriptions
- Convert all durations to days
- Generate embeddings using `all-MiniLM-L6-v2`
- Store everything in ChromaDB at `./chroma_db/`

**Expected Output:**
```
Loading ./products.csv... 661 rows found
Loading ./food_storage.csv... 3870 rows found

Processing products.csv...
  ✓ 661 products processed
Processing food_storage.csv...
  ✓ 3870 food storage entries processed

Creating ChromaDB collections...
  ✓ Collection 'products' created
  ✓ Collection 'food_storage' created

Database statistics:
  Products collection: 661 items
  Food storage collection: 3870 items
  Total documents: 4531
```

### 2. Query the Database

Use the query script to perform semantic searches:

```bash
python query_food_database.py
```

This demonstrates various query types including:
- Basic semantic search
- Search by storage method
- Search by cooking state
- Search by opened/closed status
- Query both collections simultaneously
- Get specific product details

### 3. Programmatic Queries

You can also use the database programmatically in your own scripts:

```python
from query_food_database import FoodDatabaseQuery

# Initialize the database
db = FoodDatabaseQuery()

# Basic semantic search
results = db.query_products("How long can I store cheese?", n_results=5)

# Search with filters
results = db.search_by_storage_method("beef storage", "freeze")

# Get specific product details
details = db.get_product_details(product_id=1)
```

## Database Schema

### Collection: products

Contains data from `products.csv` with the following metadata fields:

- `id`: Product ID
- `name`: Product name
- `name_subtitle`: Product subtitle/variant
- `keywords`: Search keywords
- `category_id`: Category ID
- `pantry_min/max`: Storage duration in days
- `refrigerate_min/max`: Storage duration in days
- `freeze_min/max`: Storage duration in days
- `pantry_tips`, `refrigerate_tips`, `freeze_tips`: Storage tips
- `can_pantry`, `can_refrigerate`, `can_freeze`: Boolean flags

### Collection: food_storage

Contains data from `food_storage.csv` with the following metadata fields:

- `food_item`: Original food item description
- `storage_method`: Storage method (pantry/refrigerate/freeze)
- `duration_min/max`: Storage duration in days
- `cooking_state`: Raw, cooked, canned, etc.
- `cooking_state_detail`: Additional details
- `packaging`: Packaging type (canned, bottled, wrapped, etc.)
- `packaging_type`: Opened/closed status
- `cut_state`: Whole, cut up, sliced, etc.
- `production`: Production method (homemade, commercial, etc.)
- `production_type`: Additional production details
- `preparation`: Preparation details (smoked, dried, marinated, etc.)
- `is_opened`: Opened/closed boolean

## Duration Conversion

All durations are normalized to days:
- **Days**: 1 day = 1 day
- **Weeks**: 1 week = 7 days
- **Months**: 1 month = 30 days
- **Years**: 1 year = 365 days
- **Indefinitely**: 99,999 days
- **Missing/Empty**: -1
- **Use-by date**: -1

## Example Queries

### Basic Semantic Search
```python
# Find storage information for cheese
db.query_products("How long can I store cheese?")

# Search for raw meat
db.query_food_storage("raw meat refrigerator")
```

### Filtered Search
```python
# Only freezer storage
db.search_by_storage_method("beef storage", "freeze")

# Only cooked items
db.search_by_cooking_state("chicken", "cooked")

# Only opened packages
db.search_by_opened_status("vegetables", True)
```

### Query Both Collections
```python
# Get results from both collections
results = db.query_both("fresh fruit storage recommendations")
print(results['products'])
print(results['food_storage'])
```

## Project Structure

```
.
├── products.csv              # Products data source
├── food_storage.csv          # Food storage data source
├── unify_food_database.py    # Database creation script
├── query_food_database.py    # Query interface and examples
├── chroma_db/               # ChromaDB persistent storage
│   ├── chroma.sqlite3       # Database file
│   └── {collection_dirs}/   # Collection data
└── README.md                # This file
```

## Technical Details

- **Embedding Model**: `sentence-transformers/all-MiniLM-L6-v2`
- **Vector Space**: Cosine similarity
- **Database**: ChromaDB with persistent storage
- **Total Documents**: 4,531 (661 products + 3,870 food storage entries)
- **Metadata Fields**: 20+ fields for comprehensive filtering

## Notes

- The first run will download the embedding model (approximately 120MB)
- Subsequent runs will use the cached model
- The database persists to disk and doesn't need to be recreated
- LSP errors in the code are type-checking warnings and don't affect runtime
- All None values are converted to empty strings for ChromaDB compatibility

## License

This project processes publicly available food storage data. Please check the source CSV files for their respective licenses.