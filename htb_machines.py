from datetime import datetime, timezone, timedelta
import discord
import requests
import os
import asyncio
import sqlite3
from dotenv import load_dotenv
import aiohttp

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
HTB_BEARER_TOKEN = os.getenv("HTB_BEARER_TOKEN")
MACHINES_CHANNEL_ID = int(os.getenv("MACHINES_CHANNEL_ID"))
MACHINES_VOICE_CHANNEL_ID = int(os.getenv("MACHINES_VOICE_CHANNEL_ID"))
HTB_FORUM_CHANNEL_ID = int(os.getenv("FORUM_CHANNEL_ID"))

intents = discord.Intents.default()
intents.message_content = False
client = discord.Client(intents=intents)

HTB_MACHINES_URL = "https://labs.hackthebox.com/api/v4/machine/unreleased"

headers = {
    "Authorization": f"Bearer {HTB_BEARER_TOKEN}",
    "Accept": "application/json",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36 Edg/117.0.2045.55"
}

def initialize_db():
    """Initialize the SQLite database."""
    conn = sqlite3.connect('machines.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tracked_machines (
            id INTEGER PRIMARY KEY,
            name TEXT,
            os TEXT,
            difficulty TEXT,
            release_date TEXT
        )
    ''')
    conn.commit()
    conn.close()

def machine_exists(machine_id):
    """Check if a machine with the given ID already exists in the database."""
    conn = sqlite3.connect('machines.db')
    cursor = conn.cursor()
    cursor.execute('SELECT 1 FROM tracked_machines WHERE id = ?', (machine_id,))
    exists = cursor.fetchone() is not None
    conn.close()
    return exists

def add_machine(machine):
    """Add a new machine to the database."""
    conn = sqlite3.connect('machines.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO tracked_machines (id, name, os, difficulty, release_date)
        VALUES (?, ?, ?, ?, ?)
    ''', (machine['id'], machine['name'], machine['os'], machine['difficulty_text'], machine['release']))
    conn.commit()
    conn.close()

def get_embed_color(difficulty):
    """Get the color based on machine difficulty."""
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

def format_machine_message(machine):
    """Format the machine information into a Discord embed message."""
    release_date_str = machine['release']
    release_date = datetime.fromisoformat(release_date_str.replace("Z", "+00:00")).astimezone(timezone.utc)
    release_date_utc_plus_1 = release_date + timedelta(hours=0)
    discord_timestamp = f"<t:{int(release_date_utc_plus_1.timestamp())}:F>"

    creator = machine['firstCreator'][0]['name'] if machine.get('firstCreator') else 'Unknown'

    embed_color = get_embed_color(machine['difficulty_text'])
    embed = discord.Embed(
        title=f"Machine: **{machine['name']}**",
        description=f"Release Date: {discord_timestamp}",
        color=embed_color
    )
    embed.add_field(name="Difficulty", value=machine['difficulty_text'], inline=True)
    embed.add_field(name="Operating System", value=machine['os'], inline=True)
    embed.add_field(name="Creator", value=creator, inline=True)
    if 'retiring' in machine and machine['retiring']:
        retiring = machine['retiring']
        embed.add_field(
            name="Retiring Machine",
            value=f"{retiring['name']} ({retiring['difficulty_text']}) - {retiring['os']}",
            inline=False
        )
    embed.set_thumbnail(url=f"https://labs.hackthebox.com{machine['avatar']}")
    return embed

async def download_image(url):
    """Download an image from the given URL."""
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status == 200:
                return await response.read()
            else:
                print(f"Failed to download image: {url}")
                return None

async def create_discord_event(machine):
    voice_channel = await resolve_channel(MACHINES_VOICE_CHANNEL_ID)
    if not isinstance(voice_channel, discord.VoiceChannel):
        print("Error: MACHINES_VOICE_CHANNEL_ID is not a voice channel.")
        return

    guild = voice_channel.guild
    me = guild.me or await guild.fetch_member(client.user.id)

    guild_perms = me.guild_permissions
    chan_perms = voice_channel.permissions_for(me)

    if not guild_perms.manage_events:
        print("Error: Bot lacks 'Manage Events' permission in the guild.")
        return
    if not chan_perms.view_channel:
        print("Error: Bot lacks 'View Channel' for the voice channel.")
        return
    if not chan_perms.connect:
        print("Error: Bot lacks 'Connect' for the voice channel.")
        return

    creator = machine['firstCreator'][0]['name'] if machine.get('firstCreator') else 'Unknown'
    event_name = f"{machine['name']}"
    machine_link = f"https://app.hackthebox.com/machines/{machine['name']}"
    event_description = f"{machine['os']} - {machine['difficulty_text']} - by {creator}\n\n{machine_link}"

    start = datetime.fromisoformat(machine['release'].replace("Z", "+00:00")).astimezone(timezone.utc)
    end = start + timedelta(hours=2)

    image_data = await download_image(f"https://htb-mp-prod-public-storage.s3.eu-central-1.amazonaws.com{machine['avatar']}")

    try:
        await guild.create_scheduled_event(
            name=event_name,
            description=event_description,
            start_time=start,
            end_time=end,
            channel=voice_channel,
            entity_type=discord.EntityType.voice,
            privacy_level=discord.PrivacyLevel.guild_only,
            image=image_data
        )
        print(f"Event created: {event_name}")
    except Exception as e:
        print(f"Failed to create event: {e}")



