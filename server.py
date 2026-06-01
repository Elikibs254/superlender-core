from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from engine import SuperLenderEngine
import os
import requests
import base64
from datetime import datetime
from requests.auth import HTTPBasicAuth
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

db_engine = SuperLenderEngine(
    host="localhost",
    database="superlender_core",
    user="root",
    password="SuperLender2026!" 
)

# --- CREDENTIALS ---
VERIFY_TOKEN = "superlender_secure_token_123"
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
DARAJA_CONSUMER_KEY = os.getenv("DARAJA_CONSUMER_KEY")
DARAJA_CONSUMER_SECRET = os.getenv("DARAJA_CONSUMER_SECRET")
B2C_SECURITY_CREDENTIAL = os.getenv("B2C_SECURITY_CREDENTIAL")

NGROK_URL = "https://constrain-take-property.ngrok-free.dev"
user_states = {}

# ==========================================
# 📊 WEB DASHBOARD API
# ==========================================
@app.get("/api/dashboard")
async def get_dashboard_metrics():
    try:
        db_engine.cursor.execute("SELECT COUNT(*) as total FROM borrowers")
        total_borrowers = db_engine.cursor.fetchone()['total']
        
        db_engine.cursor.execute("SELECT COUNT(*) as active_count, IFNULL(SUM(principal_amount), 0) as total_principal, IFNULL(SUM(balance_remaining), 0) as total_outstanding FROM loans WHERE status = 'active'")
        loan_stats = db_engine.cursor.fetchone()
        
        db_engine.cursor.execute("SELECT IFNULL(SUM(principal_amount), 0) as cleared_principal FROM loans WHERE status = 'cleared'")
        cleared_stats = db_engine.cursor.fetchone()
        
        total_disbursed = float(loan_stats['total_principal']) + float(cleared_stats['cleared_principal'])
        
        return {
            "total_borrowers": total_borrowers,
            "active_loans_count": loan_stats['active_count'],
            "total_disbursed": total_disbursed,
            "outstanding_debt": float(loan_stats['total_outstanding']),
            "system_status": "Operational"
        }
    except Exception as e:
        return {"error": str(e)}


# ==========================================
# 💬 WHATSAPP COMMUNICATION
# ==========================================
def send_message(phone_number, text):
    url = f"https://graph.facebook.com/v25.0/{PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"}
    payload = {"messaging_product": "whatsapp", "to": phone_number, "type": "text", "text": {"body": text}}
    
    # Catch the actual response from Meta
    response = requests.post(url, json=payload, headers=headers)
    
    # Print exactly what Meta says back to us
    if response.status_code == 200:
        print(f"--> ✅ Successfully sent reply to {phone_number}:\n{text}\n")
    else:
        print(f"--> ❌ WHATSAPP API ERROR: {response.json()}\n")


# ==========================================
# 💸 M-PESA DARAJA ENGINE
# ==========================================
def get_mpesa_access_token():
    api_url = "https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials"
    response = requests.get(api_url, auth=HTTPBasicAuth(DARAJA_CONSUMER_KEY, DARAJA_CONSUMER_SECRET))
    return response.json()["access_token"]

def trigger_stk_push(phone_number, amount):
    """Requests money FROM the user"""
    token = get_mpesa_access_token()
    shortcode = "174379"
    passkey = "bfb279f9aa9bdbcf158e97dd71a467cd2e0c893059b10f78e6b72ada1ed2c919"
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    password_string = shortcode + passkey + timestamp
    password = base64.b64encode(password_string.encode('utf-8')).decode('utf-8')
    
    api_url = "https://sandbox.safaricom.co.ke/mpesa/stkpush/v1/processrequest"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    payload = {
        "BusinessShortCode": shortcode, "Password": password, "Timestamp": timestamp,
        "TransactionType": "CustomerPayBillOnline", "Amount": int(amount),
        "PartyA": phone_number, "PartyB": shortcode, "PhoneNumber": phone_number,
        "CallBackURL": f"{NGROK_URL}/mpesa/callback", "AccountReference": "Superlender", "TransactionDesc": "Repayment"
    }
    requests.post(api_url, json=payload, headers=headers)

