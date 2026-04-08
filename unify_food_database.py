"""
unify_food_database.py - Unify products.csv and food_storage.csv into ChromaDB

This script loads two CSV files, processes and normalizes the data,
extracts comprehensive metadata, and stores everything in ChromaDB
for semantic search.

Usage:
    python unify_food_database.py
"""

import pandas as pd
import numpy as np
import re
from typing import Dict, List, Optional, Tuple
import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
import os
import warnings

warnings.filterwarnings("ignore")


class Config:
    """Configuration constants"""

    CHROMA_DB_PATH = "./chroma_db"
    PRODUCTS_CSV = "./products.csv"
    FOOD_STORAGE_CSV = "./food_storage.csv"
    EMBEDDING_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"
    INDEFINITE_DAYS = 99999
    MISSING_VALUE = -1


class DurationConverter:
    """Convert various duration formats to days"""

    UNIT_MULTIPLIERS = {
        "days": 1,
        "day": 1,
        "weeks": 7,
        "week": 7,
        "months": 30,
        "month": 30,
        "years": 365,
        "year": 365,
    }

    @staticmethod
    def parse_value(value, unit: str = "") -> Tuple[int, int]:
        """Parse duration value with unit and return (min_days, max_days)"""
        # Handle empty or None
        if pd.isna(value) or value == "" or value is None:
            return Config.MISSING_VALUE, Config.MISSING_VALUE

        # Handle "Indefinitely"
        if str(value).lower() == "indefinitely":
            return Config.INDEFINITE_DAYS, Config.INDEFINITE_DAYS

        # Handle "Package use-by date"
        if "use-by date" in str(value).lower():
            return Config.MISSING_VALUE, Config.MISSING_VALUE

        # Try to convert to float first
        try:
            num_val = float(value)
        except (ValueError, TypeError):
            return Config.MISSING_VALUE, Config.MISSING_VALUE

        # Apply unit multiplier
        unit_lower = unit.strip().lower()
        multiplier = 1
        for unit_name, mult in DurationConverter.UNIT_MULTIPLIERS.items():
            if unit_name in unit_lower:
                multiplier = mult
                break

        days = int(num_val * multiplier)
        return days, days

    @staticmethod
    def parse_range(duration_str: str) -> Tuple[int, int]:
        """Parse duration range like '2-3' or '180' into (min_days, max_days)"""
        if pd.isna(duration_str) or duration_str == "" or duration_str is None:
            return Config.MISSING_VALUE, Config.MISSING_VALUE

        duration_str = str(duration_str).strip()

        # Handle "Indefinitely"
        if duration_str.lower() == "indefinitely":
            return Config.INDEFINITE_DAYS, Config.INDEFINITE_DAYS

        # Try to parse as range "min-max"
        if "-" in duration_str:
            parts = duration_str.split("-")
            if len(parts) == 2:
                try:
                    min_val = float(parts[0].strip())
                    max_val = float(parts[1].strip())
                    return int(min_val), int(max_val)
                except (ValueError, TypeError):
                    pass

        # Try to parse as single value
        try:
            val = float(duration_str)
            return int(val), int(val)
        except (ValueError, TypeError):
            return Config.MISSING_VALUE, Config.MISSING_VALUE


