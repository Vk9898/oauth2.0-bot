import base64
import hashlib
import os
import re
import json
import requests
import redis
import logging
from requests_oauthlib import OAuth2Session
from flask import Flask, redirect, session, request

r = redis.from_url(os.environ["REDIS_URL"])

app = Flask(__name__)
app.secret_key = os.urandom(50)

client_id = os.environ.get("CLIENT_ID")
client_secret = os.environ.get("CLIENT_SECRET")
auth_url = "https://twitter.com/i/oauth2/authorize"
token_url = "https://api.twitter.com/2/oauth2/token"
redirect_uri = os.environ.get("REDIRECT_URI")

scopes = ["tweet.read", "users.read", "tweet.write", "offline.access"]

code_verifier = base64.urlsafe_b64encode(os.urandom(30)).decode("utf-8")
code_verifier = re.sub("[^a-zA-Z0-9]+", "", code_verifier)

code_challenge = hashlib.sha256(code_verifier.encode("utf-8")).digest()
code_challenge = base64.urlsafe_b64encode(code_challenge).decode("utf-8")
code_challenge = code_challenge.replace("=", "")

def make_token():
    return OAuth2Session(client_id, redirect_uri=redirect_uri, scope=scopes)

def parse_dog_fact():
    url = "http://dog-api.kinduff.com/api/facts"
    dog_fact = requests.request("GET", url).json()
    return dog_fact["facts"][0]

def post_tweet(payload, token):
    print("Tweeting!")
    return requests.request(
        "POST",
        "https://api.twitter.com/2/tweets",
        json=payload,
        headers={
            "Authorization": "Bearer {}".format(token["access_token"]),
            "Content-Type": "application/json",
        },
    )

@app.route("/")
def demo():
    global twitter
    twitter = make_token()
    authorization_url, state = twitter.authorization_url(
        auth_url, code_challenge=code_challenge, code_challenge_method="S256"
    )
    session["oauth_state"] = state
    return redirect(authorization_url)

# ... (other imports)
import logging

# ... 
logging.basicConfig(level=logging.INFO)

@app.route("/oauth/callback", methods=["GET"])
def callback():
    try:
        # ... (fetch token as before)
        logging.info(f"Token fetched: {token}")

        # Store directly as a JSON string to avoid unnecessary conversions
        r.set("token", json.dumps(token))  
        logging.info("Token saved in Redis")
        # ... (rest of the code remains the same)
        doggie_fact = parse_dog_fact()
        payload = {"text": "{}".format(doggie_fact)}
        response = post_tweet(payload, token)
        if response.status_code == 201:
            return "Tweet posted successfully!"
        else:
            logging.error(f"Error posting tweet: {response.status_code}, {response.text}")
            return f"Error posting tweet: {response.text}", response.status_code
    except Exception as e:
        logging.error(f"Error during callback: {e}")
        return f"Internal Server Error: {e}", 500


if __name__ == "__main__":
    print(app.url_map)
    app.run()
