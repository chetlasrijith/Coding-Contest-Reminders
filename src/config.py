import os
from dotenv import load_dotenv

load_dotenv()

# Read these from environment (or from your `.env` file). Do NOT hardcode tokens in source.
# Set `PHONE_NUMBER_ID` and `ACCESS_TOKEN` in your `.env` or environment variables.
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
GRAPH_API_VERSION = os.getenv("GRAPH_API_VERSION", "v24.0")
TEMPLATE_NAME = os.getenv("TEMPLATE_NAME", "contest_notification")
TEMPLATE_LANG = os.getenv("TEMPLATE_LANG", "en")
TIMEZONE = os.getenv("TIMEZONE", "UTC")

API_URL = f"https://graph.facebook.com/{GRAPH_API_VERSION}/{PHONE_NUMBER_ID}/messages"
HEADERS = {
    "Authorization": f"Bearer {ACCESS_TOKEN}",
    "Content-Type": "application/json"
}