class MetadataExtractor:
    """Extract metadata from food item descriptions"""

    COOKING_STATE_KEYWORDS = {
        "raw": "raw",
        "cooked": "cooked",
        "fresh": "fresh",
        "frozen": "frozen",
        "canned": "canned",
        "bottled": "bottled",
        "dry": "dry",
        "vacuum": "vacuum",
    }

    PACKAGING_KEYWORDS = {
        "canned": "canned",
        "bottled": "bottled",
        "packaged": "packaged",
        "wrapped": "wrapped",
        "vacuum": "vacuum",
        "jarred": "jarred",
        "tub": "tub",
        "individually wrapped": "individually",
        "bagged": "bagged",
        "block": "block",
        "wedge": "wedge",
        "slice": "sliced",
        "chunks": "chunked",
    }

    CUT_STATE_KEYWORDS = {
        "whole": "whole",
        "cut up": "cut up",
        "chopped": "chopped",
        "sliced": "sliced",
        "diced": "diced",
        "ground": "ground",
        "shredded": "shredded",
        "crumbled": "crumbled",
        "sliced or chopped": "sliced_or_chopped",
    }

    PRODUCTION_KEYWORDS = {
        "homemade": "homemade",
        "commercially": "commercially",
        "store-prepared": "store_prepared",
        "bakery": "bakery",
        "freshly baked": "freshly_baked",
        "take-out": "take_out",
        "takeout": "take_out",
        "store-sliced": "store_sliced",
    }

    PREPARATION_KEYWORDS = {
        "marinated": "marinated",
        "seasoned": "seasoned",
        "flavored": "flavored",
        "spiced": "spiced",
        "smoked": "smoked",
        "dried": "dried",
        "fermented": "fermented",
        "pasteurized": "pasteurized",
        "roasted": "roasted",
        "pickled": "pickled",
    }

    @staticmethod
    def extract_cooking_state(description: str) -> Dict[str, Optional[str]]:
        """Extract cooking state from description"""
        desc_lower = description.lower()
        cooking_state = None
        state_detail = None

        for keyword, state in MetadataExtractor.COOKING_STATE_KEYWORDS.items():
            if keyword in desc_lower:
                cooking_state = state
                # Extract detail context (e.g., "commercially", "homemade")
                if state in ["canned", "bottled", "dry"]:
                    for prod_keyword in ["commercially", "homemade", "vacuum"]:
                        if prod_keyword in desc_lower:
                            state_detail = prod_keyword
                            break
                break

        return {"cooking_state": cooking_state, "cooking_state_detail": state_detail}

    @staticmethod
    def extract_packaging(description: str) -> Dict[str, Optional[str]]:
        """Extract packaging information from description"""
        desc_lower = description.lower()
        packaging = None
        packaging_type = None

        for keyword, pack_type in MetadataExtractor.PACKAGING_KEYWORDS.items():
            if keyword in desc_lower:
                packaging = pack_type
                break

        # Determine opened/closed type
        if "opened" in desc_lower:
            packaging_type = "opened"
        elif "unopened" in desc_lower:
            packaging_type = "unopened"

        return {"packaging": packaging, "packaging_type": packaging_type}

    @staticmethod
    def extract_cut_state(description: str) -> Optional[str]:
        """Extract cut/whole state from description"""
        desc_lower = description.lower()
        for keyword, cut_state in MetadataExtractor.CUT_STATE_KEYWORDS.items():
            if keyword in desc_lower:
                return cut_state
        return None

    @staticmethod
    def extract_production(description: str) -> Dict[str, Optional[str]]:
        """Extract production method from description"""
        desc_lower = description.lower()
        production = None
        production_type = None

        for keyword, prod_type in MetadataExtractor.PRODUCTION_KEYWORDS.items():
            if keyword in desc_lower:
                production = prod_type
                break

        # Extract additional production details
        if production == "commercially":
            if "packaged" in desc_lower:
                production_type = "packaged"
            elif "bottled" in desc_lower:
                production_type = "bottled"
            elif "canned" in desc_lower:
                production_type = "canned"

        return {"production": production, "production_type": production_type}

    @staticmethod
    def extract_preparation(description: str) -> Optional[str]:
        """Extract preparation details from description"""
        desc_lower = description.lower()
        for keyword, prep in MetadataExtractor.PREPARATION_KEYWORDS.items():
            if keyword in desc_lower:
                return prep
        return None

    @staticmethod
    def extract_opened_status(description: str) -> Optional[bool]:
        """Extract opened/closed status from description"""
        desc_lower = description.lower()
        if "opened" in desc_lower:
            return True
        elif "unopened" in desc_lower:
            return False
        return None

    @staticmethod
    def extract_all_metadata(description: str) -> Dict:
        """Extract all metadata from description"""
        metadata = {}

        # Extract cooking state
        cooking_meta = MetadataExtractor.extract_cooking_state(description)
        metadata.update(cooking_meta)

        # Extract packaging
        packaging_meta = MetadataExtractor.extract_packaging(description)
        metadata.update(packaging_meta)

        # Extract cut state
        metadata["cut_state"] = MetadataExtractor.extract_cut_state(description)

        # Extract production
        production_meta = MetadataExtractor.extract_production(description)
        metadata.update(production_meta)

        # Extract preparation
        metadata["preparation"] = MetadataExtractor.extract_preparation(description)

        # Extract opened status
        metadata["is_opened"] = MetadataExtractor.extract_opened_status(description)

        return metadata


