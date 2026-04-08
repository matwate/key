#!/usr/bin/env python3
"""
Build a ChromaDB collection from the FoodKeeper Spanish JSON data.
This creates a 'products_foodkeeper_es' collection with 662 products
that have Spanish names, subtitles, and storage information.

Usage:
    python build_spanish_foodkeeper.py
"""

import json
import chromadb
from sentence_transformers import SentenceTransformer
from typing import Dict, List, Optional, Tuple

DB_PATH = "./chroma_db"
JSON_PATH = "./src/testassets/database/foodkeeper-spanish.json"
MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"
MISSING = -1
INDEFINITE = 99999


def get_field(product: list, field_name: str):
    for item in product:
        if field_name in item and item[field_name] is not None:
            return item[field_name]
    return None


UNIT_MULTIPLIERS = {
    "días": 1,
    "día": 1,
    "semanas": 7,
    "semana": 7,
    "meses": 30,
    "mes": 30,
    "años": 365,
    "año": 365,
}


def parse_duration(value, metric: str = "") -> Tuple[int, int]:
    if value is None or value == "" or str(value).lower() == "no recomendado":
        return MISSING, MISSING
    if str(value).lower() == "indefinidamente":
        return INDEFINITE, INDEFINITE
    try:
        num = float(value)
    except (ValueError, TypeError):
        return MISSING, MISSING
    metric_lower = str(metric).strip().lower()
    multiplier = 1
    for unit_name, mult in UNIT_MULTIPLIERS.items():
        if unit_name in metric_lower:
            multiplier = mult
            break
    days = int(num * multiplier)
    return days, days


def parse_range(duration_str: str) -> Tuple[int, int]:
    if not duration_str or str(duration_str).lower() == "no recomendado":
        return MISSING, MISSING
    s = str(duration_str).strip()
    if "-" in s:
        parts = s.split("-")
        if len(parts) == 2:
            try:
                return int(float(parts[0].strip())), int(float(parts[1].strip()))
            except (ValueError, TypeError):
                pass
    try:
        v = int(float(s))
        return v, v
    except (ValueError, TypeError):
        return MISSING, MISSING


def extract_all_metadata(description: str) -> Dict:
    desc_lower = description.lower()
    cooking_state = None
    for kw in ["crudo", "cocido", "fresco", "congelado", "enlatado", "seco", "ahumado"]:
        if kw in desc_lower:
            cooking_state = kw
            break

    packaging = None
    for kw in ["enlatado", "embotellado", "envasado", "frasco", "caja", "bolsa"]:
        if kw in desc_lower:
            packaging = kw
            break

    is_opened = None
    if "abierto" in desc_lower or "después de abrir" in desc_lower:
        is_opened = True
    elif "cerrado" in desc_lower or "sin abrir" in desc_lower:
        is_opened = False

    return {
        "cooking_state": cooking_state or "",
        "packaging": packaging or "",
        "is_opened": is_opened,
    }


