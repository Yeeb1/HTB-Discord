from datetime import datetime, timezone, timedelta
import discord
import requests
import os
import asyncio
import sqlite3
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
HTB_BEARER_TOKEN = os.getenv("HTB_BEARER_TOKEN")
GENERAL_CHANNEL_ID = int(os.getenv("GENERAL_CHANNEL_ID"))
CHALL_VOICE_CHANNEL_ID = int(os.getenv("CHALL_VOICE_CHANNEL_ID"))
CHALL_FORUM_CHANNEL_ID = int(os.getenv("CHALL_FORUM_CHANNEL_ID"))

intents = discord.Intents.default()
intents.message_content = False
client = discord.Client(intents=intents)

HTB_CHALLENGES_URL = "https://labs.hackthebox.com/api/v4/challenges?state=unreleased"

headers = {
    "Authorization": f"Bearer {HTB_BEARER_TOKEN}",
    "Accept": "application/json",
    "User-Agent": "HTB-Challenge-Bot/1.0"
}

def initialize_db():
    """Initialize the SQLite database."""
    conn = sqlite3.connect('challenges.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tracked_challenges (
            id INTEGER PRIMARY KEY,
            name TEXT,
            difficulty TEXT,
            category TEXT,
            release_date TEXT
        )
    ''')
    conn.commit()
    conn.close()

def challenge_exists(challenge_id):
    """Check if a challenge with the given ID already exists in the database."""
    conn = sqlite3.connect('challenges.db')
    cursor = conn.cursor()
    cursor.execute('SELECT 1 FROM tracked_challenges WHERE id = ?', (challenge_id,))
    exists = cursor.fetchone() is not None
    conn.close()
    return exists

def add_challenge(challenge):
    """Add a new challenge to the database."""
    conn = sqlite3.connect('challenges.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO tracked_challenges (id, name, difficulty, category, release_date)
        VALUES (?, ?, ?, ?, ?)
    ''', (challenge['id'], challenge['name'], challenge['difficulty'], challenge['category_name'], challenge['release_date']))
    conn.commit()
    conn.close()

def get_embed_color(difficulty):
    """Get the color based on challenge difficulty."""
    if difficulty.lower() == "easy":
        return discord.Color.green()
    elif difficulty.lower() == "medium":
        return discord.Color.orange()
    elif difficulty.lower() == "hard":
        return discord.Color.red()
    elif difficulty.lower() == "insane":
        return discord.Color.from_rgb(0, 0, 0)
    else:
        return discord.Color.blue()

def format_challenge_message(challenge):
    """Format the challenge information into a Discord embed message."""
    release_date_str = challenge['release_date']
    release_date = datetime.fromisoformat(release_date_str.replace("Z", "+00:00")).astimezone(timezone.utc)
    release_date_utc_plus_1 = release_date + timedelta(hours=-1)
    discord_timestamp = f"<t:{int(release_date_utc_plus_1.timestamp())}:F>"

    embed_color = get_embed_color(challenge['difficulty'])
    embed = discord.Embed(
        title=f" Challenge: **{challenge['name']}**",
        description=f"Release Date: {discord_timestamp}",
        color=embed_color
    )
    embed.add_field(name="Difficulty", value=challenge['difficulty'], inline=True)
    embed.add_field(name="Category", value=challenge['category_name'], inline=True)
    return embed