class ProductsProcessor:
    """Process products.csv data"""

    def __init__(self, csv_path: str):
        self.csv_path = csv_path
        self.df = None
        self.processed_data = []

    def load(self):
        """Load CSV file"""
        print(f"Loading {self.csv_path}...", end=" ")
        self.df = pd.read_csv(self.csv_path)
        print(f"{len(self.df)} rows found")

    def process_row(self, row: pd.Series, row_num: int) -> Dict:
        """Process a single row from products.csv"""
        metadata = {
            "id": int(row.get("ID", row_num)),
            "name": str(row.get("Name", "")).strip(),
            "name_subtitle": str(row.get("Name_subtitle", "")).strip(),
            "keywords": str(row.get("Keywords", "")).strip(),
            "category_id": int(row.get("Category_ID", 0)),
            "source": "products.csv",
        }

        # Process pantry storage
        pantry_min, pantry_max = DurationConverter.parse_value(
            row.get("Pantry_Min"), row.get("Pantry_Metric", "")
        )
        metadata["pantry_min"] = pantry_min
        metadata["pantry_max"] = pantry_max
        metadata["pantry_tips"] = str(row.get("Pantry_tips", "")).strip()
        metadata["can_pantry"] = bool(row.get("canPantry", False))

        # Process refrigerate storage
        refrig_min, refrig_max = DurationConverter.parse_value(
            row.get("Refrigerate_Min"), row.get("Refrigerate_Metric", "")
        )
        metadata["refrigerate_min"] = refrig_min
        metadata["refrigerate_max"] = refrig_max
        metadata["refrigerate_tips"] = str(row.get("Refrigerate_tips", "")).strip()
        metadata["can_refrigerate"] = bool(row.get("canRefrigerate", False))

        # Process freeze storage
        freeze_min, freeze_max = DurationConverter.parse_value(
            row.get("Freeze_Min"), row.get("Freeze_Metric", "")
        )
        metadata["freeze_min"] = freeze_min
        metadata["freeze_max"] = freeze_max
        metadata["freeze_tips"] = str(row.get("Freeze_Tips", "")).strip()
        metadata["can_freeze"] = bool(row.get("canFreeze", False))

        # Create document text for embedding
        doc_parts = [metadata["name"]]
        if metadata["name_subtitle"]:
            doc_parts.append(metadata["name_subtitle"])
        if metadata["keywords"]:
            doc_parts.append(metadata["keywords"])
        document = " ".join(doc_parts)

        return {
            "document": document,
            "metadata": metadata,
            "id": f"products_{metadata['id']}",
        }

    def process_all(self) -> List[Dict]:
        """Process all rows in the dataframe"""
        print("Processing products.csv...")
        self.processed_data = []

        for idx, row in self.df.iterrows():
            processed = self.process_row(row, idx + 1)
            self.processed_data.append(processed)

        print(f"  ✓ {len(self.processed_data)} products processed")
        return self.processed_data


