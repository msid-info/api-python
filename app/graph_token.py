import httpx
import os
import time

TENANT_ID = os.environ['TENANT_ID']
CLIENT_ID = os.environ['CLIENT_ID']
CLIENT_SECRET = os.environ['CLIENT_SECRET']

current_token = None
current_token_expiration = time.time()

def get_graph_token() -> str:
    global current_token
    global current_token_expiration

    # check if the token is still valid
    if current_token and current_token_expiration > time.time():
        return current_token

    # request a new token
    response = httpx.post(
        url=f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token",
        data={
            "grant_type": "client_credentials",
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "scope": "https://graph.microsoft.com/.default"
        }
    )

    # set the new token and expiration
    response.raise_for_status()
    data = response.json()
    current_token = data['access_token']
    current_token_expiration = time.time() + data['expires_in']

    return current_token