def main():
    print("=" * 60)
    print("Building FoodKeeper Spanish ChromaDB Collection")
    print("=" * 60)

    with open(JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    product_sheet = None
    for sheet in data["sheets"]:
        if sheet["name"] == "Product":
            product_sheet = sheet
            break

    if not product_sheet:
        print("ERROR: Product sheet not found in JSON")
        return

    print(f"Found {len(product_sheet['data'])} products in Spanish FoodKeeper")

    client = chromadb.PersistentClient(path=DB_PATH)

    try:
        existing = client.get_collection(name="products_foodkeeper_es")
        print(
            f"Deleting existing 'products_foodkeeper_es' collection ({existing.count()} items)"
        )
        client.delete_collection(name="products_foodkeeper_es")
    except Exception:
        pass

    collection = client.create_collection(
        name="products_foodkeeper_es",
        metadata={"hnsw:space": "cosine"},
    )
    print("Created new 'products_foodkeeper_es' collection")

    model = SentenceTransformer(MODEL_NAME)
    print(f"Loaded embedding model: {MODEL_NAME}")

    documents = []
    metadatas = []
    ids = []

    for idx, product in enumerate(product_sheet["data"]):
        product_id = int(get_field(product, "ID") or 0)
        category_id = int(get_field(product, "Category_ID") or 0)
        name_es = str(get_field(product, "Name") or "").strip()
        subtitle_es = str(get_field(product, "Name_subtitle") or "").strip()
        keywords = str(get_field(product, "Keywords") or "").strip()

        if not name_es:
            continue

        name_en = ""
        if keywords:
            first_keyword = keywords.split(",")[0].strip()
            if first_keyword:
                name_en = first_keyword

        extra_meta = extract_all_metadata(f"{name_es} {subtitle_es}")

        pantry_min, pantry_max = parse_duration(
            get_field(product, "DOP_Pantry_Min"),
            get_field(product, "DOP_Pantry_Metric"),
        )
        pantry_tips = str(get_field(product, "DOP_Pantry_tips") or "").strip()
        can_pantry = pantry_min != MISSING

        if pantry_min == MISSING:
            pantry_min2, pantry_max2 = parse_duration(
                get_field(product, "Pantry_Min"),
                get_field(product, "Pantry_Metric"),
            )
            if pantry_min2 != MISSING:
                pantry_min, pantry_max = pantry_min2, pantry_max2
                pantry_tips = str(get_field(product, "Pantry_tips") or "").strip()
                can_pantry = True

        refrig_min, refrig_max = parse_duration(
            get_field(product, "DOP_Refrigerate_Min"),
            get_field(product, "DOP_Refrigerate_Metric"),
        )
        refrig_tips = str(get_field(product, "DOP_Refrigerate_tips") or "").strip()
        can_refrig = refrig_min != MISSING

        if refrig_min == MISSING:
            refrig_min2, refrig_max2 = parse_duration(
                get_field(product, "Refrigerate_Min"),
                get_field(product, "Refrigerate_Metric"),
            )
            if refrig_min2 != MISSING:
                refrig_min, refrig_max = refrig_min2, refrig_max2
                refrig_tips = str(get_field(product, "Refrigerate_tips") or "").strip()
                can_refrig = True

        freeze_min, freeze_max = parse_duration(
            get_field(product, "DOP_Freeze_Min"),
            get_field(product, "DOP_Freeze_Metric"),
        )
        freeze_tips = str(get_field(product, "DOP_Freeze_Tips") or "").strip()
        can_freeze = freeze_min != MISSING

        if freeze_min == MISSING:
            freeze_min2, freeze_max2 = parse_duration(
                get_field(product, "Freeze_Min"),
                get_field(product, "Freeze_Metric"),
            )
            if freeze_min2 != MISSING:
                freeze_min, freeze_max = freeze_min2, freeze_max2
                freeze_tips = str(get_field(product, "Freeze_Tips") or "").strip()
                can_freeze = True

        if not can_pantry and not can_refrig and not can_freeze:
            continue

        doc_parts = [name_es]
        if subtitle_es:
            doc_parts.append(subtitle_es)
        if keywords:
            doc_parts.append(keywords)
        document = " ".join(doc_parts)

        metadata = {
            "id": product_id,
            "name_spanish": name_es,
            "name_english": name_en,
            "name_subtitle_spanish": subtitle_es,
            "keywords": keywords,
            "category_id": category_id,
            "source": "foodkeeper_spanish",
            "can_pantry": can_pantry,
            "pantry_min": pantry_min,
            "pantry_max": pantry_max,
            "pantry_tips": pantry_tips,
            "can_refrigerate": can_refrig,
            "refrigerate_min": refrig_min,
            "refrigerate_max": refrig_max,
            "refrigerate_tips": refrig_tips,
            "can_freeze": can_freeze,
            "freeze_min": freeze_min,
            "freeze_max": freeze_max,
            "freeze_tips": freeze_tips,
            "cooking_state": extra_meta["cooking_state"],
            "packaging": extra_meta["packaging"],
        }

        if extra_meta["is_opened"] is not None:
            metadata["is_opened"] = extra_meta["is_opened"]

        documents.append(document)
        metadatas.append(metadata)
        ids.append(f"fk_es_{product_id}")

    print(f"\nProcessed {len(documents)} products with storage data")

    batch_size = 200
    for i in range(0, len(documents), batch_size):
        batch_docs = documents[i : i + batch_size]
        batch_metas = metadatas[i : i + batch_size]
        batch_ids = ids[i : i + batch_size]

        embeddings = model.encode(batch_docs, convert_to_numpy=True)

        collection.add(
            documents=batch_docs,
            embeddings=embeddings.tolist(),
            metadatas=batch_metas,
            ids=batch_ids,
        )
        print(f"  Added batch {i // batch_size + 1}: {len(batch_docs)} documents")

    print(f"\n✓ Total documents in collection: {collection.count()}")

    print("\n" + "=" * 60)
    print("Verification queries:")
    print("=" * 60)

    test_queries = [
        "huevos",
        "carne de res",
        "pollo pechuga",
        "salchicha",
        "plátano",
        "pan",
        "leche",
        "atún enlatado",
    ]

    for query in test_queries:
        q_emb = model.encode([query], convert_to_numpy=True)
        results = collection.query(query_embeddings=q_emb.tolist(), n_results=2)

        print(f"\nQuery: '{query}'")
        if results["documents"] and results["documents"][0]:
            for i, (doc, meta, dist) in enumerate(
                zip(
                    results["documents"][0],
                    results["metadatas"][0],
                    results["distances"][0],
                )
            ):
                es = meta.get("name_spanish", "N/A")
                en = meta.get("name_english", "N/A")
                print(f"  {i + 1}. {es} ({en}) [dist: {dist:.4f}]")
                if meta.get("can_refrigerate"):
                    print(
                        f"     Refrigerate: {meta['refrigerate_min']}-{meta['refrigerate_max']} days"
                    )
                if meta.get("can_freeze"):
                    print(
                        f"     Freeze: {meta['freeze_min']}-{meta['freeze_max']} days"
                    )

    print("\n" + "=" * 60)
    print("Done!")
    print("=" * 60)


if __name__ == "__main__":
    main()
