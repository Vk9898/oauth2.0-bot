import base64
import hashlib
import os
import re
import json
import requests
import redis
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

def generate_code_verifier():
    code_verifier = base64.urlsafe_b64encode(os.urandom(30)).decode("utf-8")
    return re.sub("[^a-zA-Z0-9]+", "", code_verifier)

def generate_code_challenge(code_verifier):
    code_challenge = hashlib.sha256(code_verifier.encode("utf-8")).digest()
    code_challenge = base64.urlsafe_b64encode(code_challenge).decode("utf-8")
    return code_challenge.replace("=", "")

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
    
    code_verifier = generate_code_verifier()
    code_challenge = generate_code_challenge(code_verifier)
    
    # Store the code verifier in the session
    session["code_verifier"] = code_verifier
    session["oauth_state"] = twitter.state
    
    authorization_url, state = twitter.authorization_url(
        auth_url, code_challenge=code_challenge, code_challenge_method="S256"
    )
    return redirect(authorization_url)

@app.route("/oauth/callback", methods=["GET"])
def callback():
    try:
        code = request.args.get("code")
        state = request.args.get("state")
        
        # Verify state parameter to prevent CSRF
        if state != session.get("oauth_state"):
            raise ValueError("State mismatch. Potential CSRF attack.")
        
        code_verifier = session.get("code_verifier")
        print(f"Code received: {code}")
        print(f"Code verifier from session: {code_verifier}")
        
        token = twitter.fetch_token(
            token_url=token_url,
            client_secret=client_secret,
            code_verifier=code_verifier,
            code=code,
        )
        print(f"Token fetched: {token}")
        st_token = '"{}"'.format(token)
        j_token = json.loads(st_token)
        r.set("token", j_token)
        doggie_fact = parse_dog_fact()
        payload = {"text": "{}".format(doggie_fact)}
        response = post_tweet(payload, token).json()
        return response
    except Exception as e:
        print(f"Error during callback: {e}")
        return f"Internal Server Error: {e}", 500

if __name__ == "__main__":
    print(app.url_map)
    app.run()
