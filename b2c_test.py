import os
import requests
from requests.auth import HTTPBasicAuth
from dotenv import load_dotenv

load_dotenv()

# Pulling your keys from the .env vault
consumer_key = os.getenv("DARAJA_CONSUMER_KEY")
consumer_secret = os.getenv("DARAJA_CONSUMER_SECRET")

# The exact URLs Safaricom will ping when the money is sent
ngrok_url = "https://constrain-take-property.ngrok-free.dev"

def get_access_token():
    api_url = "https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials"
    response = requests.get(api_url, auth=HTTPBasicAuth(consumer_key, consumer_secret))
    return response.json()["access_token"]

def test_b2c_disbursement():
    print("⏳ Authenticating with Safaricom...")
    token = get_access_token()
    
    api_url = "https://sandbox.safaricom.co.ke/mpesa/b2c/v1/paymentrequest"
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    # The blueprint for sending money OUT
    payload = {
        "InitiatorName": "testapi",
        "SecurityCredential": "dummy_unencrypted_password_123", # 🛑 This will intentionally fail Safaricom's security check
        "CommandID": "BusinessPayment",
        "Amount": 100, # Trying to send you KES 100
        "PartyA": "600996", # The standard Sandbox B2C account
        "PartyB": "254700757876", # Your phone number
        "Remarks": "Superlender Loan Disbursement test",
        "QueueTimeOutURL": f"{ngrok_url}/b2c/timeout",
        "ResultURL": f"{ngrok_url}/b2c/result",
        "Occasion": "Loan"
    }
    
    print("💸 Firing Disbursement Request to Safaricom B2C Endpoint...")
    response = requests.post(api_url, json=payload, headers=headers)
    
    print("\n--- SAFARICOM RESPONSE ---")
    print(response.json())

if __name__ == "__main__":
    test_b2c_disbursement()