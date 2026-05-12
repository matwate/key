from __future__ import annotations

import re
import unicodedata
from typing import Dict, Optional

from .models import StorageInfo


COLOMBIAN_QUICK_LOOKUP = [
    {"name": "CARAM BARRILETEX120G", "normalized_name": "Caramel Candy", "pantry_shelf_life_days": 365, "fridge_shelf_life_days": 365, "freezer_shelf_life_days": 730},
    {"name": "GAS KOLA ROMAN 1.5L", "normalized_name": "Kola Roman Soda", "pantry_shelf_life_days": 180, "fridge_shelf_life_days": 365, "freezer_shelf_life_days": None},
    {"name": "GOMA TRULU GUS X70G", "normalized_name": "Gummy Candy", "pantry_shelf_life_days": 365, "fridge_shelf_life_days": 365, "freezer_shelf_life_days": 730},
    {"name": "NATUCHIPS MADUR 135G", "normalized_name": "Plantain Chips", "pantry_shelf_life_days": 90, "fridge_shelf_life_days": 120, "freezer_shelf_life_days": 180},
    {"name": "PBOCA NATUCHIPS", "normalized_name": "Plantain Chips (Small Bag)", "pantry_shelf_life_days": 90, "fridge_shelf_life_days": 120, "freezer_shelf_life_days": 180},
    {"name": "AVENA MEDALLA ORO", "normalized_name": "Oatmeal (Medalla Oro)", "pantry_shelf_life_days": 365, "fridge_shelf_life_days": 365, "freezer_shelf_life_days": 730},
    {"name": "PALOM MAIZ ACT II", "normalized_name": "Microwave Popcorn", "pantry_shelf_life": 365, "fridge_shelf_life_days": 365, "freezer_shelf_life_days": 730},
    {"name": "AVENA QUAKER S/GLU", "normalized_name": "Quaker Oatmeal (Sugar-Free)", "pantry_shelf_life_days": 365, "fridge_shelf_life_days": 365, "freezer_shelf_life_days": 730},
    {"name": "QSO MOZAR COLANTA", "normalized_name": "Mozzarella Cheese", "pantry_shelf_life_days": None, "fridge_shelf_life_days": 14, "freezer_shelf_life_days": 180},
    {"name": "ATUN VAN CAMPS A/A", "normalized_name": "Tuna in Vegetable Oil", "pantry_shelf_life_days": 730, "fridge_shelf_life_days": 730, "freezer_shelf_life_days": None},
    {"name": "HUEVO AAA RJO 15UN", "normalized_name": "Red Eggs (15 units)", "pantry_shelf_life_days": None, "fridge_shelf_life_days": 35, "freezer_shelf_life_days": 180},
    {"name": "TOCINETA ZENU CERD", "normalized_name": "Pork Bacon", "pantry_shelf_life_days": None, "fridge_shelf_life_days": 7, "freezer_shelf_life_days": 90},
    {"name": "PASTA ESPAG DORIA", "normalized_name": "Spaghetti Pasta", "pantry_shelf_life_days": 730, "fridge_shelf_life_days": 730, "freezer_shelf_life_days": 730},
    {"name": "BANAN GRL", "normalized_name": "Bananas", "pantry_shelf_life_days": 5, "fridge_shelf_life_days": 7, "freezer_shelf_life_days": 90},
    {"name": "RES BOLLO/MUCHACHO", "normalized_name": "Beef Eye of Round", "pantry_shelf_life_days": None, "fridge_shelf_life_days": 3, "freezer_shelf_life_days": 365},
    {"name": "POLLO PECHUGA BUCA", "normalized_name": "Chicken Breast", "pantry_shelf_life_days": None, "fridge_shelf_life_days": 2, "freezer_shelf_life_days": 270},
    {"name": "REFRESCO HIT MANGO", "normalized_name": "Mango Juice Drink", "pantry_shelf_life_days": 180, "fridge_shelf_life_days": 365, "freezer_shelf_life_days": None},
    {"name": "TUMECITOS LA DELIC", "normalized_name": "Small Bread Rolls (Tumecitos)", "pantry_shelf_life_days": 3, "fridge_shelf_life_days": 7, "freezer_shelf_life_days": 180},
    {"name": "PAN TAJ MANTQ '0'", "normalized_name": "Sliced Butter Bread", "pantry_shelf_life_days": 5, "fridge_shelf_life_days": 14, "freezer_shelf_life_days": 180},
    {"name": "ARVEJA DESGRANADA", "normalized_name": "Shelled Peas", "pantry_shelf_life_days": None, "fridge_shelf_life_days": 5, "freezer_shelf_life_days": 365},
    {"name": "REPOLLO BLANCO", "normalized_name": "White Cabbage", "pantry_shelf_life_days": None, "fridge_shelf_life_days": 14, "freezer_shelf_life_days": 180},
    {"name": "ZUQUINI VERDE", "normalized_name": "Green Zucchini", "pantry_shelf_life_days": None, "fridge_shelf_life_days": 7, "freezer_shelf_life_days": 90},
    {"name": "CEBOLLA LARGA C83", "normalized_name": "Long Onion (Green Onion)", "pantry_shelf_life_days": None, "fridge_shelf_life_days": 10, "freezer_shelf_life_days": 180},
    {"name": "ESPINACA", "normalized_name": "Spinach", "pantry_shelf_life_days": None, "fridge_shelf_life_days": 5, "freezer_shelf_life_days": 365},
    {"name": "LECHUGA CRESPA", "normalized_name": "Curly Lettuce/Romaine", "pantry_shelf_life_days": None, "fridge_shelf_life_days": 7, "freezer_shelf_life_days": None},
    {"name": "CEBOLLA CABEZONA", "normalized_name": "Large Onion", "pantry_shelf_life_days": 30, "fridge_shelf_life_days": 60, "freezer_shelf_life_days": 365},
    {"name": "ZANAHORIA", "normalized_name": "Carrots", "pantry_shelf_life_days": None, "fridge_shelf_life_days": 21, "freezer_shelf_life_days": 365},
    {"name": "HABICHUELA", "normalized_name": "Green Beans", "pantry_shelf_life_days": None, "fridge_shelf_life_days": 5, "freezer_shelf_life_days": 365},
    {"name": "MANZANA VERDE PAQUETE", "normalized_name": "Green Apples (Package)", "pantry_shelf_life_days": 7, "fridge_shelf_life_days": 30, "freezer_shelf_life_days": 365},
    {"name": "LIMON", "normalized_name": "Lemon", "pantry_shelf_life_days": 7, "fridge_shelf_life_days": 30, "freezer_shelf_life_days": 180},
    {"name": "PIMENTON", "normalized_name": "Bell Pepper", "pantry_shelf_life_days": None, "fridge_shelf_life_days": 10, "freezer_shelf_life_days": 180},
    {"name": "TOMATE DE ARBOL", "normalized_name": "Tree Tomato (Tamarillo)", "pantry_shelf_life_days": None, "fridge_shelf_life_days": 7, "freezer_shelf_life_days": 180},
    {"name": "GUAYABA PAQUETE", "normalized_name": "Guava (Package)", "pantry_shelf_life_days": 3, "fridge_shelf_life_days": 7, "freezer_shelf_life_days": 365},
    {"name": "LULO PAQUETE", "normalized_name": "Lulo Fruit (Naranjilla) (Package)", "pantry_shelf_life_days": 3, "fridge_shelf_life_days": 7, "freezer_shelf_life_days": 365},
    {"name": "AGUACATE PAQUETE", "normalized_name": "Avocado (Package)", "pantry_shelf_life_days": 4, "fridge_shelf_life_days": 7, "freezer_shelf_life_days": 180},
    {"name": "TOMATE CHONTO PAQUETE", "normalized_name": "Plum Tomatoes (Package)", "pantry_shelf_life_days": None, "fridge_shelf_life_days": 7, "freezer_shelf_life_days": 180},
    {"name": "BANANO CRIOLLO", "normalized_name": "Criollo Banana/Plantain", "pantry_shelf_life_days": 5, "fridge_shelf_life_days": 7, "freezer_shelf_life_days": 90},
    {"name": "TOMATE CHONTO", "normalized_name": "Plum Tomato", "pantry_shelf_life_days": None, "fridge_shelf_life_days": 7, "freezer_shelf_life_days": 180},
    {"name": "CHAMPINON TAJADO", "normalized_name": "Sliced Mushrooms", "pantry_shelf_life_days": None, "fridge_shelf_life_days": 5, "freezer_shelf_life_days": 180},
    {"name": "RAICES CHINAS", "normalized_name": "Chinese Roots (Ginger)", "pantry_shelf_life_days": 21, "fridge_shelf_life_days": 30, "freezer_shelf_life_days": 365},
    {"name": "GALLETA FESTIVAL", "normalized_name": "Festival Cookies", "pantry_shelf_life_days": 180, "fridge_shelf_life_days": 180, "freezer_shelf_life_days": 365},
    {"name": "MEZC BREVEDA 2.5L", "normalized_name": "Beverage Mix (Breveda)", "pantry_shelf_life_days": 365, "fridge_shelf_life_days": 365, "freezer_shelf_life_days": None},
    {"name": "TE INST OLIMPICA", "normalized_name": "Instant Tea (Olimpica)", "pantry_shelf_life_days": 730, "fridge_shelf_life_days": 730, "freezer_shelf_life_days": 730},
    {"name": "ARROZ DIANA 5 KG", "normalized_name": "Diana Rice (5kg)", "pantry_shelf_life_days": 730, "fridge_shelf_life_days": 730, "freezer_shelf_life_days": 1095},
    {"name": "ACEITE PREMIER GIR", "normalized_name": "Premier Cooking Oil", "pantry_shelf_life_days": 365, "fridge_shelf_life_days": 365, "freezer_shelf_life_days": None},
    {"name": "BDILLO VELED SN AN", "normalized_name": "Snack Item (Veled)", "pantry_shelf_life_days": 180, "fridge_shelf_life_days": 180, "freezer_shelf_life_days": 365},
    {"name": "JAMON ZENU SANDUCH", "normalized_name": "Sandwich Ham (Zenu)", "pantry_shelf_life_days": None, "fridge_shelf_life_days": 7, "freezer_shelf_life_days": 60},
    {"name": "PAN MANTEQ GUADALUPE", "normalized_name": "Guadalupe Butter Bread", "pantry_shelf_life_days": 5, "fridge_shelf_life_days": 14, "freezer_shelf_life_days": 180},
    {"name": "PAN INTEG GUADALUP", "normalized_name": "Guadalupe Whole Wheat Bread", "pantry_shelf_life_days": 5, "fridge_shelf_life_days": 14, "freezer_shelf_life_days": 180},
    {"name": "PAN MOGOLL GUADALU", "normalized_name": "Guadalupe Mogoll Bread", "pantry_shelf_life_days": 5, "fridge_shelf_life_days": 14, "freezer_shelf_life_days": 180},
    {"name": "TOST GUADALUPE INT", "normalized_name": "Guadalupe Whole Wheat Toast", "pantry_shelf_life_days": 180, "fridge_shelf_life_days": 180, "freezer_shelf_life_days": 365},
    {"name": "LECHE UHT COLANTA", "normalized_name": "Colanta UHT Milk", "pantry_shelf_life_days": 180, "fridge_shelf_life_days": 180, "freezer_shelf_life_days": 180},
    {"name": "PECHUG C/P MERCAPO", "normalized_name": "Seasoned Chicken Breast", "pantry_shelf_life_days": None, "fridge_shelf_life_days": 2, "freezer_shelf_life_days": 270},
]