def trigger_b2c_disbursement(phone_number, amount):
    """Sends real money TO the user"""
    token = get_mpesa_access_token()
    api_url = "https://sandbox.safaricom.co.ke/mpesa/b2c/v1/paymentrequest"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    payload = {
        "InitiatorName": "testapi",
        "SecurityCredential": B2C_SECURITY_CREDENTIAL, 
        "CommandID": "BusinessPayment",
        "Amount": int(amount),
        "PartyA": "600996", 
        "PartyB": phone_number,
        "Remarks": "Superlender Loan",
        "QueueTimeOutURL": f"{NGROK_URL}/b2c/timeout",
        "ResultURL": f"{NGROK_URL}/b2c/result",
        "Occasion": "Loan"
    }
    requests.post(api_url, json=payload, headers=headers)
    print(f"🚀 Fired KES {amount} to {phone_number} via B2C!")


# ==========================================
# 🚪 WEBHOOK DOORS
# ==========================================
@app.get("/webhook")
async def verify_webhook(request: Request):
    if request.query_params.get("hub.mode") == "subscribe" and request.query_params.get("hub.verify_token") == VERIFY_TOKEN:
        return int(request.query_params.get("hub.challenge"))
    return {"error": "Invalid token"}

@app.post("/webhook")
async def receive_message(request: Request):
    body = await request.json()
    try:
        phone_number = body["entry"][0]["changes"][0]["value"]["messages"][0]["from"]
        text_received = body["entry"][0]["changes"][0]["value"]["messages"][0]["text"]["body"].strip()
        print(f"\n--- Incoming Message from {phone_number}: '{text_received}' ---")
        process_user_message(phone_number, text_received)
    except KeyError:
        pass
    return {"status": "success"}

@app.post("/mpesa/callback")
async def mpesa_callback(request: Request):
    body = await request.json()
    try:
        if body["Body"]["stkCallback"]["ResultCode"] == 0: 
            metadata = body["Body"]["stkCallback"]["CallbackMetadata"]["Item"]
            amount = next(item["Value"] for item in metadata if item["Name"] == "Amount")
            phone_number = str(next(item["Value"] for item in metadata if item["Name"] == "PhoneNumber"))
            
            db_engine.cursor.execute("SELECT borrower_id FROM borrowers WHERE phone_number = %s", (phone_number,))
            user = db_engine.cursor.fetchone()
            if user:
                db_engine.cursor.execute("SELECT loan_id, balance_remaining FROM loans WHERE borrower_id = %s AND status = 'active'", (user['borrower_id'],))
                active_loan = db_engine.cursor.fetchone()
                if active_loan:
                    new_balance = float(active_loan['balance_remaining']) - float(amount)
                    if new_balance <= 0:
                        db_engine.cursor.execute("UPDATE loans SET balance_remaining = 0, status = 'cleared' WHERE loan_id = %s", (active_loan['loan_id'],))
                        send_message(phone_number, f"✅ KES {amount} received! Loan cleared.")
                    else:
                        db_engine.cursor.execute("UPDATE loans SET balance_remaining = %s WHERE loan_id = %s", (new_balance, active_loan['loan_id']))
                        send_message(phone_number, f"✅ Partial Payment KES {amount} received. Remaining: KES {new_balance}.")
                    db_engine.connection.commit()
    except Exception as e:
        print(f"Error processing M-PESA Callback: {e}")
    return {"status": "success"}

@app.post("/b2c/result")
async def b2c_result(request: Request):
    body = await request.json()
    try:
        if body["Result"]["ResultCode"] == 0:
            print("\n✅ B2C SUCCESS: Real money successfully deposited to user's M-PESA!")
        else:
            print(f"\n❌ B2C FAILED: {body['Result']['ResultDesc']}")
    except KeyError:
        pass
    return {"status": "success"}

@app.post("/b2c/timeout")
async def b2c_timeout(request: Request):
    return {"status": "success"}


