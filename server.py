import os
import time
import base64
import requests
from datetime import datetime
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

# Safaricom Keys
DARAJA_CONSUMER_KEY = os.getenv("DARAJA_CONSUMER_KEY")
DARAJA_CONSUMER_SECRET = os.getenv("DARAJA_CONSUMER_SECRET")
B2C_SECURITY_CREDENTIAL = os.getenv("B2C_SECURITY_CREDENTIAL")
INITIATOR_NAME = "testapi"
B2C_SHORTCODE = "600989" 

# STK Push (Express) Keys
LIPA_NA_MPESA_SHORTCODE = os.getenv("LIPA_NA_MPESA_SHORTCODE", "174379")
LIPA_NA_MPESA_PASSKEY = os.getenv("LIPA_NA_MPESA_PASSKEY", "bfb279f9aa9bdbcf158e97dd71a467cd2e0c893059b10f78e6b72ada1ed2c919")

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

# --- HELPER: SAFARICOM DARAJA ---
def get_daraja_access_token():
    api_url = "https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials"
    r = requests.get(api_url, auth=(DARAJA_CONSUMER_KEY, DARAJA_CONSUMER_SECRET))
    return r.json()['access_token']

def send_b2c_payment(phone_number, amount):
    access_token = get_daraja_access_token()
    api_url = "https://sandbox.safaricom.co.ke/mpesa/b2c/v1/paymentrequest"
    
    formatted_phone = phone_number.replace("+", "")
    if formatted_phone.startswith("0"):
        formatted_phone = "254" + formatted_phone[1:]
        
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    payload = {
        "InitiatorName": INITIATOR_NAME,
        "SecurityCredential": B2C_SECURITY_CREDENTIAL,
        "CommandID": "BusinessPayment",
        "Amount": str(amount),
        "PartyA": B2C_SHORTCODE,
        "PartyB": formatted_phone,
        "Remarks": "Boresha Cash Loan",
        "QueueTimeOutURL": f"{NGROK_URL}/b2c_timeout",
        "ResultURL": f"{NGROK_URL}/b2c_result",
        "Occasion": "Loan"
    }
    response = requests.post(api_url, json=payload, headers=headers)
    return response.status_code == 200

def trigger_stk_push(phone_number, amount):
    access_token = get_daraja_access_token()
    api_url = "https://sandbox.safaricom.co.ke/mpesa/stkpush/v1/processrequest"
    
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    password_str = f"{LIPA_NA_MPESA_SHORTCODE}{LIPA_NA_MPESA_PASSKEY}{timestamp}"
    password = base64.b64encode(password_str.encode()).decode('utf-8')
    
    formatted_phone = phone_number.replace("+", "")
    if formatted_phone.startswith("0"):
        formatted_phone = "254" + formatted_phone[1:]
        
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    payload = {
        "BusinessShortCode": LIPA_NA_MPESA_SHORTCODE,
        "Password": password,
        "Timestamp": timestamp,
        "TransactionType": "CustomerPayBillOnline",
        "Amount": str(amount),
        "PartyA": formatted_phone,
        "PartyB": LIPA_NA_MPESA_SHORTCODE,
        "PhoneNumber": formatted_phone,
        "CallBackURL": f"{NGROK_URL}/stk_callback",
        "AccountReference": "Boresha Cash",
        "TransactionDesc": "Loan Repayment"
    }
    response = requests.post(api_url, json=payload, headers=headers)
    return response.status_code == 200

# --- WHATSAPP CORE ENGINE ---
@app.get("/webhook")
async def verify_webhook(request: Request):
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")
    if mode == "subscribe" and token == VERIFY_TOKEN:
        return int(challenge)
    return {"error": "Invalid token"}

