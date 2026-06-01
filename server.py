import os
from fastapi import FastAPI, Request
from dotenv import load_dotenv
import requests
from engine import SuperLenderEngine

# Load the secret vault
load_dotenv()

app = FastAPI()

# 1. Connect to Cloud Database
db_engine = SuperLenderEngine(
    host=os.getenv("DB_HOST"),
    port=int(os.getenv("DB_PORT")),
    database=os.getenv("DB_NAME"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD")
)

# 2. Load API Keys
VERIFY_TOKEN = "superlender_secure_token_123"
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
NGROK_URL = "https://superlender-engine.onrender.com"

# 3. The Bot's Short-Term Memory
user_states = {}

# --- HELPER FUNCTION: SEND WHATSAPP MESSAGE ---
def send_whatsapp_message(phone_number, text):
    url = f"https://graph.facebook.com/v19.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": phone_number,
        "type": "text",
        "text": {"body": text}
    }
    try:
        requests.post(url, headers=headers, json=payload)
    except Exception as e:
        print(f"Failed to send message: {e}")

# --- WEBHOOK ENDPOINTS ---

@app.get("/webhook")
async def verify_webhook(request: Request):
    """This allows Meta to verify our server is alive."""
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        return int(challenge)
    return {"error": "Invalid token"}

@app.post("/webhook")
async def handle_whatsapp_message(request: Request):
    """This is the brain that reads incoming messages and routes the conversation."""
    data = await request.json()
    
    try:
        # Check if the incoming data contains an actual text message
        entry = data['entry'][0]['changes'][0]['value']
        if 'messages' in entry:
            message = entry['messages'][0]
            sender_phone = message['from']
            msg_text = message['text']['body'].strip()

            # --- CONVERSATION ROUTER ---
            
            # Step A: Check where the user currently is in the conversation (Default is 'start')
            current_state = user_states.get(sender_phone, "start")

            # Step B: If they say hello, or just started, show the main menu
            if current_state == "start" or msg_text.lower() in ["hello", "hi", "menu"]:
                menu = (
                    "Welcome to *Superlender Pro*! 🚀\n\n"
                    "Please reply with a number to proceed:\n"
                    "1️⃣ Apply for a Loan\n"
                    "2️⃣ Check My Balance\n"
                    "3️⃣ Contact Support"
                )
                send_whatsapp_message(sender_phone, menu)
                # Update their memory state so the bot knows they are looking at the menu
                user_states[sender_phone] = "main_menu"
            
            # Step C: If they are looking at the Main Menu, read the number they typed
            elif current_state == "main_menu":
                if msg_text == "1":
                    send_whatsapp_message(sender_phone, "Great! Let's get you registered.\n\nPlease reply with your *National ID Number*:")
                    user_states[sender_phone] = "applying_step_1"
                
                elif msg_text == "2":
                    # Placeholder: We will wire this to the MySQL database later!
                    send_whatsapp_message(sender_phone, "Your current balance is: *KES 0.00*.\n\nType 'Menu' to go back.")
                    user_states[sender_phone] = "start" 
                
                elif msg_text == "3":
                    send_whatsapp_message(sender_phone, "Our support team is available Mon-Fri, 8 AM to 5 PM.\nCall: 0712345678\n\nType 'Menu' to go back.")
                    user_states[sender_phone] = "start"
                
                else:
                    # If they type "4" or "Apple"
                    send_whatsapp_message(sender_phone, "⚠️ Invalid option. Please reply with 1, 2, or 3.")
                    
            # Step D: If they selected Option 1, catch their ID Number
            elif current_state == "applying_step_1":
                # Placeholder: We will save this ID to the database later!
                send_whatsapp_message(sender_phone, f"Thank you. We have received ID: *{msg_text}*.\n\n(Database integration coming soon!).\nType 'Menu' to restart.")
                user_states[sender_phone] = "start"

        return {"status": "success"}
    except Exception as e:
        print(f"Webhook Error: {e}")
        return {"status": "error"}