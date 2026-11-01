
import os
import requests
from dotenv import load_dotenv

load_dotenv()

N8N_WEBHOOK_URL = os.getenv("N8N_WEBHOOK_URL")


def send_lead_to_n8n(lead):
    if not N8N_WEBHOOK_URL:
        print("n8n webhook URL is missing!")
        return

    payload = {
        "id": lead.id,
        "name": lead.name,
        "email": lead.email,
        "phone": lead.phone,
        "service": lead.service,
        "status": lead.status,
        "lead_score": lead.lead_score,
        "priority": lead.priority
    }

    print("Sending payload to n8n:", payload)

    try:
        response = requests.post(
            N8N_WEBHOOK_URL,
            json=payload,
            timeout=10
        )
        response.raise_for_status()
        print("Lead successfully sent to n8n!")

    except requests.RequestException as error:
        print(f"Could not send lead to n8n: {error}")
