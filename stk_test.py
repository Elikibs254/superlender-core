import os
import requests
import base64
from datetime import datetime
from requests.auth import HTTPBasicAuth
from dotenv import load_dotenv

load_dotenv()

consumer_key = os.getenv("DARAJA_CONSUMER_KEY")
consumer_secret = os.getenv("DARAJA_CONSUMER_SECRET")

# Standard Safaricom Sandbox Credentials
shortcode = "174379"
passkey = "bfb279f9aa9bdbcf158e97dd71a467cd2e0c893059b10f78e6b72ada1ed2c919"
your_phone_number = "254700757876"  

def get_access_token():
    api_url = "https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials"
    response = requests.get(api_url, auth=HTTPBasicAuth(consumer_key, consumer_secret))
    return response.json()["access_token"]

def trigger_stk_push():
    token = get_access_token()
    
    # Safaricom requires a uniquely encoded password for every single transaction
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    password_string = shortcode + passkey + timestamp
    password = base64.b64encode(password_string.encode('utf-8')).decode('utf-8')
    
    api_url = "https://sandbox.safaricom.co.ke/mpesa/stkpush/v1/processrequest"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    # The blueprint of the money transfer
    payload = {
        "BusinessShortCode": shortcode,
        "Password": password,
        "Timestamp": timestamp,
        "TransactionType": "CustomerPayBillOnline",
        "Amount": 1, # We are only requesting 1 KES for the test
        "PartyA": your_phone_number,
        "PartyB": shortcode,
        "PhoneNumber": your_phone_number,
        "CallBackURL": "https://google.com", # We will change this to your ngrok URL later
        "AccountReference": "Superlender Pro",
        "TransactionDesc": "Loan Repayment"
    }
    
    print("📲 Sending STK Push request to Safaricom...")
    response = requests.post(api_url, json=payload, headers=headers)
    
    if response.status_code == 200:
        print("\n✅ SUCCESS! Check your phone right now. You should see the M-PESA PIN prompt!")
        print(response.json())
    else:
        print("\n❌ FAILED.")
        print(response.json())

if __name__ == "__main__":
    trigger_stk_push()