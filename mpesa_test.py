import os
import requests
from requests.auth import HTTPBasicAuth
from dotenv import load_dotenv

# Load the keys from your .env file
load_dotenv()

consumer_key = os.getenv("DARAJA_CONSUMER_KEY")
consumer_secret = os.getenv("DARAJA_CONSUMER_SECRET")

def get_mpesa_access_token():
    print("⏳ Attempting to handshake with Safaricom Daraja...")
    
    api_url = "https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials"
    
    try:
        # We send the Key and Secret using Basic Authentication
        response = requests.get(api_url, auth=HTTPBasicAuth(consumer_key, consumer_secret))
        
        if response.status_code == 200:
            access_token = response.json()["access_token"]
            print("\n✅ HANDSHAKE SUCCESSFUL!")
            print(f"Your temporary 1-hour M-PESA token is: {access_token[:15]}...")
            return access_token
        else:
            print("\n❌ HANDSHAKE FAILED.")
            print(response.text)
            return None
            
    except Exception as e:
        print(f"Error connecting to Daraja: {e}")

# Run the test
if __name__ == "__main__":
    get_mpesa_access_token()