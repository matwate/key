import os
import re
from typing import Dict, List, Optional

from dotenv import load_dotenv

from .food_database import FoodDatabaseQuery
from .models import (
    NutritionInfo,
    ProcessedProduct,
    Product,
    ReceiptAnalysis,
    StorageInfo,
)
from .result import Err, Ok, Result
from .translation import TranslationResult, TranslationService

QUANTITY_OCR_FIXES = {
    "k9": "kg",
    "kq": "kg",
    "kl": "kg",
    "q9": "g",
    "grl": "gr",
}

FOOD_CATEGORY_MAP = {
    "egg": "eggs",
    "eggs": "eggs",
    "huevo": "eggs",
    "huevos": "eggs",
    "sausage": "sausage",
    "salchicha": "sausage",
    "chicken": "chicken",
    "pollo": "chicken",
    "beef": "beef",
    "carne": "beef",
    "res": "beef",
    "banana": "banana",
    "banano": "banana",
    "bread": "bread",
    "pan": "bread",
    "milk": "milk",
    "leche": "milk",
    "cheese": "cheese",
    "queso": "cheese",
    "soda": "soda",
    "refresco": "soda",
    "gaseosa": "soda",
    "tuna": "tuna",
    "atún": "tuna",
    "candy": "candy",
    "caramelos": "candy",
    "rice": "rice",
    "arroz": "rice",
    "coffee": "coffee",
    "café": "coffee",
    "juice": "juice",
    "jugo": "juice",
    "beer": "beer",
    "cerveza": "beer",
    "oil": "oil",
    "aceite": "oil",
    "butter": "butter",
    "mantequilla": "butter",
    "fish": "fish",
    "pescado": "fish",
    "plantain": "plantain",
    "plátano": "plantain",
}

STORAGE_PREFERENCE = {
    "eggs": "refrigerate",
    "banana": "pantry",
    "bread": "pantry",
    "candy": "pantry",
    "soda": "pantry",
}

PRODUCT_COLLECTIONS = [
    ("products_foodkeeper_es", 0.67),
    ("products_spanish", 0.70),
    ("products", 0.70),
]