COLOMBIAN_QUICK_ALIASES = {
    "AGUCATE PAQUETE": "AGUACATE PAQUETE",
    "ARROZ DIANA 6 KG": "ARROZ DIANA 5 KG",
    "ARVEJA DEGRANADA": "ARVEJA DESGRANADA",
    "ARVEJA DESGRANADA": "ARVEJA DESGRANADA",
    "CHAMPION TAJADO": "CHAMPINON TAJADO",
    "GAS KOLA RÓMAN 1.5L": "GAS KOLA ROMAN 1.5L",
    "GAS KOLA ROMAN 1.5 L": "GAS KOLA ROMAN 1.5L",
    "MEZC BRETADA 2.5 L": "MEZC BREVEDA 2.5L",
    "MEZC BRETADA 2.5L": "MEZC BREVEDA 2.5L",
    "PAN MANTEQ GUADALU": "PAN MANTEQ GUADALUPE",
    "PAN TAJ MANTQ 'O'": "PAN TAJ MANTQ '0'",
    "RAICES CIINAS": "RAICES CHINAS",
    "7ANAHORIA": "ZANAHORIA",
}


def _normalize_key(name: str) -> str:
    normalized = unicodedata.normalize("NFKD", name.upper().strip())
    normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    normalized = re.sub(r"[^A-Z0-9]+", " ", normalized)
    return re.sub(r"\s+", " ", normalized).strip()


