import base64
import json
import logging
import mimetypes
import os
import re
import sys
from typing import Any, Optional

import zai
from dotenv import load_dotenv

from .result import Err, Ok, Result

logger = logging.getLogger(__name__)

if not load_dotenv():
    print("Error: .env file not found or could not be loaded", file=sys.stderr)
    sys.exit(1)

api_key = os.getenv("ZAI_API_KEY")
if not api_key:
    print("Error: ZAI_API_KEY environment variable not set", file=sys.stderr)
    sys.exit(1)

client = zai.ZaiClient(api_key=api_key, base_url="https://api.z.ai/api/coding/paas/v4")


def encode_image(image_path):
    try:
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode("utf-8")
    except FileNotFoundError:
        raise ValueError(f"Image file not found: {image_path}")
    except PermissionError:
        raise ValueError(f"Permission denied reading file: {image_path}")


def scan_receipt(path: Optional[str], data: Optional[str]) -> Result[Any, str]:
    if path:
        data = encode_image(path)
    elif not data:
        return Err("Either path or data must be defined")

    result = client.chat.completions.create(
        model="glm-4.6V-flash",
        messages=[
            {
                "role": "system",
                "content": """
You are an expert receipt scanner specializing in Colombian grocery and supermarket receipts.
Extract every individual product line item from the receipt.

RULES:
1. Include ONLY actual purchased products — skip subtotals, totals, tax (IVA/IMPUESTO), change (CAMBIO), payment method, store name, date, register info, and any non-product lines.
2. If a single product appears on two lines (e.g. description on one line, price on the next), merge them into ONE entry.
3. Preserve the original product name EXACTLY as written on the receipt, including abbreviations and brand names.
4. QUANTITY EXTRACTION:
   - Look for the ACTUAL quantity purchased: "x2", "2 UN", "3 K", "1.5 KG", etc.
   - Line item numbers (01, 02, 03... at the start of a line) are NOT quantities — they are sequential item indices on the receipt. IGNORE them.
   - If the receipt shows weight like "1.000 KG" or "0.500 K", that IS the quantity.
   - Common Colombian units: KG/K (kilogram), UN (unit), GR (gram), LT (liter)
   - Common OCR errors to auto-correct: "k9" means "kg", "9" alone after a number often means "g"
   - If no real quantity is shown, use "1 un".
5. PRICE: Report the unitary price per item, NOT the line total. If only the line total is shown, divide by quantity.
6. If the text is ambiguous or partially unreadable, include your best interpretation — do not skip it.
7. Do NOT invent or hallucinate products that are not on the receipt.

Return the products in the following JSON format:
{
    "products": [
        {
            "name": "Exact product name AS IS in the receipt",
            "quantity": "Quantity with unit (e.g. '1 kg', '2 un', '500 g'). Default: '1 un'",
            "price": "Unitary price of the item"
        }
    ]
}
""",
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "Itemize every product on this receipt. Include all line items that are actual products, skip totals and tax.",
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{mimetypes.guess_type(path)[0] if path else 'image/jpeg'};base64,{data}",
                        },
                    },
                ],
            },
        ],
        response_format={"type": "json_object"},
    )

    raw_content = result.choices[0].message.content
    if not raw_content or not raw_content.strip():
        logger.error("Vision model returned empty content")
        return Err("Vision model returned empty response — receipt may be unreadable")

    parsed_result = _extract_json(raw_content)
    if parsed_result is not None:
        return Ok(parsed_result)

    logger.error("Could not extract JSON from vision response: %s", raw_content[:500])
    return Err("Couldn't decode receipt — model returned unparseable content")


def _extract_json(raw: str) -> Optional[dict]:
    """Robust JSON extraction from LLM output with multiple fallback strategies."""
    strategies = [
        _extract_json_fenced,
        _extract_json_brace,
        _extract_json_regex,
    ]
    for strategy in strategies:
        try:
            result = strategy(raw)
            if isinstance(result, dict):
                return result
        except (json.JSONDecodeError, ValueError, AttributeError):
            continue
    return None


def _extract_json_fenced(raw: str) -> dict:
    """Strip ```json / ``` fences, then try direct parse."""
    cleaned = re.sub(r"^```(?:json)?\s*\n?", "", raw.strip())
    cleaned = re.sub(r"\n?\s*```\s*$", "", cleaned)
    return json.loads(cleaned)


def _extract_json_brace(raw: str) -> dict:
    """Find outermost { ... }, capture everything between."""
    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("No braces found")
    block = raw[start : end + 1]
    return json.loads(block)


def _extract_json_regex(raw: str) -> dict:
    """Regex-based extraction: match balanced braces near the start."""
    stripped = raw.strip()
    # Find first { and find matching }
    depth = 0
    start = stripped.find("{")
    if start == -1:
        raise ValueError("No opening brace")
    for i, ch in enumerate(stripped[start:], start=start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                block = stripped[start : i + 1]
                return json.loads(block)
    raise ValueError("Unbalanced braces")
