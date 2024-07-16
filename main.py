import os
import base64
import hashlib
import re
import requests
import redis
from requests_oauthlib import OAuth2Session
from flask import Flask, redirect, session, request, jsonify

# Read the REDIS_URL from the environment variables
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

@app.route("/")
def demo():
    twitter = OAuth2Session(client_id, redirect_uri=redirect_uri, scope=scopes)
    
    code_verifier = generate_code_verifier()
    code_challenge = generate_code_challenge(code_verifier)
    
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
        
        if state != session.get("oauth_state"):
            return "State mismatch. Potential CSRF attack.", 400
        
        code_verifier = session.get("code_verifier")
        
        twitter = OAuth2Session(client_id, redirect_uri=redirect_uri, scope=scopes)
        
        token = twitter.fetch_token(
            token_url=token_url,
            client_secret=client_secret,
            code_verifier=code_verifier,
            code=code,
        )
        
        st_token = '"{}"'.format(token)
        j_token = json.loads(st_token)
        r.set("token", j_token)
        return f"Token fetched and stored: {token}"
    except Exception as e:
        return f"Error during callback: {e}", 500

if __name__ == "__main__":
    app.run()
