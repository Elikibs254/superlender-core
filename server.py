import os
import time
import base64
import requests
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from dotenv import load_dotenv
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

# Safaricom B2C Keys
DARAJA_CONSUMER_KEY = os.getenv("DARAJA_CONSUMER_KEY")
DARAJA_CONSUMER_SECRET = os.getenv("DARAJA_CONSUMER_SECRET")
B2C_SECURITY_CREDENTIAL = os.getenv("B2C_SECURITY_CREDENTIAL")
INITIATOR_NAME = "testapi"
SHORTCODE = "600989" # Standard Daraja Sandbox B2C Shortcode

# 3. The Bot's Short-Term Memory
user_states = {}

# --- HELPER: WHATSAPP SENDER ---
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
        print(f"Failed to send WhatsApp message: {e}")

# --- HELPER: M-PESA B2C DISBURSEMENT ---
def get_daraja_access_token():
    """Generates the temporary password needed to talk to Safaricom."""
    api_url = "https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials"
    r = requests.get(api_url, auth=(DARAJA_CONSUMER_KEY, DARAJA_CONSUMER_SECRET))
    return r.json()['access_token']

def send_b2c_payment(phone_number, amount):
    """Fires the M-PESA Business to Customer payment."""
    access_token = get_daraja_access_token()
    api_url = "https://sandbox.safaricom.co.ke/mpesa/b2c/v1/paymentrequest"
    
    # Safaricom requires the phone number in 254 format, not +254 or 07
    formatted_phone = phone_number.replace("+", "")
    if formatted_phone.startswith("0"):
        formatted_phone = "254" + formatted_phone[1:]
        
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    payload = {
        "InitiatorName": INITIATOR_NAME,
        "SecurityCredential": B2C_SECURITY_CREDENTIAL,
        "CommandID": "BusinessPayment",
        "Amount": str(amount),
        "PartyA": SHORTCODE,
        "PartyB": formatted_phone,
        "Remarks": "Superlender Loan Disbursement",
        "QueueTimeOutURL": f"{NGROK_URL}/b2c_timeout",
        "ResultURL": f"{NGROK_URL}/b2c_result",
        "Occasion": "Loan"
    }
    
    response = requests.post(api_url, json=payload, headers=headers)
    print(f"Safaricom API Response: {response.text}")
    return response.status_code == 200

# --- WEBHOOK ENDPOINTS ---

@app.get("/webhook")
async def verify_webhook(request: Request):
    """WhatsApp verification."""
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        return int(challenge)
    return {"error": "Invalid token"}

@app.post("/webhook")
async def handle_whatsapp_message(request: Request):
    """The core engine logic."""
    data = await request.json()
    
    try:
        entry = data['entry'][0]['changes'][0]['value']
        if 'messages' in entry:
            message = entry['messages'][0]
            sender_phone = message['from']
            msg_text = message['text']['body'].strip()

            current_state = user_states.get(sender_phone, "start")

            if current_state == "start" or msg_text.lower() in ["hello", "hi", "menu"]:
                menu = (
                    "Welcome to *Superlender Pro*! 🚀\n\n"
                    "Please reply with a number to proceed:\n"
                    "1️⃣ Apply for an Account\n"
                    "2️⃣ Check My Balance\n"
                    "3️⃣ Request Loan (KES 500)"
                )
                send_whatsapp_message(sender_phone, menu)
                user_states[sender_phone] = "main_menu"
            
            elif current_state == "main_menu":
                if msg_text == "1":
                    send_whatsapp_message(sender_phone, "Great! Let's get you registered.\n\nPlease reply with your *National ID Number*:")
                    user_states[sender_phone] = "applying_step_1"
                
                elif msg_text == "2":
                    user_profile = db_engine.get_user(sender_phone)
                    if user_profile:
                        balance = user_profile['balance']
                        limit = user_profile['loan_limit']
                        statement = (
                            "📊 *Account Statement*\n\n"
                            f"Current Loan Balance: *KES {balance}*\n"
                            f"Available Limit: *KES {limit}*\n\n"
                            "Type 'Menu' to go back."
                        )
                        send_whatsapp_message(sender_phone, statement)
                    else:
                        send_whatsapp_message(sender_phone, "⚠️ We couldn't find an account for this number. Please reply with 1 to Apply.")
                    user_states[sender_phone] = "start" 
                
                elif msg_text == "3":
                    # --- THE MONEY TRIGGER ---
                    user_profile = db_engine.get_user(sender_phone)
                    
                    if not user_profile:
                        send_whatsapp_message(sender_phone, "⚠️ You need an account first. Reply with 1 to Apply.")
                        user_states[sender_phone] = "start"
                    
                    elif user_profile['balance'] > 0:
                        send_whatsapp_message(sender_phone, "⚠️ You currently have an outstanding loan. Please repay it before requesting a new one.")
                        user_states[sender_phone] = "start"
                        
                    elif user_profile['loan_limit'] < 500:
                        send_whatsapp_message(sender_phone, "⚠️ Your available limit is too low for this request.")
                        user_states[sender_phone] = "start"
                        
                    else:
                        send_whatsapp_message(sender_phone, "⏳ Processing your loan of KES 500. Please wait...")
                        
                        # Call the Safaricom function
                        success = send_b2c_payment(sender_phone, 500)
                        
                        if success:
                            send_whatsapp_message(sender_phone, "✅ Disbursement successful! You will receive an M-PESA notification shortly.")
                            # Update the database so they owe us money now
                            db_engine.cursor.execute("UPDATE customers SET balance = 500, loan_limit = 0 WHERE phone_number = %s", (sender_phone,))
                            db_engine.connection.commit()
                        else:
                            send_whatsapp_message(sender_phone, "❌ M-PESA Disbursement failed. Please try again later.")
                            
                        user_states[sender_phone] = "start"
                
                else:
                    send_whatsapp_message(sender_phone, "⚠️ Invalid option. Please reply with 1, 2, or 3.")
                    
            elif current_state == "applying_step_1":
                db_engine.create_user(sender_phone, msg_text)
                success_msg = (
                    "Account successfully created! ✅\n\n"
                    f"Your National ID (*{msg_text}*) has been verified.\n"
                    "You have been awarded a starting loan limit of *KES 500*.\n\n"
                    "Type 'Menu' to go back."
                )
                send_whatsapp_message(sender_phone, success_msg)
                user_states[sender_phone] = "start"

        return {"status": "success"}
    except Exception as e:
        print(f"Webhook Error: {e}")
        return {"status": "error"}

@app.post("/b2c_result")
async def b2c_result(request: Request):
    """Safaricom sends the final receipt here."""
    data = await request.json()
    print(f"M-PESA Receipt Received: {data}")
    return {"ResultCode": 0, "ResultDesc": "Success"}

@app.post("/b2c_timeout")
async def b2c_timeout(request: Request):
    """Safaricom tells us if the payment timed out."""
    return {"ResultCode": 0, "ResultDesc": "Success"}

# --- DASHBOARD ENDPOINTS ---

@app.get("/")
async def serve_dashboard():
    """Serves the visual HTML interface when you visit the main URL."""
    return FileResponse("dashboard.html")

@app.get("/api/metrics")
async def get_metrics():
    """Provides the live database numbers to the JavaScript frontend."""
    return db_engine.get_dashboard_metrics()