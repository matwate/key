import base64
import json
import os
from datetime import date

import zai
from dotenv import load_dotenv

if not load_dotenv():
    exit(0)


def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")


# Load an image
IMAGE_PATH = "./src/testassets/image.jpg"

# Convert it to something sendable.
data = encode_image(IMAGE_PATH)

# Get the current date

date_str = date.today().isoformat()


# Read API Key from environment variable
client = zai.ZaiClient(api_key=os.getenv("ZAI_API_KEY"))


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
                {"type": "text", "text": "Describe esta imagen lo mejor que puedas"},
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{data}",
                    },
                },
            ],
        },
    ],
    response_format={"type": "json_object"},
)

# Parse the JSON response - ignore type hints for now
parsed_result = json.loads(result.choices[0].message.content)  # type: ignore

print("Objetos encontrados:")
for obj in parsed_result["objects"]:
    print(f"  - Nombre: {obj['name']}")
    print(f"    Cantidad: {obj['quantity']}")
    print(f"    Posible fecha de expiración: {obj['possible_expiry']}")
    print()
