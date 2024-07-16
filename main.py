import base64
import hashlib
import os
import re
import json
import time
import requests
import tweepy
from requests_oauthlib import OAuth2Session
from flask import Flask, redirect, session, request

app = Flask(__name__)
app.secret_key = os.urandom(50)

# OAuth2 Configuration
client_id = os.environ.get("CLIENT_ID")
client_secret = os.environ.get("CLIENT_SECRET")
auth_url = "https://twitter.com/i/oauth2/authorize"
token_url = "https://api.twitter.com/2/oauth2/token"
redirect_uri = os.environ.get("REDIRECT_URI")

# Debugging prints for environment variables
print(f"CLIENT_ID: {client_id}")
print(f"CLIENT_SECRET: {client_secret}")
print(f"REDIRECT_URI: {redirect_uri}")

scopes = ["tweet.read", "users.read", "tweet.write", "offline.access"]

code_verifier = base64.urlsafe_b64encode(os.urandom(30)).decode("utf-8")
code_verifier = re.sub("[^a-zA-Z0-9]+", "", code_verifier)

code_challenge = hashlib.sha256(code_verifier.encode("utf-8")).digest()
code_challenge = base64.urlsafe_b64encode(code_challenge).decode("utf-8")
code_challenge = code_challenge.replace("=", "")

def make_token():
    return OAuth2Session(client_id, redirect_uri=redirect_uri, scope=scopes)

# Tweepy Configuration
bearer_token = os.environ.get('BEARER_TOKEN')

# Debugging print for bearer token
print(f"BEARER_TOKEN: {bearer_token}")

client = tweepy.Client(bearer_token=bearer_token, wait_on_rate_limit=True)

# Fetch bot's username and ID
try:
    me = client.get_me()
    BOT_USERNAME = me.data.username
    BOT_ID = me.data.id
    print("Bot username:", BOT_USERNAME)
except tweepy.TweepyException as e:
    print(f"Error authenticating with Twitter API: {e}")
    exit(1)

# Chatbase API details
CHATBASE_API_KEY = os.environ.get('CHATBASE_API_KEY')
CHATBASE_API_URL = 'https://www.chatbase.co/api/v1/chat'
CHATBOT_ID = os.environ.get('CHATBOT_ID')

# Debugging prints for Chatbase
print(f"CHATBASE_API_KEY: {CHATBASE_API_KEY}")
print(f"CHATBOT_ID: {CHATBOT_ID}")

def get_chatbot_response(user_message):
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {CHATBASE_API_KEY}',
    }
    data = {
        "messages": [{"content": user_message, "role": "user"}],
        "chatbot_id": CHATBOT_ID,
    }

    response = requests.post(CHATBASE_API_URL, headers=headers, json=data)

    if response.status_code == 200:
        return response.json()['messages'][-1]['content']
    else:
        print(f"Error: {response.status_code}, {response.text}")
        return "I'm sorry, I couldn't process your request."

def get_recent_mentions(since_id=None):
    try:
        return client.get_users_mentions(
            id=BOT_ID,
            since_id=since_id,
            tweet_fields=['id', 'text'],
            max_results=10,
            expansions=['author_id']
        )
    except tweepy.TweepyException as e:
        print(f"Error fetching mentions: {e}")
        return None

def post_reply(tweet_id, text, author_id=None):
    try:
        text = f"@{author_id} {text}"
        client.create_tweet(text=text, in_reply_to_tweet_id=tweet_id)
    except tweepy.TweepyException as e:
        print(f"Error posting reply: {e}")

def process_mentions():
    since_id = fetch_last_processed_mention_id()

    while True:
        mentions = get_recent_mentions(since_id)

        if mentions is None:
            time.sleep(60)
            continue

        if mentions.data:
            for mention in mentions.data:
                author_id = [user.username for user in mentions.includes['users'] if user.id == mention.author_id][0]
                user_message = mention.text
                print(f"Mention received from @{author_id}: {mention.text}")

                chatbot_response = get_chatbot_response(user_message)
                if len(chatbot_response) <= 280:
                    post_reply(mention.id, chatbot_response, author_id)
                else:
                    print(f"Error: Chatbot response too long.")
    
            since_id = mentions.data[-1].id
            store_last_processed_mention_id(since_id)

        time.sleep(60)

def fetch_last_processed_mention_id():
    try:
        with open("last_mention_id.txt", "r") as f:
            return int(f.read().strip())
    except FileNotFoundError:
        return None

def store_last_processed_mention_id(mention_id):
    with open("last_mention_id.txt", "w") as f:
        f.write(str(mention_id))

@app.route("/")
def demo():
    twitter = make_token()
    authorization_url, state = twitter.authorization_url(
        auth_url, code_challenge=code_challenge, code_challenge_method="S256"
    )
    session["oauth_state"] = state
    return redirect(authorization_url)

@app.route("/oauth/callback", methods=["GET"])
def callback():
    try:
        code = request.args.get("code")
        twitter = make_token()
        token = twitter.fetch_token(
            token_url,
            client_secret=client_secret,
            code=code,
            code_verifier=code_verifier,
        )
        payload = {"text": "Hello, world!"}
        post_tweet(payload, token)
        return "Tweet posted successfully!"
    except Exception as e:
        return f"An error occurred: {e}"

if __name__ == "__main__":
    try:
        client.get_me()
    except tweepy.TweepyException as e:
        print(f"Error authenticating with Twitter API: {e}")
        exit(1)

    process_mentions()
    app.run(debug=True)
