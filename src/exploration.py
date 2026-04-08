import base64
import json
import mimetypes
import os
import sys
from typing import Any, Optional

import zai
from dotenv import load_dotenv

from .result import Err, Ok, Result

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

    try:
        content = result.choices[0].message.content

        start_idx = content.find("{")
        end_idx = content.rfind("}")

        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
            content = content[start_idx : end_idx + 1]

        parsed_result = json.loads(content)
    except json.decoder.JSONDecodeError as e:
        print(f"JSON Decode Error: {e}")
        print(f"Content: {result.choices[0].message.content}")
        return Err("Couldn't decode this")

    return Ok(parsed_result)