class ColombianFastStorageIndex:
    def __init__(self) -> None:
        self._by_name: Dict[str, dict] = {}
        for row in COLOMBIAN_QUICK_LOOKUP:
            self._by_name[_normalize_key(row["name"])] = row
        for alias, canonical in COLOMBIAN_QUICK_ALIASES.items():
            row = self._by_name.get(_normalize_key(canonical))
            if row:
                self._by_name[_normalize_key(alias)] = row
        self._keys_by_length = sorted(self._by_name.keys(), key=len, reverse=True)

    def lookup(self, raw_name: str) -> Optional[dict]:
        query = _normalize_key(raw_name)
        exact = self._by_name.get(query)
        if exact:
            return exact
        for key in self._keys_by_length:
            if key and key in query:
                return self._by_name[key]
        return None

    def to_storage_options(self, row: dict) -> list[StorageInfo]:
        pantry = row.get("pantry_shelf_life_days", row.get("pantry_shelf_life"))
        fridge = row.get("fridge_shelf_life_days")
        freezer = row.get("freezer_shelf_life_days")

        options: list[StorageInfo] = []
        if pantry is not None:
            options.append(
                StorageInfo(
                    method="pantry",
                    duration_min=int(pantry),
                    duration_max=int(pantry),
                    tips="Colombian quick lookup",
                )
            )
        if fridge is not None:
            options.append(
                StorageInfo(
                    method="refrigerate",
                    duration_min=int(fridge),
                    duration_max=int(fridge),
                    tips="Colombian quick lookup",
                )
            )
        if freezer is not None:
            options.append(
                StorageInfo(
                    method="freeze",
                    duration_min=int(freezer),
                    duration_max=int(freezer),
                    tips="Colombian quick lookup",
                )
            )
        return options