@app.post("/webhook")
async def handle_whatsapp_message(request: Request):
    data = await request.json()
    try:
        entry = data['entry'][0]['changes'][0]['value']
        if 'messages' in entry:
            message = entry['messages'][0]
            sender_phone = message['from']
            msg_text = message['text']['body'].strip()
            
            # The client-side admin command has been permanently removed from here.
            current_state = user_states.get(sender_phone, "start")

            if current_state == "start" or msg_text.lower() in ["hello", "hi", "menu"]:
                menu = (
                    "Welcome to *Boresha Cash*! 🚀\n\n"
                    "Reply with a number:\n"
                    "1️⃣ Apply for an Account\n"
                    "2️⃣ Check My Balance\n"
                    "3️⃣ Request Loan (KES 500)\n"
                    "4️⃣ Repay Loan"
                )
                send_whatsapp_message(sender_phone, menu)
                user_states[sender_phone] = "main_menu"
            
            elif current_state == "main_menu":
                if msg_text == "1":
                    send_whatsapp_message(sender_phone, "Reply with your *National ID Number*:")
                    user_states[sender_phone] = "applying_step_1"
                
                elif msg_text == "2":
                    user_profile = db_engine.get_user(sender_phone)
                    if user_profile:
                        statement = f"📊 *Account Statement*\n\nOutstanding Balance: *KES {user_profile['balance']}*\n\nType 'Menu' to go back."
                        send_whatsapp_message(sender_phone, statement)
                    else:
                        send_whatsapp_message(sender_phone, "⚠️ Account not found. Reply 1 to Apply.")
                    user_states[sender_phone] = "start" 
                
                elif msg_text == "3":
                    user_profile = db_engine.get_user(sender_phone)
                    if not user_profile:
                        send_whatsapp_message(sender_phone, "⚠️ You need an account first. Reply 1 to Apply.")
                    elif user_profile['balance'] > 0:
                        send_whatsapp_message(sender_phone, "⚠️ You have an outstanding loan. Please repay first.")
                    elif user_profile['loan_limit'] < 500:
                        send_whatsapp_message(sender_phone, "⚠️ Your loan request could not be processed at this time. Please contact Boresha Cash support.")
                    else:
                        send_whatsapp_message(sender_phone, "⏳ Processing KES 500. Please wait...")
                        success = send_b2c_payment(sender_phone, 500)
                        if success:
                            send_whatsapp_message(sender_phone, "✅ Disbursement queued! You will receive an M-PESA text.")
                            db_engine.cursor.execute("UPDATE customers SET balance = 500, loan_limit = loan_limit - 500 WHERE phone_number = %s", (sender_phone,))
                            db_engine.connection.commit()
                        else:
                            send_whatsapp_message(sender_phone, "❌ M-PESA failed. Try again later.")
                    user_states[sender_phone] = "start"

                elif msg_text == "4":
                    user_profile = db_engine.get_user(sender_phone)
                    if not user_profile or user_profile['balance'] <= 0:
                        send_whatsapp_message(sender_phone, "✅ You have no outstanding loan to repay!")
                        user_states[sender_phone] = "start"
                    else:
                        send_whatsapp_message(sender_phone, f"Your balance is *KES {user_profile['balance']}*.\n\nReply with the exact amount you want to pay (e.g., 500):")
                        user_states[sender_phone] = "repaying_step_1"
                else:
                    send_whatsapp_message(sender_phone, "⚠️ Invalid option.")
                    
            elif current_state == "applying_step_1":
                db_engine.create_user(sender_phone, msg_text)
                send_whatsapp_message(sender_phone, f"Account created! ✅\nNational ID *{msg_text}* verified.\n\nType 'Menu' to go back.")
                user_states[sender_phone] = "start"

            elif current_state == "repaying_step_1":
                try:
                    amount = int(msg_text)
                    send_whatsapp_message(sender_phone, f"⏳ Sending an M-PESA prompt to your phone for *KES {amount}*. Please enter your PIN to complete the repayment.")
                    trigger_stk_push(sender_phone, amount)
                except ValueError:
                    send_whatsapp_message(sender_phone, "⚠️ Please enter a valid number.")
                user_states[sender_phone] = "start"

        return {"status": "success"}
    except Exception as e:
        print(f"Webhook Error: {e}")
        return {"status": "error"}

# --- M-PESA CALLBACK ENDPOINTS ---
@app.post("/b2c_result")
async def b2c_result(request: Request):
    data = await request.json()
    print(f"B2C Receipt: {data}")
    return {"ResultCode": 0, "ResultDesc": "Success"}

@app.post("/b2c_timeout")
async def b2c_timeout(request: Request):
    return {"ResultCode": 0, "ResultDesc": "Success"}

@app.post("/stk_callback")
async def stk_callback(request: Request):
    data = await request.json()
    print(f"STK Push Callback: {data}")
    try:
        body = data.get('Body', {}).get('stkCallback', {})
        result_code = body.get('ResultCode')
        
        if result_code == 0:
            metadata = body.get('CallbackMetadata', {}).get('Item', [])
            amount = next((item['Value'] for item in metadata if item['Name'] == 'Amount'), 0)
            phone = next((item['Value'] for item in metadata if item['Name'] == 'PhoneNumber'), "")
            
            db_phone = str(phone)
            db_engine.cursor.execute(
                "UPDATE customers SET balance = balance - %s, loan_limit = loan_limit + %s WHERE phone_number LIKE %s", 
                (amount, amount, f"%{db_phone[-9:]}")
            )
            db_engine.connection.commit()
            print(f"Ledger updated securely for {db_phone}")
            
    except Exception as e:
        print(f"Database sync failed during STK callback: {e}")
        
    return {"ResultCode": 0, "ResultDesc": "Success"}

# --- DASHBOARD / ADMIN ENDPOINTS ---
@app.get("/")
async def serve_dashboard():
    return FileResponse("dashboard.html")

@app.get("/api/metrics")
async def get_metrics():
    return db_engine.get_dashboard_metrics()

from fastapi import HTTPException

# SECURE ADMIN ROUTE: Deletes a user via dashboard command
@app.delete("/api/reset_user/{phone_number}")
async def reset_user(phone_number: str):
    try:
        # 1. Delete from MySQL
        db_engine.delete_user(phone_number)
        
        # 2. Delete from Bot RAM
        if phone_number in user_states:
            del user_states[phone_number]
            
        return {"status": "success"}
    except Exception as e:
        # Force a real HTTP error so the browser actually alerts you
        print(f"Delete Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))