class FoodStorageProcessor:
    """Process food_storage.csv data"""

    def __init__(self, csv_path: str):
        self.csv_path = csv_path
        self.df = None
        self.processed_data = []

    def load(self):
        """Load CSV file"""
        print(f"Loading {self.csv_path}...", end=" ")
        self.df = pd.read_csv(self.csv_path)
        print(f"{len(self.df)} rows found")

    def parse_storage_method(self, method: str) -> str:
        """Standardize storage method names"""
        if not method:
            return None
        method_lower = method.lower().strip()
        if "refrigerat" in method_lower:
            return "refrigerate"
        elif "freez" in method_lower:
            return "freeze"
        else:
            return "pantry"

    def process_row(self, row: pd.Series, row_num: int) -> List[Dict]:
        """Process a single row from food_storage.csv

        Note: Each food item may have multiple storage methods,
        so this returns a list of processed items.
        """
        food_item = str(row.get("Food Item", "")).strip()
        storage_method = self.parse_storage_method(row.get("Storage Method", ""))
        duration_str = str(row.get("Duration (Days)", "")).strip()

        # Parse duration
        duration_min, duration_max = DurationConverter.parse_range(duration_str)

        # Extract metadata from food item description
        metadata = MetadataExtractor.extract_all_metadata(food_item)

        # Add basic metadata
        metadata.update(
            {
                "food_item": food_item,
                "storage_method": storage_method,
                "duration_min": duration_min,
                "duration_max": duration_max,
                "source": "food_storage.csv",
            }
        )

        return [
            {
                "document": food_item,
                "metadata": metadata,
                "id": f"food_storage_{row_num}_{storage_method or 'unknown'}",
            }
        ]

    def process_all(self) -> List[Dict]:
        """Process all rows in the dataframe"""
        print("Processing food_storage.csv...")
        self.processed_data = []

        for idx, row in self.df.iterrows():
            processed = self.process_row(row, idx + 1)
            self.processed_data.extend(processed)

        print(f"  ✓ {len(self.processed_data)} food storage entries processed")
        return self.processed_data


class DatabaseManager:
    """Manage ChromaDB operations"""

    @staticmethod
    def clean_metadata(metadata: Dict) -> Dict:
        """Clean metadata to ensure all values are ChromaDB-compatible"""
        cleaned = {}
        for key, value in metadata.items():
            # Handle None values
            if value is None:
                cleaned[key] = ""  # Replace None with empty string
            # Handle boolean values
            elif isinstance(value, bool):
                cleaned[key] = value
            # Handle numeric values
            elif isinstance(value, (int, float)):
                cleaned[key] = value
            # Handle string values
            elif isinstance(value, str):
                cleaned[key] = value
            # Handle other types - convert to string
            else:
                cleaned[key] = str(value)
        return cleaned

    def __init__(self, db_path: str, model_name: str):
        self.db_path = db_path
        self.model_name = model_name
        self.client = None
        self.model = None
        self.collections = {}

        # Create database directory if it doesn't exist
        os.makedirs(db_path, exist_ok=True)

    def initialize(self):
        """Initialize ChromaDB client and embedding model"""
        print(f"Initializing ChromaDB at {self.db_path}...")
        print(f"Loading embedding model: {self.model_name}...")

        # Initialize ChromaDB client with persistence
        self.client = chromadb.PersistentClient(path=self.db_path)

        # Load embedding model
        self.model = SentenceTransformer(self.model_name)

        print(f"  ✓ ChromaDB initialized")
        print(f"  ✓ Embedding model loaded")

    def get_or_create_collection(self, name: str) -> chromadb.Collection:
        """Get existing collection or create new one"""
        try:
            collection = self.client.get_collection(name=name)
            print(f"  ✓ Collection '{name}' already exists")
        except:
            collection = self.client.create_collection(
                name=name, metadata={"hnsw:space": "cosine"}
            )
            print(f"  ✓ Collection '{name}' created")

        self.collections[name] = collection
        return collection

    def add_documents(
        self,
        collection_name: str,
        documents: List[str],
        metadatas: List[Dict],
        ids: List[str],
    ):
        """Add documents to a collection with embeddings"""
        collection = self.collections.get(collection_name)
        if not collection:
            collection = self.get_or_create_collection(collection_name)

        print(f"Adding documents to '{collection_name}' collection...", end=" ")

        # Clean metadata to ensure ChromaDB compatibility
        cleaned_metadatas = [DatabaseManager.clean_metadata(m) for m in metadatas]

        # Generate embeddings
        embeddings = self.model.encode(documents, convert_to_numpy=True)

        # Add documents to collection
        collection.add(
            documents=documents,
            embeddings=embeddings.tolist(),
            metadatas=cleaned_metadatas,
            ids=ids,
        )

        print(f"✓ {len(documents)} documents added")

    def query(
        self,
        collection_name: str,
        query_text: str,
        n_results: int = 5,
        filters: Dict = None,
    ):
        """Perform semantic search with optional filters"""
        collection = self.collections.get(collection_name)
        if not collection:
            return None

        query_embedding = self.model.encode([query_text], convert_to_numpy=True)

        results = collection.query(
            query_embeddings=query_embedding.tolist(),
            n_results=n_results,
            where=filters,
        )

        return results

    def get_collection_stats(self, collection_name: str) -> Dict:
        """Get statistics about a collection"""
        collection = self.collections.get(collection_name)
        if not collection:
            return {}

        return {"name": collection_name, "count": collection.count()}


