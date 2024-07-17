import json
import os
import time
import requests
import redis

# Redis Configuration
r = redis.from_url(os.environ["REDIS_URL"])

# Twitter API Configuration
def load_user_access_token():
    token_data = r.get("user_token")
    if token_data:
        return json.loads(token_data)
    else:
        print("User access token not found in Redis. Exiting.")
        exit(1)
    
bearer_token = load_user_access_token().get("access_token", None)
if bearer_token is None:
    print("Failed to load access token from Redis. Exiting.")
    exit(1)

# Chatbase API details 
CHATBASE_API_KEY = os.environ.get('CHATBASE_API_KEY')
CHATBASE_API_URL = 'https://www.chatbase.co/api/v1/chat'
CHATBOT_ID = os.environ.get('CHATBOT_ID')

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
        return response.json()['messages'][-1]['content']  # Get the last message (bot response)
    else:
        print(f"Error: {response.status_code}, {response.text}")
        return "I'm sorry, I couldn't process your request."

def get_bot_info():
    headers = {
        "Authorization": f"Bearer {bearer_token}"
    }
    response = requests.get("https://api.twitter.com/2/users/me", headers=headers)
    if response.status_code == 200:
        return response.json()["data"]
    else:
        print(f"Error fetching bot info: {response.status_code}, {response.text}")
        return None
    
def get_recent_mentions(since_id=None):
    headers = {
        "Authorization": f"Bearer {bearer_token}"
    }
    params = {
        "tweet.fields": "id,text,author_id,created_at",
        "expansions": "author_id",
        "max_results": 100 
    }
    if since_id:
        params["since_id"] = since_id

    response = requests.get(
        f"https://api.twitter.com/2/users/{BOT_ID}/mentions", 
        headers=headers, params=params
    )

    if response.status_code == 200:
        return response.json()
    else:
        print(f"Error fetching mentions: {response.status_code}, {response.text}")
        return None

def post_reply(tweet_id, text, author_id):
    headers = {
        "Authorization": f"Bearer {bearer_token}",
        "Content-Type": "application/json"
    }
    payload = {
        "text": f"@{author_id} {text}",
        "in_reply_to_tweet_id": tweet_id
    }
    response = requests.post("https://api.twitter.com/2/tweets", headers=headers, json=payload)
    if response.status_code != 201:
        print(f"Error posting reply: {response.status_code}, {response.text}")
        
def process_mentions():
    since_id = fetch_last_processed_mention_id()
    while True:
        mentions = get_recent_mentions(since_id)

        if mentions is None:  
            time.sleep(60)
            continue
        
        if "data" in mentions:
            mentions["data"].sort(key=lambda m: m["created_at"]) 

            for mention in mentions["data"]:
                author_id = [user["username"] for user in mentions["includes"]["users"] if user["id"] == mention["author_id"]][0]
                user_message = mention["text"]
                print(f"Mention received from @{author_id}: {mention['text']}")

                chatbot_response = get_chatbot_response(user_message)
                if len(chatbot_response) <= 280:
                    post_reply(mention["id"], chatbot_response, author_id)
                else:
                    print(f"Error: Chatbot response too long.")
            since_id = mentions["data"][-1]["id"]
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


if __name__ == "__main__":
    bot_info = get_bot_info()

    if bot_info is None:
        exit(1) 
    
    BOT_USERNAME = bot_info["username"]
    BOT_ID = bot_info["id"]
    print(f"Bot username: {BOT_USERNAME}, Bot ID: {BOT_ID}")

    process_mentions()
