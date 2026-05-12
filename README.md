# Receipt Analyzer

FastAPI service and small static frontend for analyzing Colombian grocery
receipts.

The app accepts a receipt image, extracts purchased products with a vision
model, normalizes Colombian grocery names, looks up food storage guidance from
a local ChromaDB database.

## What It Does

- Upload a receipt image through `static/index.html`
- Extract product names, quantities, and unit prices
- Normalize Spanish/Colombian supermarket item names into common food names
- Query local semantic food-storage collections for pantry, fridge, and freezer
  guidance
- Return a structured JSON response for every detected receipt item
- Provide basic email/password auth with JWTs

## Stack

- Python 3.11+
- FastAPI
- SQLite
- ChromaDB
- sentence-transformers
- Z.ai SDK
- Static HTML/CSS/JS frontend

## Setup

Install dependencies:

```bash
uv sync
```

Create a `.env` file with:

```bash
ZAI_API_KEY=your_key_here
SECRET_KEY=change_this_for_real_deployments
JWT_EXPIRE_MINUTES=60
```

The app expects the ChromaDB storage database at `./chroma_db`.

## Run

```bash
uv run python main.py
```

The API starts on:

```text
http://localhost:5003
```

The frontend is a static file:

```text
static/index.html
```

Note: `static/index.html` currently points at a deployed API URL. Change
`API_URL` in that file if you want it to call your local server.

## API

### `GET /`

Returns basic service metadata.

### `GET /health`

Returns a health check.

### `POST /api/receipt/analyze`

Accepts multipart form data with an uploaded image field named `file`.

Example:

```bash
curl -X POST http://localhost:5003/api/receipt/analyze \
  -F "file=@receipt.jpg"
```

Response shape:

```json
{
  "success": true,
  "total_items": 1,
  "products": [
    {
      "original_name": "HUEVO AAA RJO 15UN",
      "normalized_name": "Grade AAA Eggs",
      "spanish_name": "HUEVO AAA RJO 15UN",
      "quantity": "15 un",
      "price": "12000",
      "storage_options": [],
      "nutrition_info": null,
      "status": "success",
      "error": null,
      "debug_info": {}
    }
  ]
}
```

### `POST /api/auth/register`

Registers a user and returns a bearer token.

### `POST /api/auth/login`

Logs in a user and returns a bearer token.

## Important Files

- `main.py` - Uvicorn entry point
- `src/api.py` - FastAPI app and receipt endpoint
- `src/receipt_processor.py` - receipt product processing pipeline
- `src/exploration.py` - Z.ai vision receipt extraction
- `src/translation.py` - Colombian grocery translation/normalization
- `src/food_database.py` - ChromaDB query wrapper
- `src/auth.py` and `src/auth_routes.py` - JWT auth
- `src/database.py` - SQLite user database
- `static/index.html` - upload UI
- `unify_food_database.py` - builds the ChromaDB food storage database
- `build_spanish_foodkeeper.py` - builds Spanish FoodKeeper collection data

## Food Storage Database

The local semantic database is built from:

- `products.csv`
- `food_storage.csv`
- FoodKeeper Spanish test assets under `src/testassets/database/`

To rebuild the main storage database:

```bash
uv run python unify_food_database.py
```

This writes persistent ChromaDB data into `./chroma_db`.

## Local Data

Runtime local data includes:

- `key.db` - SQLite users
- `chroma_db/` - ChromaDB collections
- `.env` - API keys and auth settings

Do not commit real secrets.