def run_test_queries(db_manager: DatabaseManager):
    """Run test queries to verify the database is working"""
    print("\n" + "=" * 60)
    print("Testing queries...")
    print("=" * 60)

    test_queries = [
        ("products", "beef freezer storage"),
        ("products", "opened cheese storage"),
        ("food_storage", "raw meat refrigerator"),
        ("food_storage", "canned vegetables"),
    ]

    for collection_name, query in test_queries:
        print(f"\nQuery: '{query}' (Collection: {collection_name})")
        results = db_manager.query(collection_name, query, n_results=3)

        if results:
            for i, (doc, metadata, distance) in enumerate(
                zip(
                    results["documents"][0],
                    results["metadatas"][0],
                    results["distances"][0],
                )
            ):
                print(f"  {i + 1}. {doc}")
                print(f"     Distance: {distance:.4f}")
        else:
            print("  No results found")


def main():
    """Main execution function"""
    print("=" * 60)
    print("Food Database Unification Tool")
    print("=" * 60)

    # Initialize database manager
    db_manager = DatabaseManager(
        db_path=Config.CHROMA_DB_PATH, model_name=Config.EMBEDDING_MODEL
    )
    db_manager.initialize()

    # Load and process products.csv
    products_processor = ProductsProcessor(Config.PRODUCTS_CSV)
    products_processor.load()
    products_data = products_processor.process_all()

    # Load and process food_storage.csv
    food_storage_processor = FoodStorageProcessor(Config.FOOD_STORAGE_CSV)
    food_storage_processor.load()
    food_storage_data = food_storage_processor.process_all()

    # Create collections
    print("\nCreating ChromaDB collections...")
    products_collection = db_manager.get_or_create_collection("products")
    food_storage_collection = db_manager.get_or_create_collection("food_storage")

    # Add documents to collections
    if products_data:
        documents = [item["document"] for item in products_data]
        metadatas = [item["metadata"] for item in products_data]
        ids = [item["id"] for item in products_data]
        db_manager.add_documents("products", documents, metadatas, ids)

    if food_storage_data:
        documents = [item["document"] for item in food_storage_data]
        metadatas = [item["metadata"] for item in food_storage_data]
        ids = [item["id"] for item in food_storage_data]
        db_manager.add_documents("food_storage", documents, metadatas, ids)

    # Get statistics
    print("\n" + "=" * 60)
    print("Database statistics:")
    print("=" * 60)

    products_stats = db_manager.get_collection_stats("products")
    food_storage_stats = db_manager.get_collection_stats("food_storage")

    print(f"Products collection: {products_stats.get('count', 0)} items")
    print(f"Food storage collection: {food_storage_stats.get('count', 0)} items")
    print(
        f"Total documents: {(products_stats.get('count', 0) + food_storage_stats.get('count', 0))}"
    )
    print(f"Database location: {Config.CHROMA_DB_PATH}")

    # Run test queries
    run_test_queries(db_manager)

    print("\n" + "=" * 60)
    print("Database successfully created and tested!")
    print("=" * 60)


if __name__ == "__main__":
    main()
