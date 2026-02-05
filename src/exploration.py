import os

from zai import ZaiClient

from

# Read API Key from environment variable
client = ZaiClient(api_key=os.getenv("ZAI_API_KEY"))

# Or use directly (if environment variable is set)
client = ZaiClient()
