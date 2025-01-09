import discord
import sqlite3
import re
import json
import asyncio
import http.client
import os
import time



DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
LINKWARDEN_API_URL = os.getenv("LINKWARDEN_API_URL")
LINKWARDEN_TOKEN = os.getenv("LINKWARDEN_TOKEN")
CATEGORIES_TO_MONITOR = os.getenv("CATEGORIES_TO_MONITOR", "").split(",") # monitors all channels in a specific category for the sake of ease

if not DISCORD_TOKEN:
    raise ValueError("DISCORD_TOKEN environment variable is not set.")
if not LINKWARDEN_API_URL:
    raise ValueError("LINKWARDEN_API_URL environment variable is not set.")
if not LINKWARDEN_TOKEN:
    raise ValueError("LINKWARDEN_TOKEN environment variable is not set.")
if not CATEGORIES_TO_MONITOR or CATEGORIES_TO_MONITOR == ['']:
    raise ValueError("CATEGORIES_TO_MONITOR environment variable is not set or invalid.")

intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
intents.message_content = True
client = discord.Client(intents=intents)

DB_FILE = "links.db"

# Global rate limiter status
last_sent_time = 0
links_sent_this_minute = 0

def initialize_db():
    """Initialize the SQLite database."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel_name TEXT,
            link TEXT,
            processed INTEGER DEFAULT 0
        )
    ''')
    conn.commit()
    conn.close()

def save_link(channel_name, link):
    """Save a new link to the database if it's not already present."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('SELECT 1 FROM links WHERE link = ?', (link,))
    if not cursor.fetchone():
        cursor.execute('INSERT INTO links (channel_name, link) VALUES (?, ?)', (channel_name, link))
        conn.commit()
    conn.close()

async def process_channel_history(channel):
    """Process the message history of a channel to extract links."""
    try:
        async for message in channel.history(limit=None):
            extract_links_from_message(message)
    except Exception as e:
        print(f"Error processing channel {channel.name}: {e}")

def extract_links_from_message(message):
    """Extract links from a message and save them."""
    links = re.findall(r'(https?://\S+)', message.content)
    for link in links:
        save_link(message.channel.name, link)

@client.event
async def on_ready():
    print(f"Bot connected as {client.user}")

    # Process all existing messages in the channels of specified categories, to safe already posted links
    for guild in client.guilds:
        for category in guild.categories:
            if str(category.id) in CATEGORIES_TO_MONITOR:
                for channel in category.channels:
                    if isinstance(channel, discord.TextChannel):
                        print(f"Processing history for channel: {channel.name}")
                        await process_channel_history(channel)

    print("Finished processing existing messages. Now watching for new messages...")
    asyncio.create_task(process_links())

@client.event
async def on_message(message):
    """Listen for new messages and extract links."""
    if isinstance(message.channel.category, discord.CategoryChannel):
        if str(message.channel.category.id) in CATEGORIES_TO_MONITOR:
            extract_links_from_message(message)

def get_collections():
    """Fetch existing collections from Linkwarden."""
    try:
        conn = http.client.HTTPSConnection(LINKWARDEN_API_URL)
        conn.request("GET", "/api/v1/collections", headers={"Authorization": f"Bearer {LINKWARDEN_TOKEN}"})
        response = conn.getresponse()
        data = response.read()
        data = json.loads(data)

        if "response" in data and isinstance(data["response"], list):
            return {collection["name"]: {"id": collection["id"], "name": collection["name"]} for collection in data["response"]}

        print(f"Unexpected data format: {data}")
        return {}

    except Exception as e:
        print(f"Error fetching collections: {e}")
        return {}

def create_collection(collection_name):
    """Create a new collection in Linkwarden."""
    collections = get_collections()

    if collection_name in collections:
        print(f"Collection already exists: {collection_name}")
        return collections[collection_name]  

    try:
        conn = http.client.HTTPSConnection(LINKWARDEN_API_URL)
        payload = json.dumps({
            "name": collection_name,
            "description": f"Links from {collection_name}",
            "color": "#000000"
        })
        headers = {
            "Authorization": f"Bearer {LINKWARDEN_TOKEN}",
            "Content-Type": "application/json"
        }
        conn.request("POST", "/api/v1/collections", payload, headers)
        response = conn.getresponse()
        data = json.loads(response.read())

        if "response" in data:
            new_collection = data["response"]
            print(f"Collection created: {new_collection['name']}")
            return {"id": new_collection["id"], "name": new_collection["name"]}

        print(f"Failed to create collection: {data}")
        return None

    except Exception as e:
        print(f"Error creating collection: {e}")
        return None

async def process_links():
    """Send links to Linkwarden and mark them as processed."""
    collections = get_collections()

    while True:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('SELECT id, channel_name, link FROM links WHERE processed = 0 LIMIT 10')  # Send max 10 links at a time to prevent instance from overloading
        new_links = cursor.fetchall()

        if not new_links:
            conn.close()
            await asyncio.sleep(10)
            continue

        for link_id, channel_name, link in new_links:
            # Check if collection exists, if not, create it
            if channel_name not in collections:
                collection_data = create_collection(channel_name)
                if collection_data:
                    collections[channel_name] = collection_data  # Add to collections dictionary
                else:
                    print(f"Failed to create collection for channel: {channel_name}")
                    continue  # Skip this link if collection creation failed

            collection_id = collections[channel_name]["id"]
            try:
                conn_lw = http.client.HTTPSConnection(LINKWARDEN_API_URL)
                payload = json.dumps({
                    "url": link,
                    "type": "url",
                    "tags": [{"name": channel_name}],  # Use the channel name as a tag
                    "collection": {
                        "id": collection_id,
                        "name": channel_name
                    }
                })
                headers = {
                    "Authorization": f"Bearer {LINKWARDEN_TOKEN}",
                    "Content-Type": "application/json"
                }
                conn_lw.request("POST", "/api/v1/links", payload, headers)
                response = conn_lw.getresponse()
                response_data = response.read().decode("utf-8")
                response_json = json.loads(response_data)

                if response.status in {200, 201} and "response" in response_json:
                    # Mark the link as processed
                    cursor.execute('UPDATE links SET processed = 1 WHERE id = ?', (link_id,))
                    conn.commit()
                    print(f"Successfully sent link: {link}")
                else:
                    print(f"Unexpected response structure or missing data: {response_data}")

            except Exception as e:
                print(f"Error sending link to Linkwarden: {e}")

        conn.close()
        await asyncio.sleep(6) 

initialize_db()
client.run(DISCORD_TOKEN)