# ==========================================
# 🧠 THE BOT BRAIN
# ==========================================
def process_user_message(phone_number, text_received):
    db_engine.cursor.execute("SELECT b.*, c.company_name, c.interest_rate, c.registration_fee FROM borrowers b JOIN companies c ON b.company_id = c.company_id WHERE b.phone_number = %s", (phone_number,))
    user = db_engine.cursor.fetchone()

    if user:
        text_lower = text_received.lower()
        if text_lower.startswith("borrow"):
            try:
                amount = float(text_lower.replace("borrow", "").strip())
                handle_borrow_request(phone_number, user, amount)
            except ValueError:
                send_message(phone_number, "Example: 'borrow 500'")
        elif text_lower.startswith("pay") or text_lower.startswith("repay"):
            try:
                amount = float(text_lower.replace("repay", "").replace("pay", "").strip())
                trigger_stk_push(phone_number, amount)
                send_message(phone_number, f"📲 M-PESA prompt sent! Please enter your PIN to pay KES {amount}.")
            except Exception as e:
                send_message(phone_number, "System Error initiating payment.")
        elif "balance" in text_lower:
            db_engine.cursor.execute("SELECT balance_remaining FROM loans WHERE borrower_id = %s AND status = 'active'", (user['borrower_id'],))
            loan = db_engine.cursor.fetchone()
            if loan:
                send_message(phone_number, f"Your debt with {user['company_name']} is KES {loan['balance_remaining']}.")
            else:
                send_message(phone_number, "You have no active loans.")
        else:
            send_message(phone_number, f"Welcome back, {user['name']}! Reply 'borrow [amount]', 'pay [amount]', or 'balance'.")
    else:
        current_state = user_states.get(phone_number, {}).get("step")
        if current_state == "waiting_for_name":
            user_states[phone_number] = {"name": text_received.title(), "step": "waiting_for_id"}
            send_message(phone_number, "Thanks! Please reply with your National ID number to complete your KYC.")
        elif current_state == "waiting_for_id":
            db_engine.cursor.execute("INSERT INTO borrowers (name, phone_number, credit_limit, national_id, company_id) VALUES (%s, %s, %s, %s, %s)", (user_states[phone_number]["name"], phone_number, 2000.00, text_received.strip(), 1))
            db_engine.connection.commit()
            send_message(phone_number, f"KYC Verified! ✅ Welcome. Your limit is KES 2,000. Reply 'borrow 500' to test it out.")
            del user_states[phone_number]
        else:
            user_states[phone_number] = {"step": "waiting_for_name"}
            send_message(phone_number, "Welcome! We don't recognize this number. Please reply with your Full Name to register.")

def handle_borrow_request(phone_number, user, requested_amount):
    db_engine.cursor.execute("SELECT balance_remaining FROM loans WHERE borrower_id = %s AND status = 'active'", (user['borrower_id'],))
    if db_engine.cursor.fetchone():
        send_message(phone_number, "Sorry, you have an active loan. Clear it before borrowing again.")
        return

    if requested_amount > float(user['credit_limit']):
        send_message(phone_number, f"Request exceeds your limit of KES {user['credit_limit']}.")
        return

    interest_fee = requested_amount * float(user['interest_rate'])
    reg_fee = float(user['registration_fee']) if not user.get('registration_fee_paid') else 0.0
    total_owed = requested_amount + interest_fee + reg_fee
    
    if reg_fee > 0:
        db_engine.cursor.execute("UPDATE borrowers SET registration_fee_paid = TRUE WHERE borrower_id = %s", (user['borrower_id'],))
        
    db_engine.cursor.execute("INSERT INTO loans (borrower_id, principal_amount, balance_remaining, status) VALUES (%s, %s, %s, 'active')", (user['borrower_id'], requested_amount, total_owed))
    db_engine.connection.commit()
    
    # 💥 THE MONEY CANNON: Instantly send the funds to their phone!
    trigger_b2c_disbursement(phone_number, requested_amount)
    
    send_message(phone_number, f"✅ Loan Approved!\nPrincipal: KES {requested_amount}\nTotal to Repay: KES {total_owed}\n\nFunds have been sent to your M-PESA!")