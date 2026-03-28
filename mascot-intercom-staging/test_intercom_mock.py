import asyncio
import os
import httpx
import uuid
from dotenv import load_dotenv

load_dotenv()
token = os.getenv("INTERCOM_TOKEN")
admin_id = os.getenv("INTERCOM_ADMIN_ID")
conversation_id = "215473211294326"

async def test_reply():
    url = f"https://api.intercom.io/conversations/{conversation_id}/reply"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    
    # Test 3: message_type="comment", body AND blocks
    payload3 = {
        "message_type": "comment",
        "type": "admin",
        "admin_id": admin_id,
        "body": "Testing blocks + body",
        "blocks": [
            {
                "type": "paragraph",
                "text": "Please choose an option:",
            },
            {
                "type": "button",
                "text": "Yes",
                "style": "primary",
                "action": {
                    "type": "submit"
                }
            }
        ]
    }
    
    # Test 4: message_type="quick_reply" supplying UUIDs for reply_options
    payload4 = {
        "message_type": "quick_reply",
        "type": "admin",
        "admin_id": admin_id,
        "body": "Test Quick Replies 4",
        "reply_options": [
            {"uuid": str(uuid.uuid4()), "text": "Yes"},
            {"uuid": str(uuid.uuid4()), "text": "No"}
        ]
    }

    async with httpx.AsyncClient() as client:
        print("Testing payload3 (blocks + body)...")
        r3 = await client.post(url, headers=headers, json=payload3)
        print(f"Status 3: {r3.status_code}")
        print(r3.text)

        print("Testing payload4 (quick_reply with UUIDs)...")
        r4 = await client.post(url, headers=headers, json=payload4)
        print(f"Status 4: {r4.status_code}")
        print(r4.text)

if __name__ == "__main__":
    asyncio.run(test_reply())
