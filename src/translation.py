import json
import os
import re
from dataclasses import dataclass
from typing import Optional

import zai
from dotenv import load_dotenv

from .result import Err, Ok, Result


@dataclass
class TranslationResult:
    name: str
    name_spanish: Optional[str] = None
    packaging_hint: Optional[str] = None
    volume_hint: Optional[str] = None


class TranslationService:
    """Enhanced service for translating and normalizing Colombian grocery items"""

    COLOMBIAN_BRANDS = {
        "ALQUERIA",
        "POSTOBON",
        "COLCAFÉ",
        "NUTELLA",
        "TRULU",
        "GUS",
        "BIMBO",
        "NOELLA",
        "FESTIVAL",
        "KOLINO",
        "PASTAS DORIA",
        "DOÑA GALLINA",
        "MEDELLIN",
        "COLOMBINA",
        "LACTEOS",
        "PASTAS",
        "ALIMENTOS",
    }

    PRODUCT_CODE_PATTERNS = [
        r"\b\d+[Xx]\d+[Gg]\b",
        r"\b\d+[GgKkLl]\b",
        r"\b[A-Z]{1,3}\d{3,}\b",
        r"\bL\s*\d+\b",
        r"\bML\b",
        r"\bGR\b",
        r"\bLT\b",
    ]

    COLOMBIAN_FOOD_TERMS = {
        "GOMA": "gummy candy",
        "GOMITAS": "gummy candy",
        "BOMBONES": "chocolates",
        "CHICLE": "gum",
        "MELCOCHA": "hard candy",
        "HUEVOS": "eggs",
        "AREPAS": "arepas",
        "PAN": "bread",
        "LECHE": "milk",
        "QUESO": "cheese",
        "CARNE": "beef",
        "POLLO": "chicken",
        "PESCADO": "fish",
        "FRUTAS": "fruits",
        "VERDURAS": "vegetables",
        "ARROZ": "rice",
        "AZUCAR": "sugar",
        "ACEITE": "oil",
        "SAL": "salt",
        "CAFE": "coffee",
        "TE": "tea",
        "JUGO": "juice",
        "YOGURT": "yogurt",
        "MANTEQUILLA": "butter",
        "REFRESCO": "soda",
        "GASEOSA": "soda",
        "CERVEZA": "beer",
        "VINAGRE": "vinegar",
    }

    VOLUME_PACKAGING_RULES = {
        "can_sizes_ml": {250, 330, 355, 375, 473, 500},
    }

    def __init__(self, api_key: Optional[str] = None):
        """Initialize translation service with ZAI API key"""
        if not api_key:
            load_dotenv()
            api_key = os.getenv("ZAI_API_KEY")

        if not api_key:
            raise ValueError("ZAI_API_KEY environment variable not set")

        self.client = zai.ZaiClient(
            api_key=api_key, base_url="https://api.z.ai/api/coding/paas/v4"
        )
        self.api_key = api_key

    def _extract_packaging_hints(self, text: str) -> dict:
        text_upper = text.upper()
        hints = {}

        volume_match = re.search(r"(\d+(?:\.\d+)?)\s*(L|ML|LT|LTR|CC)\b", text_upper)
        if volume_match:
            volume_str = volume_match.group(0)
            number = float(volume_match.group(1))
            unit = volume_match.group(2)
            hints["volume_hint"] = volume_str.lower()

            if unit in ("L", "LT", "LTR"):
                if number >= 1.0:
                    hints["packaging_hint"] = "bottled"
                else:
                    hints["packaging_hint"] = "bottled"
            elif unit == "ML":
                if number in self.VOLUME_PACKAGING_RULES["can_sizes_ml"]:
                    hints["packaging_hint"] = "canned"
                elif number >= 600:
                    hints["packaging_hint"] = "bottled"

        packaging_spanish = {
            "LATA": "canned",
            "BOTELLA": "bottled",
            "BOTE": "bottled",
            "CAJA": "packaged",
            "PAQUETE": "packaged",
            "BOLSA": "bagged",
            "SOBRE": "packaged",
            "FRASCO": "jarred",
            "TETRA": "packaged",
            "VIDRIO": "bottled",
            "RETORNABLE": "bottled",
            "PET": "bottled",
        }
        for spanish, english in packaging_spanish.items():
            if spanish in text_upper:
                hints["packaging_hint"] = english
                break

        return hints

    def translate_to_english(self, text: str) -> Result[TranslationResult, str]:
        """Translate and normalize text to English with fallback strategies

        Args:
            text: Text to translate

        Returns:
            Result containing translated/normalized English text or error message
        """
        if not text or not text.strip():
            return Err("Empty text provided")

        text = text.strip()

        # Step 0: Extract packaging hints BEFORE any preprocessing strips them
        packaging_hints = self._extract_packaging_hints(text)

        # Step 1: Check if text is already English
        if self._is_likely_english(text):
            return Ok(
                TranslationResult(
                    name=text,
                    name_spanish=None,
                    packaging_hint=packaging_hints.get("packaging_hint"),
                    volume_hint=packaging_hints.get("volume_hint"),
                )
            )

        # Step 3: Pre-process text (remove codes, preserve essential info)
        preprocessed = self._preprocess_text(text)

        # Step 4: Try translation with enhanced context
        result = self._call_zai_translation(preprocessed, original=text)

        if result.is_err():
            local_result = self._try_local_normalization(text, packaging_hints)
            if local_result:
                return Ok(local_result)
            return result

        translation_data = result.unwrap()

        english_name = translation_data.get("english", "")
        spanish_name = translation_data.get("spanish")

        # Step 5: Post-process translation
        final_result = self._postprocess_translation(
            english_name, original=text, packaging_hints=packaging_hints
        )

        if spanish_name:
            final_result.name_spanish = spanish_name.lower().strip()

        if not final_result or not final_result.name.strip():
            return Err("Empty translation result")

        return Ok(final_result)

    def _try_local_normalization(
        self, text: str, packaging_hints: dict
    ) -> Optional[TranslationResult]:
        """Try local normalization dictionary for instant results

        Args:
            text: Text to normalize
            packaging_hints: Pre-extracted packaging hints

        Returns:
            TranslationResult or None if no match
        """
        text_upper = text.upper()

        for spanish, english in self.COLOMBIAN_FOOD_TERMS.items():
            if spanish in text_upper:
                if len(spanish) / len(text) > 0.2:
                    return TranslationResult(
                        name=english,
                        name_spanish=spanish.lower(),
                        packaging_hint=packaging_hints.get("packaging_hint"),
                        volume_hint=packaging_hints.get("volume_hint"),
                    )

        return None

    def _preprocess_text(self, text: str) -> str:
        """Pre-process text to remove product codes while preserving brands

        Args:
            text: Original text

        Returns:
            Cleaned text ready for translation
        """
        cleaned = text

        # Remove product code patterns
        for pattern in self.PRODUCT_CODE_PATTERNS:
            cleaned = re.sub(pattern, "", cleaned)

        # Clean up extra spaces and special characters
        cleaned = re.sub(r"\s+", " ", cleaned)
        cleaned = re.sub(r"[^\w\s]", " ", cleaned)
        cleaned = cleaned.strip()

        return cleaned if cleaned else text

    def _postprocess_translation(
        self, translated: str, original: str, packaging_hints: dict
    ) -> TranslationResult:
        """Post-process translation to ensure quality

        Args:
            translated: Translated text
            original: Original text
            packaging_hints: Pre-extracted packaging hints

        Returns:
            TranslationResult with cleaned name and packaging info
        """
        for pattern in self.PRODUCT_CODE_PATTERNS:
            translated = re.sub(pattern, "", translated)

        translated = re.sub(r"\s+", " ", translated)
        translated = translated.strip()

        ai_packaging = None
        for keyword in ["bottled", "canned", "jarred", "boxed", "bagged", "packaged"]:
            if keyword in translated.lower():
                ai_packaging = keyword
                translated = re.sub(
                    r",?\s*" + keyword, "", translated, flags=re.IGNORECASE
                ).strip()
                break

        final_packaging = ai_packaging or packaging_hints.get("packaging_hint")

        if len(translated) < 3:
            for spanish_term, english_term in self.COLOMBIAN_FOOD_TERMS.items():
                if spanish_term in original.upper():
                    return TranslationResult(
                        name=english_term,
                        name_spanish=spanish_term.lower(),
                        packaging_hint=final_packaging
                        or packaging_hints.get("packaging_hint"),
                        volume_hint=packaging_hints.get("volume_hint"),
                    )
            return TranslationResult(
                name=original,
                name_spanish=None,
                packaging_hint=final_packaging or packaging_hints.get("packaging_hint"),
                volume_hint=packaging_hints.get("volume_hint"),
            )

        return TranslationResult(
            name=translated,
            packaging_hint=final_packaging,
            volume_hint=packaging_hints.get("volume_hint"),
        )

    def _is_likely_english(self, text: str) -> bool:
        """Enhanced heuristic to check if text is likely English"""
        # Check for common non-English characters (accents, special characters)
        non_english_chars = set("áéíóúàèìòùäëïöüãõâêîôûñç¿¡")

        # If text has many non-English characters, likely not English
        non_english_count = sum(1 for c in text.lower() if c in non_english_chars)
        if non_english_count > len(text) * 0.3:
            return False

        # Check for Colombian brands (indicates Spanish)
        text_upper = text.upper()
        for brand in self.COLOMBIAN_BRANDS:
            if brand in text_upper:
                return False

        # Check for common English words (expanded list)
        common_english_words = {
            "the",
            "and",
            "for",
            "are",
            "but",
            "not",
            "you",
            "all",
            "can",
            "milk",
            "cheese",
            "bread",
            "water",
            "juice",
            "coffee",
            "tea",
            "egg",
            "sugar",
            "salt",
            "pepper",
            "butter",
            "oil",
            "rice",
            "pasta",
            "chicken",
            "beef",
            "pork",
            "fish",
            "fruit",
            "vegetables",
            "candy",
            "gummy",
            "chocolate",
            "cookie",
            "cracker",
            "chips",
        }

        words = text.lower().split()
        english_word_count = sum(1 for word in words if word in common_english_words)

        # If >30% of words are common English words, likely English
        if words and english_word_count / len(words) > 0.3:
            return True

        return False

    def _call_zai_translation(self, text: str, original: str) -> Result[dict, str]:
        try:
            result = self.client.chat.completions.create(
                model="glm-5-turbo",
                messages=[
                    {
                        "role": "system",
                        "content": """You are an expert translator specializing in Colombian grocery items and food products.

Your job is to take a raw product name from a Colombian supermarket receipt and produce TWO outputs:
1. A normalized SPANISH food name (what this product would commonly be called in Spanish)
2. A normalized ENGLISH food name (the equivalent in English)

IMPORTANT RULES:
1. Context: Colombian grocery items from supermarkets, receipts, and stores.
2. SPECIFICITY: Preserve cut of meat, preparation type, and form. Do NOT over-generalize.
   BUT: Do NOT assume flavors, colors, or varieties when the original doesn't specify them.
3. Remove brands: ALQUERIA, POSTOBON, TRULU, GUS, BIMBO, NOELLA, FESTIVAL, KOLINO, PASTAS DORIA, DOÑA GALLINA, COLOMBINA, VAN CAMPS, HIT, etc.
4. Ignore product codes: X70G, 120G, 1K, L, ML, GR, LT, A/A, AAA, 15UN, etc.
5. Shell color for eggs (RJO/rojo, blanco) is NOT a distinct product — just use "huevos"/"eggs".
6. Include packaging type ONLY when clearly indicated: "enlatado"/"canned", "embotellado"/"bottled", etc.
7. Do NOT guess flavors. "TUMECITOS" is a candy brand name — if flavor isn't stated, just say "caramelos"/"candy".
8. BOLLO in Colombian butcher context = a type of sausage/meat product. MUCHACHO = a beef cut.

TRANSLATION EXAMPLES:
- "HUEVO AAA RJO 15UN" → spanish: "huevos", english: "eggs"
- "RES BOLLO/MUCHACHO" → spanish: "salchicha de res", english: "beef sausage"
- "POLLO PECHUGA BUCA" → spanish: "pechuga de pollo", english: "chicken breast"
- "REFRESCO HIT MANGO" → spanish: "refresco de mango", english: "mango soda"
- "ATUN VAN CAMPS A/A" → spanish: "atún enlatado en aceite", english: "canned tuna in oil"
- "TUMECITOS LA DELIC" → spanish: "caramelos", english: "candy"
- "PAN TAJ MANTQ 'O'" → spanish: "pan tajado con mantequilla", english: "sliced bread with butter"
- "BANAN GRL" → spanish: "banano", english: "banana"
- "LECHE ENTERA 1L" → spanish: "leche entera", english: "whole milk"
- "LECHE DESLACTOSADA" → spanish: "leche deslactosada", english: "lactose-free milk"
- "QUESO FRESCO" → spanish: "queso fresco", english: "fresh cheese"
- "CARNE MOLIDA" → spanish: "carne molida", english: "ground beef"
- "ARROZ ROA 500G" → spanish: "arroz", english: "rice"
- "GASEOSA COCA-COLA 1.5L" → spanish: "gaseosa", english: "cola soda"
- "CERVEZA BAVARIA 350ML" → spanish: "cerveza", english: "beer"

WRONG vs RIGHT:
- "HUEVO RJO" → "huevos"/"eggs" NOT "huevos rojos"/"red eggs"
- "TUMECITOS LA DELIC" → "caramelos"/"candy" NOT "caramelos de guayaba"/"guava candy"
- "POLLO PECHUGA" → "pechuga de pollo"/"chicken breast" NOT "pollo"/"chicken"
- "ATUN VAN CAMPS A/A" → "atún enlatado en aceite"/"canned tuna in oil" NOT "atún"/"tuna"
- "PAN TAJADO" → "pan tajado"/"sliced bread" NOT "pan"/"bread"

OUTPUT FORMAT — Return ONLY valid JSON, nothing else:
{"spanish": "normalized spanish name", "english": "normalized english name"}

Colombian grocery terms:
- GOMA/GOMITAS = gummy candy (NOT rubber!)
- BOMBONES = chocolates/candies
- HUEVO/HUEVOS = eggs
- AREPAS = arepas (keep as is)
- QUESO = cheese
- CARNE/RES = beef
- POLLO = chicken
- PECHUGA = breast (meat cut)
- BOLLO = Colombian sausage/steamed food
- MUCHACHO = beef cut
- GASEOSA/REFRESCO = soda
- TAJADO/TAJ = sliced
- MANTQ = butter (mantequilla)
- RJO = red (rojo)
- A/A = in oil (al aceite)
- BUCA = boneless (deshuesado)
- GRL = regular/grande
- UN = units
""",
                    },
                    {
                        "role": "user",
                        "content": f"""Original text: "{original}"
Cleaned text: "{text}"

Return the Spanish and English normalized names as JSON.""",
                    },
                ],
                temperature=0.2,
                response_format={"type": "json_object"},
            )

            raw = result.choices[0].message.content.strip()

            try:
                parsed = json.loads(raw)
                return Ok(parsed)
            except json.JSONDecodeError:
                start = raw.find("{")
                end = raw.rfind("}")
                if start != -1 and end != -1:
                    parsed = json.loads(raw[start : end + 1])
                    return Ok(parsed)
                return Ok({"english": raw, "spanish": None})

        except Exception as e:
            return Err(f"ZAI API error: {str(e)}")
