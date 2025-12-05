import requests
from .config import API_URL, HEADERS, TEMPLATE_NAME, TEMPLATE_LANG

def send_template(to_number: str, var1: str, var2: str):
    """
    Send the approved template with two text variables.
    Returns response object.
    """
    payload = {
        "messaging_product": "whatsapp",
        "to": to_number,
        "type": "template",
        "template": {
            "name": TEMPLATE_NAME,
            "language": {"code": TEMPLATE_LANG},
            "components": [
                {
                    "type": "body",
                    "parameters": [
                        {"type": "text", "text": var1},
                        {"type": "text", "text": var2}
                    ]
                }
            ]
        }
    }
    resp = requests.post(API_URL, headers=HEADERS, json=payload, timeout=30)
    try:
        data = resp.json()
    except Exception:
        data = {"raw": resp.text}
    print(f"[SEND] to={to_number} status={resp.status_code} resp={data}")
    return resp