async def create_forum_thread(machine):
    """Create a forum thread for the new machine with the avatar image as the thread's cover."""
    forum_channel = client.get_channel(HTB_FORUM_CHANNEL_ID)
    if not forum_channel:
        print("Error: Forum channel not found!")
        return

    try:
        available_tags = {tag.name.lower(): tag for tag in forum_channel.available_tags}
        os_tag = available_tags.get(machine['os'].lower())
        difficulty_tag = available_tags.get(machine['difficulty_text'].lower())

        if not os_tag or not difficulty_tag:
            print(f"Error: Missing tags for OS='{machine['os']}' or Difficulty='{machine['difficulty_text']}'")
            return

        avatar_url = f"https://htb-mp-prod-public-storage.s3.eu-central-1.amazonaws.com{machine['avatar']}"
        image_data = await download_image(avatar_url)
        creator = machine['firstCreator'][0]['name'] if machine.get('firstCreator') else 'Unknown'

        avatar_file_path = f"{machine['name']}_avatar.png"
        with open(avatar_file_path, "wb") as f:
            f.write(image_data)

        thread_name = machine['name']
        machine_link = f"https://app.hackthebox.com/machines/{machine['name']}"
        thread_content = (
            f"**Machine Name:** {machine['name']}\n"
            f"**Operating System:** {machine['os']}\n"
            f"**Difficulty:** {machine['difficulty_text']}\n"
            f"**Creator:** {creator}\n\n"
            f"[View Machine on Hack The Box]({machine_link})"
        )

        avatar_file = discord.File(fp=avatar_file_path, filename=f"{machine['name']}_avatar.png")

        thread_with_message = await forum_channel.create_thread(
            name=thread_name,
            content=thread_content,
            file=avatar_file,
            applied_tags=[os_tag, difficulty_tag],
            auto_archive_duration=1440,
        )

        thread = thread_with_message.thread

        print(f"Thread created successfully: {thread.name} (ID: {thread.id})")

        os.remove(avatar_file_path)

    except discord.HTTPException as e:
        print(f"Failed to create thread for machine {machine['name']}: {e}")


async def send_machine_to_channel(machine):
    channel = await resolve_channel(MACHINES_CHANNEL_ID)

    if isinstance(channel, discord.ForumChannel):
        print("MACHINES_CHANNEL_ID is a Forum channel; skipping .send() here.")
    else:
        me = channel.guild.me or await channel.guild.fetch_member(client.user.id)
        perms = channel.permissions_for(me)
        if not perms.send_messages:
            print("Error: Bot lacks 'Send Messages' permission.")
            return
        if not perms.embed_links:
            print("Error: Bot lacks 'Embed Links' permission.")
            return

        embed = format_machine_message(machine)
        await channel.send(embed=embed)

    await create_discord_event(machine)
    await create_forum_thread(machine)


async def resolve_channel(channel_id: int):
    ch = client.get_channel(channel_id)  # cache
    if ch is not None:
        return ch
    try:
        ch = await client.fetch_channel(channel_id)  # API
        return ch
    except discord.NotFound:
        raise RuntimeError(f"Channel {channel_id} not found or bot not in its guild.")
    except discord.Forbidden:
        raise RuntimeError(f"Bot lacks permission to view channel {channel_id}.")


async def fetch_machines():
    """Fetch unreleased machines from the HTB API."""
    try:
        response = requests.get(HTB_MACHINES_URL, headers=headers)
        if response.status_code == 200:
            return response.json().get("data", [])
        else:
            print(f"Failed to fetch machines. Status code: {response.status_code}")
    except Exception as e:
        print(f"Error fetching machines: {e}")
    return []

async def check_new_machines():
    """Check for new machines and post them to the Discord channel."""
    await client.wait_until_ready()
    while not client.is_closed():
        machines = await fetch_machines()
        for machine in machines:
            machine_id = machine['id']
            if not machine_exists(machine_id):
                await send_machine_to_channel(machine)
                add_machine(machine)
        await asyncio.sleep(600)

@client.event
async def on_ready():
    print(f"Bot connected as {client.user}")
    client.loop.create_task(check_new_machines())

initialize_db()
client.run(DISCORD_TOKEN)
