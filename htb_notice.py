import discord
import requests
import os
import asyncio
import sqlite3
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
HTB_BEARER_TOKEN = os.getenv("HTB_BEARER_TOKEN")
ERROR_CHANNEL_ID = int(os.getenv("ERROR_CHANNEL_ID"))

intents = discord.Intents.default()
intents.message_content = True  
client = discord.Client(intents=intents)

HTB_NOTICES_URL = "https://labs.hackthebox.com/api/v4/notices"

headers = {
    "Authorization": f"Bearer {HTB_BEARER_TOKEN}",
    "Accept": "application/json"
}

def initialize_db():
    """Initialize the SQLite database."""
    conn = sqlite3.connect('notices.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sent_notices (
            id INTEGER PRIMARY KEY
        )
    ''')
    conn.commit()
    conn.close()

def notice_exists(notice_id):
    """Check if a notice with the given ID already exists in the database."""
    conn = sqlite3.connect('notices.db')
    cursor = conn.cursor()
    cursor.execute('SELECT 1 FROM sent_notices WHERE id = ?', (notice_id,))
    exists = cursor.fetchone() is not None
    conn.close()
    return exists

def add_notice(notice_id):
    """Add a notice ID to the database."""
    conn = sqlite3.connect('notices.db')
    cursor = conn.cursor()
    cursor.execute('INSERT INTO sent_notices (id) VALUES (?)', (notice_id,))
    conn.commit()
    conn.close()

async def fetch_notices():
    """Fetch notices from HTB API."""
    try:
        response = requests.get(HTB_NOTICES_URL, headers=headers)
        if response.status_code == 200:
            return response.json().get("data", [])
        else:
            print(f"Failed to fetch notices. Status code: {response.status_code}")
    except Exception as e:
        print(f"Error fetching notices: {e}")
    return []

def extract_message_info(notice):
    """Extract machine name and error/warning message from the notice."""
    machine_url = notice.get("url")
    machine_name = machine_url.split("/")[-1] if machine_url else "N/A"
    message = notice.get("message", "No message provided")
    notice_type = notice.get("type", "info")
    return machine_name, message, notice_type

def get_embed_color_and_emoji(notice_type):
    """Return the appropriate color and emoji based on the notice type."""
    if notice_type == "error":
        return discord.Color.red(), "❌"
    elif notice_type == "warning":
        return discord.Color.orange(), "⚠️"
    elif notice_type == "success":
        return discord.Color.green(), "✅"
    else:
        return discord.Color.blue(), "ℹ️"

async def send_notice_to_channel(notice):
    """Send a formatted message to the appropriate Discord channel."""
    machine_name, message, notice_type = extract_message_info(notice)
    channel = client.get_channel(ERROR_CHANNEL_ID)
    if channel:
        color, emoji = get_embed_color_and_emoji(notice_type)
        embed = discord.Embed(
            title=f"{emoji} {notice_type.capitalize()} Notice for {machine_name}",
            description=message,
            color=color
        )
        await channel.send(embed=embed)

async def check_htb_notices():
    """Check for new notices and post them to the Discord channel."""
    await client.wait_until_ready()
    while not client.is_closed():
        notices = await fetch_notices()
        for notice in notices:
            notice_id = notice.get("id")
            
            if not notice_exists(notice_id):
                await send_notice_to_channel(notice)
                add_notice(notice_id)
        
        await asyncio.sleep(60)

@client.event
async def on_ready():
    print(f"Bot connected as {client.user}")
    client.loop.create_task(check_htb_notices())

initialize_db()
client.run(DISCORD_TOKEN)
