# console.truelayer.com/

import requests
import credentials

# Sandbox Credentials
CLIENT_ID = credentials.client_id
CLIENT_SECRET = credentials.client_secret
BASE_URL = "https://auth.truelayer-sandbox.com"

def get_access_token():
    url = f"{BASE_URL}/connect/token"
    payload = {
        "grant_type": "client_credentials",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "scope": "payments" # or "info", "accounts", etc.
    }
    response = requests.post(url, data=payload)
    if response.status_code != 200:
        print(f"Error: {response.status_code}")
        print(response.text)
        return None
    return response.json().get("access_token")



if __name__ == "__main__":
    token = get_access_token()
    if token:
        print("Successfully obtained access token!")
        print(f"Token: {token[:10]}...")
        with open("./open_banking_integration/token.txt", "w") as f:
            f.write(token)
    else:
        print("Failed to get access token.")

# Use this token to interact with the Mock Bank at:
# https://api.truelayer-sandbox.com/data/v1/accounts