async def create_discord_event(challenge):
    """Create a Discord scheduled event for the challenge."""
    guild = None
    if client.guilds:
        guild = client.guilds[0]  

    if not guild:
        print("Error: Bot is not connected to any guilds.")
        return

    voice_channel = guild.get_channel(CHALL_VOICE_CHANNEL_ID)
    
    if voice_channel is None:
        print("Error: Voice channel not found!")
        return
    
    guild_permissions = guild.me.guild_permissions
    voice_permissions = voice_channel.permissions_for(guild.me)

    print(f"Guild Permissions: {guild_permissions}")
    print(f"Voice Channel Permissions: {voice_permissions}")

    if not guild_permissions.manage_events:
        print("Error: Bot lacks 'Manage Events' permission in the guild.")
        return
    if not voice_permissions.view_channel:
        print("Error: Bot lacks 'View Channel' permission for the voice channel.")
        return
    if not voice_permissions.connect:
        print("Error: Bot lacks 'Connect' permission for the voice channel.")
        return

    event_name = f"[{challenge['category_name']}] {challenge['name']}"
    event_description = f"{challenge['category_name']} - {challenge['difficulty']}"
    
    release_date_str = challenge['release_date']
    release_date = datetime.fromisoformat(release_date_str.replace("Z", "+00:00")).astimezone(timezone.utc)
    release_date_utc_plus_1 = release_date + timedelta(hours=1)
    event_start_time = release_date_utc_plus_1
    event_end_time = event_start_time + timedelta(hours=2)
    
    try:
        await guild.create_scheduled_event(
            name=event_name,
            description=event_description,
            start_time=event_start_time,
            end_time=event_end_time,
            channel=voice_channel,
            entity_type=discord.EntityType.voice,
            privacy_level=discord.PrivacyLevel.guild_only
        )
        print(f"Event created: {event_name}")
    except Exception as e:
        print(f"Failed to create event: {e}")

async def create_forum_thread(challenge):
    """Create a forum thread for the challenge with difficulty and category tags."""
    forum_channel = client.get_channel(CHALL_FORUM_CHANNEL_ID)
    if not forum_channel:
        print("Error: Forum channel not found!")
        return

    # Fetch available tags
    available_tags = {tag.name.lower(): tag for tag in forum_channel.available_tags}
    difficulty_tag = available_tags.get(challenge['difficulty'].lower())
    category_tag = available_tags.get(challenge['category_name'].lower())

    if not difficulty_tag or not category_tag:
        print(f"Error: Missing tags for Difficulty='{challenge['difficulty']}' or Category='{challenge['category_name']}'")
        return

    thread_name = challenge['name']
    thread_content = (
        f"**Challenge Name:** {challenge['name']}\n"
        f"**Category:** {challenge['category_name']}\n"
        f"**Difficulty:** {challenge['difficulty']}\n"
        f"Release Date: <t:{int(datetime.fromisoformat(challenge['release_date'].replace('Z', '+00:00')).timestamp())}:F>"
    )

    try:
        thread_with_message = await forum_channel.create_thread(
            name=thread_name,
            content=thread_content,
            applied_tags=[difficulty_tag, category_tag],
            auto_archive_duration=1440
        )
        thread = thread_with_message.thread
        print(f"Thread created successfully: {thread.name} (ID: {thread.id})")
    except Exception as e:
        print(f"Failed to create thread for challenge {challenge['name']}: {e}")



async def send_challenge_to_channel(challenge):
    """Send a new challenge notification and create an event."""
    channel = client.get_channel(GENERAL_CHANNEL_ID)

    permissions = channel.permissions_for(channel.guild.me)
    print(f"Text Channel Permissions: {permissions}")

    if not permissions.send_messages:
        print("Error: Bot lacks 'Send Messages' permission.")
        return
    if not permissions.embed_links:
        print("Error: Bot lacks 'Embed Links' permission.")
        return

    
    if channel is None:
        print("Error: Channel not found!")
        return
    
    embed = format_challenge_message(challenge)
    await channel.send(embed=embed)
    await create_discord_event(challenge)
    await create_forum_thread(challenge)


async def fetch_challenges():
    """Fetch unreleased challenges from the HTB API."""
    try:
        response = requests.get(HTB_CHALLENGES_URL, headers=headers)
        if response.status_code == 200:
            return response.json().get("data", [])
        else:
            print(f"Failed to fetch challenges. Status code: {response.status_code}")
    except Exception as e:
        print(f"Error fetching challenges: {e}")
    return []

async def check_new_challenges():
    """Check for new challenges and post them to the Discord channel."""
    await client.wait_until_ready()
    while not client.is_closed():
        challenges = await fetch_challenges()
        for challenge in challenges:
            challenge_id = challenge['id']
            if not challenge_exists(challenge_id):
                await send_challenge_to_channel(challenge)
                add_challenge(challenge)
        await asyncio.sleep(600)

@client.event
async def on_ready():
    print(f"Bot connected as {client.user}")
    client.loop.create_task(check_new_challenges())

initialize_db()
client.run(DISCORD_TOKEN)
