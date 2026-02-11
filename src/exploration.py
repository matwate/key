import base64
import json
import mimetypes
import os
import sys
from datetime import date
from typing import Any, Optional

import zai
from dotenv import load_dotenv

from result import Err, Ok, Result

if not load_dotenv():
    print("Error: .env file not found or could not be loaded", file=sys.stderr)
    sys.exit(1)

api_key = os.getenv("ZAI_API_KEY")
if not api_key:
    print("Error: ZAI_API_KEY environment variable not set", file=sys.stderr)
    sys.exit(1)

client = zai.ZaiClient(api_key=api_key)


def encode_image(image_path):
    try:
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode("utf-8")
    except FileNotFoundError:
        raise ValueError(f"Image file not found: {image_path}")
    except PermissionError:
        raise ValueError(f"Permission denied reading file: {image_path}")


def describe_image(path: Optional[str], data: Optional[str]) -> Result[Any, str]:
    # Convert it to something sendable.
    if path:
        data = encode_image(path)
    elif data:
        pass
    else:
        return Err("Either path or data must be defined")

    # Get the current date

    date_str = date.today().isoformat()

    # Read API Key from environment variable

    result = client.chat.completions.create(
        model="glm-4.6V-flash",
        messages=[
            {
                "role": "system",
                "content": """
                You are a food expiry and scene analysis  expert. ALL ANSWERS MUST BE IN SPANISH, FOCUS SPECIALLY ON FOOD ITEMS
                Please return the analysis results in the following JSON format:
                {
                    "objects": [
                        {
                            "name": "Nombre del objeto en la escena",
                            "quantity": "Cantidad del objeto especificado en la escena",
                            "possible_expiry": "Si aplica y se compró el dia: ### , ¿cuándo expiraría como una fecha en formato YYYY-MM-DD, o null si no aplica"
                        }
                    ]
                }
                """.replace(
                    "###", date_str
                ),
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "Describe esta imagen lo mejor que puedas",
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
        parsed_result = json.loads(result.choices[0].message.content)  # type: ignore
    except json.decoder.JSONDecodeError:
        print(result.choices[0].message.content)
        return Err("Couldn't decode API response")
    print(parsed_result)
    return Ok(parsed_result)


def scan_receipt(path: Optional[str], data: Optional[str]) -> Result[Any, str]:
    # Convert it to something sendable.
    if path:
        data = encode_image(path)
    elif data:
        data = data
    else:
        return Err("Either path or data must be defined")

    # Get the current date

    # Read API Key from environment variable

    result = client.chat.completions.create(
        model="glm-4.6V-flash",
        messages=[
            {
                "role": "system",
                "content": """
                You are a PERFECT Receipt Scanner 
                Please return the products in the following JSON format:
                {
                    "products": [
                        {
                            "name": "Name of the product bought AS IS in the receipt", 
                            "quantity": "Quantity of the product specified in the receipt",
                            "price": "Unitary price of the item in question" 
                        }
                    ]
                }
                """,
            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Itemize this receipt"},
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

    # Parse the JSON response - ignore type hints for now
    try:
        parsed_result = json.loads(result.choices[0].message.content)  # type: ignore
    except json.decoder.JSONDecodeError:
        print(result.choices[0].message.content)
        return Err("Couldn't decode this")

    return Ok(parsed_result)


"""
description = describe_image(path="./src/testassets/image.jpg", data=None).unwrap()

print("Objetos encontrados:")
for obj in description["objects"]:
    print(f"  - Nombre: {obj['name']}")
    print(f"    Cantidad: {obj['quantity']}")
    print(f"    Posible fecha de expiración: {obj['possible_expiry']}")
    print()
"""

items = scan_receipt(path="./src/testassets/receipt.jpeg", data=None)

if items.is_ok():
    print("Objetos encontrados:")
    for obj in items.value["products"]:
        print(f"  - Nombre: {obj['name']}")
        print(f"    Cantidad: {obj['quantity']}")
        print(f"    Precio Unitario: {obj['price']}")
        print()
