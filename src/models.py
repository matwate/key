from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class Product:
    name: str
    quantity: str
    price: str


@dataclass
class StorageInfo:
    method: str
    duration_min: int
    duration_max: int
    tips: str


@dataclass
class NutritionInfo:
    found: bool
    name: str
    calories: Optional[int]
    proteins: Optional[float]
    carbohydrates: Optional[float]
    fats: Optional[float]


@dataclass
class ProcessedProduct:
    original_name: str
    normalized_name: Optional[str]
    spanish_name: Optional[str]
    quantity: str
    price: str
    storage_options: List[StorageInfo] = field(default_factory=list)
    nutrition_info: Optional[NutritionInfo] = None
    status: str = "success"
    error: Optional[str] = None
    debug_info: Optional[Dict[str, Any]] = None


@dataclass
class ReceiptAnalysis:
    total_items: int
    products: List[ProcessedProduct]