class ReceiptProcessor:
    def __init__(
        self,
        translation_service: Optional[TranslationService] = None,
        food_database: Optional[FoodDatabaseQuery] = None,
    ):
        load_dotenv()
        self.translation = translation_service or TranslationService()
        self.food_db = food_database or FoodDatabaseQuery()

        from .exploration import scan_receipt

        self.scan_receipt = scan_receipt
        from .openfood import find_by_text

        self.find_by_text = find_by_text

    def process_receipt(self, image_path: str) -> Result[ReceiptAnalysis, str]:
        if not os.path.exists(image_path):
            return Err(f"Image file not found: {image_path}")

        extract_result = self._extract_products(image_path)
        if extract_result.is_err():
            return Err(f"Failed to extract products: {extract_result.unwrap_err()}")

        products = extract_result.unwrap()
        processed = [self._process_single_product(p) for p in products]
        return Ok(ReceiptAnalysis(total_items=len(processed), products=processed))

    def _extract_products(self, image_path: str) -> Result[List[Product], str]:
        try:
            result = self.scan_receipt(path=image_path, data=None)
            if result.is_err():
                return Err(f"Failed to scan receipt: {result.unwrap_err()}")

            scan_data = result.unwrap()
            if "products" not in scan_data:
                return Err("No products found in receipt scan result")

            products = []
            for item in scan_data["products"]:
                products.append(
                    Product(
                        name=item.get("name", ""),
                        quantity=self._clean_quantity(
                            str(item.get("quantity", "1 un")).strip()
                        ),
                        price=self._clean_price(str(item.get("price", "")).strip()),
                    )
                )
            return Ok(products)
        except Exception as e:
            return Err(f"Error extracting products: {str(e)}")

    def _clean_quantity(self, raw: str) -> str:
        cleaned = raw.lower().strip()
        cleaned = re.sub(r"^\d{1,3}\s+", "", cleaned)
        for bad, good in QUANTITY_OCR_FIXES.items():
            cleaned = cleaned.replace(bad, good)
        cleaned = re.sub(r"(\d)\s*9\b", r"\1g", cleaned)
        cleaned = cleaned.strip()
        if not cleaned or cleaned.isdigit():
            return f"{cleaned or '1'} un"
        if not re.search(r"\b(kg|g|un|lt|l|ml)\b", cleaned):
            cleaned = f"{cleaned} un"
        return cleaned

    def _clean_price(self, raw: str) -> str:
        cleaned = raw.strip()
        cleaned = re.sub(r"[^\d.,]", "", cleaned)
        cleaned = cleaned.replace(",", ".")
        if cleaned.count(".") > 1:
            parts = cleaned.split(".")
            cleaned = parts[0] + "." + "".join(parts[1:])
        return cleaned if cleaned else raw

    def _process_single_product(self, product: Product) -> ProcessedProduct:
        translation_result = self._translate_product_name(product.name)

        if translation_result.is_err():
            return ProcessedProduct(
                original_name=product.name,
                normalized_name=None,
                spanish_name=None,
                quantity=product.quantity,
                price=product.price,
                status="error",
                error=f"Translation failed: {translation_result.unwrap_err()}",
            )

        translation = translation_result.unwrap()

        storage_options, storage_debug = self._query_storage_info(
            translation.name,
            spanish_name=translation.name_spanish,
            packaging_hint=translation.packaging_hint,
        )

        if not storage_options and translation.name != product.name:
            storage_options, fallback_debug = self._query_storage_info(product.name)
            storage_debug["fallback_query"] = fallback_debug

        nutrition_info, nutrition_debug = self._query_nutrition_info(
            translation.name, product.name
        )

        status = "success"
        error = None
        if not storage_options:
            status = "warning"
            error = "No storage information found in database"

        return ProcessedProduct(
            original_name=product.name,
            normalized_name=translation.name,
            spanish_name=translation.name_spanish,
            quantity=product.quantity,
            price=product.price,
            storage_options=storage_options,
            nutrition_info=nutrition_info,
            status=status,
            error=error,
            debug_info={"storage": storage_debug, "nutrition": nutrition_debug},
        )

    def _translate_product_name(self, name: str) -> Result[TranslationResult, str]:
        if not name or not name.strip():
            return Err("Empty product name")
        try:
            result = self.translation.translate_to_english(name)
            if result.is_err():
                return Ok(TranslationResult(name=name))
            translation = result.unwrap()
            if len(translation.name) < 3:
                return Ok(TranslationResult(name=name))
            return result
        except Exception:
            return Ok(TranslationResult(name=name))

    def _query_storage_info(self, name, spanish_name=None, packaging_hint=None):
        debug = {"queries_tried": [], "candidates": [], "winner": None}
        try:
            if packaging_hint:
                opts = self._query_packaging_filtered(name, packaging_hint)
                if opts:
                    debug["queries_tried"].append(
                        f"{name} (packaging={packaging_hint})"
                    )
                    debug["winner"] = f"packaging_filtered({packaging_hint})"
                    return opts, debug

            candidates = []
            queries = [name]
            core = self._extract_core_food_term(name)
            if core and core.lower() != name.lower():
                queries.append(core)

            for query in queries:
                debug["queries_tried"].append(query)
                results = self.food_db.query_all(query, n_results=10)

                for coll_name, threshold in PRODUCT_COLLECTIONS:
                    coll_data = results.get(coll_name)
                    if not coll_data or not coll_data.get("documents"):
                        continue
                    dist = coll_data["distances"][0][0]
                    doc = coll_data["documents"][0][0]
                    if dist < threshold:
                        opts = self._extract_product_storage(
                            coll_data["metadatas"][0][0]
                        )
                        opts = self._apply_sanity_rules(name, opts)
                        if opts:
                            bonus = -0.03 if "foodkeeper_es" in coll_name else 0
                            adjusted = dist + bonus
                            candidates.append((adjusted, opts))
                            debug["candidates"].append(
                                {
                                    "collection": coll_name,
                                    "distance": round(dist, 4),
                                    "adjusted_distance": round(adjusted, 4),
                                    "document": doc[:120],
                                    "methods": [o.method for o in opts],
                                }
                            )

                fs_data = results.get("food_storage")
                if fs_data and fs_data.get("documents"):
                    fs_dist, fs_opts = self._collect_food_storage_options(fs_data, 0.70)
                    if fs_opts:
                        fs_opts = self._apply_sanity_rules(name, fs_opts)
                        if fs_opts:
                            candidates.append((fs_dist, fs_opts))
                            debug["candidates"].append(
                                {
                                    "collection": "food_storage",
                                    "distance": round(fs_dist, 4),
                                    "document": (
                                        fs_data.get("documents", [[]])[0] or [""]
                                    )[0][:120],
                                    "methods": [o.method for o in fs_opts],
                                }
                            )

            if spanish_name:
                debug["queries_tried"].append(f"{spanish_name} (foodkeeper_es direct)")
                fk_data = self.food_db.query(
                    "products_foodkeeper_es", spanish_name, n_results=3
                )
                if fk_data and fk_data.get("documents"):
                    dist = fk_data["distances"][0][0]
                    doc = fk_data["documents"][0][0]
                    if dist < 0.70:
                        opts = self._extract_product_storage(fk_data["metadatas"][0][0])
                        opts = self._apply_sanity_rules(name, opts)
                        if opts:
                            adjusted = dist - 0.03
                            candidates.append((adjusted, opts))
                            debug["candidates"].append(
                                {
                                    "collection": "products_foodkeeper_es (spanish direct)",
                                    "distance": round(dist, 4),
                                    "adjusted_distance": round(adjusted, 4),
                                    "document": doc[:120],
                                    "methods": [o.method for o in opts],
                                }
                            )

            if candidates:
                candidates = [
                    (d, o)
                    for d, o in candidates
                    if any(opt.duration_min > 0 or opt.duration_max > 0 for opt in o)
                ]
            if candidates:
                candidates.sort(key=lambda c: c[0])
                winner_dist, winner_opts = candidates[0]
                for c in debug["candidates"]:
                    if (
                        abs(c.get("adjusted_distance", c["distance"]) - winner_dist)
                        < 0.0001
                    ):
                        debug["winner"] = f"{c['collection']} ({c['distance']})"
                        break
                return winner_opts, debug

            return [], debug
        except Exception as e:
            debug["error"] = str(e)
            return [], debug

    def _query_packaging_filtered(self, name, packaging_hint):
        results = self.food_db.query(
            "food_storage", name, n_results=5, filters={"packaging": packaging_hint}
        )
        if not results or not results.get("documents"):
            return []

        options = []
        seen = set()
        for dist, meta in zip(results["distances"][0], results["metadatas"][0]):
            if dist >= 0.8:
                break
            storage = self._extract_food_storage_entry(meta)
            if storage and storage.method not in seen:
                options.append(storage)
                seen.add(storage.method)
        return options

    def _extract_core_food_term(self, name):
        name_lower = name.lower()
        for keyword, category in FOOD_CATEGORY_MAP.items():
            if keyword in name_lower:
                return category
        return None

    def _apply_sanity_rules(self, product_name, options):
        if not options:
            return options
        name_lower = product_name.lower()
        preferred_method = None
        for keyword, category in FOOD_CATEGORY_MAP.items():
            if keyword in name_lower:
                preferred_method = STORAGE_PREFERENCE.get(category)
                break
        if not preferred_method:
            return options
        preferred = [o for o in options if o.method == preferred_method]
        other = [o for o in options if o.method != preferred_method]
        return preferred + other

    def _extract_product_storage(self, metadata):
        options = []
        for method, can_flag, min_key, max_key, tips_key in [
            ("pantry", "can_pantry", "pantry_min", "pantry_max", "pantry_tips"),
            (
                "refrigerate",
                "can_refrigerate",
                "refrigerate_min",
                "refrigerate_max",
                "refrigerate_tips",
            ),
            ("freeze", "can_freeze", "freeze_min", "freeze_max", "freeze_tips"),
        ]:
            if metadata.get(can_flag):
                options.append(
                    StorageInfo(
                        method=method,
                        duration_min=metadata.get(min_key, -1),
                        duration_max=metadata.get(max_key, -1),
                        tips=metadata.get(tips_key, ""),
                    )
                )
        return options

    def _extract_food_storage_entry(self, metadata):
        method = metadata.get("storage_method")
        if not method:
            return None
        tips_parts = []
        if metadata.get("cooking_state"):
            tips_parts.append(f"State: {metadata['cooking_state']}")
        if metadata.get("packaging"):
            tips_parts.append(f"Packaging: {metadata['packaging']}")
        return StorageInfo(
            method=method,
            duration_min=metadata.get("duration_min", -1),
            duration_max=metadata.get("duration_max", -1),
            tips=" | ".join(tips_parts),
        )

    def _collect_food_storage_options(self, fs_results, threshold=0.70):
        raw_entries = []
        cooked_entries = []
        seen_raw = set()
        seen_cooked = set()
        raw_best_dist = 1.0
        cooked_best_dist = 1.0

        distances = fs_results.get("distances", [[]])[0]
        metadatas = fs_results.get("metadatas", [[]])[0]

        for dist, meta in zip(distances, metadatas):
            if dist >= threshold:
                break
            storage = self._extract_food_storage_entry(meta)
            if not storage:
                continue
            state = (meta.get("cooking_state") or "").strip().lower()
            is_raw = state in ("raw", "fresh", "")
            if is_raw and storage.method not in seen_raw:
                raw_entries.append(storage)
                seen_raw.add(storage.method)
                raw_best_dist = min(raw_best_dist, dist)
            elif storage.method not in seen_cooked:
                cooked_entries.append(storage)
                seen_cooked.add(storage.method)
                cooked_best_dist = min(cooked_best_dist, dist)

        if raw_entries:
            return raw_best_dist, raw_entries
        return cooked_best_dist + 0.05, cooked_entries

    def _query_nutrition_info(self, name, original_name=None):
        debug = {"queries_tried": [], "found": False}

        def not_found(q):
            return NutritionInfo(
                found=False,
                name=q,
                calories=None,
                proteins=None,
                carbohydrates=None,
                fats=None,
            )

        def try_find(q):
            try:
                result = self.find_by_text(q)
                if not result or not isinstance(result, list) or len(result) == 0:
                    return None
                product = result[0]
                nutriments = product.get("nutriments", {})
                calories = nutriments.get("energy-kcal_100g")
                if calories is None:
                    return None
                return NutritionInfo(
                    found=True,
                    name=product.get("product_name", q),
                    calories=calories,
                    proteins=nutriments.get("proteins_100g"),
                    carbohydrates=nutriments.get("carbohydrates_100g"),
                    fats=nutriments.get("fat_100g"),
                )
            except Exception as e:
                debug["queries_tried"].append(f"{q} -> error: {e}")
                return None

        debug["queries_tried"].append(name)
        result = try_find(name)
        if result:
            debug["found"] = True
            return result, debug

        if original_name and original_name != name:
            debug["queries_tried"].append(f"{original_name} (original)")
            result = try_find(original_name)
            if result:
                debug["found"] = True
                return result, debug

        words = name.split()
        if len(words) > 1:
            debug["queries_tried"].append(f"{words[0]} (first word)")
            result = try_find(words[0])
            if result:
                debug["found"] = True
                return result, debug

        return not_found(name), debug
