import discord
from discord.ext import commands
import requests
import os
from dotenv import load_dotenv
from urllib.parse import urlparse

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
HTB_BEARER_TOKEN = os.getenv("HTB_BEARER_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

DEFAULT_HEADERS = {
    "Authorization": f"Bearer {HTB_BEARER_TOKEN}",
    "Accept": "application/json",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/117.0.0.0 Safari/537.36 Edg/117.0.2045.55"
    ),
}

def is_valid_url(url: str) -> bool:
    if not url:
        return False
    url = url.strip()
    parsed = urlparse(url)
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


@bot.command()
async def osint(ctx, machine_name: str):
    HTB_MACHINE_PROFILE_URL = f"https://labs.hackthebox.com/api/v4/machine/profile/{machine_name}"

    try:
        machine_response = requests.get(HTB_MACHINE_PROFILE_URL, headers=DEFAULT_HEADERS)
        if machine_response.status_code != 200:
            await ctx.send(f"Failed to fetch machine '{machine_name}'. Error: {machine_response.status_code}")
            return

        machine_data = machine_response.json().get("info", {})
        if not machine_data:
            await ctx.send(f"Machine '{machine_name}' not found or no data returned.")
            return

        difficulty = machine_data.get("difficultyText", "Unknown")
        os_type = machine_data.get("os", "Unknown")
        creator1 = machine_data.get("maker", {})
        creator2 = machine_data.get("maker2", {})
        machine_id = machine_data.get("id")

        avatar_path = machine_data.get("avatar", "")
        avatar_url = None
        if avatar_path:
            avatar_path = avatar_path.strip()
            avatar_url = (avatar_path if avatar_path.startswith("http")
                          else f"https://htb-mp-prod-public-storage.s3.eu-central-1.amazonaws.com{avatar_path}")
        if avatar_url and is_valid_url(avatar_url):
            machine_thumbnail = avatar_url
        else:
            machine_thumbnail = None

        embed = discord.Embed(
            title=f"Machine: {machine_data.get('name', 'Unknown')}",
            description=f"**Difficulty:** {difficulty}\n**OS:** {os_type}",
            color=discord.Color.blue()
        )
        if machine_thumbnail:
            embed.set_thumbnail(url=machine_thumbnail)

        if creator1:
            profile_url_1 = f"https://app.hackthebox.com/profile/{creator1.get('id')}"
            embed.add_field(
                name="Maker 1",
                value=f"[{creator1.get('name', 'Unknown')}]({profile_url_1})",
                inline=False
            )
            embed.add_field(name="Maker 1 ID", value=creator1.get("id", "Unknown"), inline=True)

        if creator2:
            profile_url_2 = f"https://app.hackthebox.com/profile/{creator2.get('id')}"
            embed.add_field(
                name="Maker 2",
                value=f"[{creator2.get('name', 'Unknown')}]({profile_url_2})",
                inline=False
            )
            embed.add_field(name="Maker 2 ID", value=creator2.get("id", "Unknown"), inline=True)

        await ctx.send(embed=embed)

        for maker in [creator1, creator2]:
            if maker:
                await fetch_and_display_maker(ctx, maker.get("id"), skip_machine_id=machine_id)

    except Exception as e:
        await ctx.send(f"An error occurred: {e}")


async def fetch_and_display_maker(ctx, maker_id: int, skip_machine_id=None):
    HTB_USER_PROFILE_URL = f"https://labs.hackthebox.com/api/v4/user/profile/basic/{maker_id}"
    HTB_USER_CONTENT_URL = f"https://labs.hackthebox.com/api/v4/user/profile/content/{maker_id}"

    try:
        profile_response = requests.get(HTB_USER_PROFILE_URL, headers=DEFAULT_HEADERS)
        if profile_response.status_code != 200:
            await ctx.send(f"Failed to fetch profile for Maker ID {maker_id}. Error: {profile_response.status_code}")
            return

        profile_data = profile_response.json().get("profile", {})

        content_response = requests.get(HTB_USER_CONTENT_URL, headers=DEFAULT_HEADERS)
        content_data = content_response.json().get("profile", {}).get("content", {})

        avatar_path = profile_data.get("avatar", "")
        avatar_url = None
        if avatar_path:
            avatar_path = avatar_path.strip()
            if avatar_path.startswith("/"):
                avatar_url = f"https://account.hackthebox.com{avatar_path}"
            elif avatar_path.startswith("http"):
                avatar_url = avatar_path
        if avatar_url and is_valid_url(avatar_url):
            user_thumbnail = avatar_url
        else:
            user_thumbnail = None

        embed = discord.Embed(
            title=f"Maker: {profile_data.get('name', 'Unknown')}",
            color=discord.Color.gold()
        )
        if user_thumbnail:
            embed.set_thumbnail(url=user_thumbnail)

        embed.add_field(name="System Owns", value=profile_data.get("system_owns", "N/A"), inline=True)
        embed.add_field(name="User Owns", value=profile_data.get("user_owns", "N/A"), inline=True)
        embed.add_field(name="Respects", value=profile_data.get("respects", "N/A"), inline=True)
        embed.add_field(name="Rank", value=profile_data.get("rank", "N/A"), inline=True)
        embed.add_field(name="Ranking", value=profile_data.get("ranking", "N/A"), inline=True)
        embed.add_field(name="Country", value=profile_data.get("country_name", "N/A"), inline=True)
        embed.add_field(name="Time Zone", value=profile_data.get("timezone", "N/A"), inline=True)

        team = profile_data.get("team", {})
        if team:
            team_profile_url = f"https://app.hackthebox.com/team/{team.get('id')}"
            embed.add_field(
                name="Team",
                value=f"[{team.get('name')}]({team_profile_url})",
                inline=True
            )
            embed.add_field(name="Team Ranking", value=team.get("ranking", "N/A"), inline=True)

        if profile_data.get("github"):
            embed.add_field(name="GitHub", value=f"[GitHub]({profile_data.get('github')})", inline=False)
        if profile_data.get("linkedin"):
            embed.add_field(name="LinkedIn", value=f"[LinkedIn]({profile_data.get('linkedin')})", inline=False)
        if profile_data.get("twitter"):
            embed.add_field(name="Twitter", value=f"[Twitter]({profile_data.get('twitter')})", inline=False)

        await ctx.send(embed=embed)

        await display_content(ctx, content_data,
                              username=profile_data.get("name", "Unknown"),
                              skip_machine_id=skip_machine_id)

    except Exception as e:
        await ctx.send(f"An error occurred while fetching maker details: {e}")


async def display_content(ctx, content_data, username, skip_machine_id=None):
    embed = discord.Embed(
        title=f"Content Created by {username}",
        color=discord.Color.blue()
    )

    def split_content(content, max_length=1024):
        lines = content.split("\n")
        chunks, current_chunk = [], ""
        for line in lines:
            if len(current_chunk) + len(line) + 1 > max_length:
                chunks.append(current_chunk)
                current_chunk = line + "\n"
            else:
                current_chunk += line + "\n"
        if current_chunk:
            chunks.append(current_chunk)
        return chunks

    if content_data.get("machines"):
        machine_list = ""
        for machine in content_data["machines"]:
            if skip_machine_id and machine.get("id") == skip_machine_id:
                continue
            avatar_path = machine.get("machine_avatar", "")
            avatar_url = f"https://labs.hackthebox.com{avatar_path}" if avatar_path else ""
            machine_list += (
                f"- **[{machine['name']}]"
                f"(https://app.hackthebox.com/machines/{machine['id']})** "
                f"(OS: {machine['os']}, Difficulty: {machine['difficulty']}, "
                f"Rating: {machine['rating']})\n"
                f"  Avatar: {avatar_url}\n"
            )
        if machine_list:
            for i, chunk in enumerate(split_content(machine_list)):
                embed.add_field(
                    name=f"Created Machines (Part {i + 1})" if i > 0 else "Created Machines",
                    value=chunk,
                    inline=False
                )

    if content_data.get("writeups"):
        writeup_list = ""
        for writeup in content_data["writeups"]:
            writeup_list += (
                f"- **{writeup['machine_name']}** (Type: {writeup['type']})\n"
                f"  URL: {writeup['url']}\n"
            )
        if writeup_list:
            for i, chunk in enumerate(split_content(writeup_list)):
                embed.add_field(
                    name=f"Created Writeups (Part {i + 1})" if i > 0 else "Created Writeups",
                    value=chunk,
                    inline=False
                )

    if content_data.get("challenges"):
        challenge_list = ""
        for challenge in content_data["challenges"]:
            avatar_path = challenge.get("challenge_avatar", "")
            avatar_url = f"https://labs.hackthebox.com{avatar_path}" if avatar_path else ""
            challenge_list += (
                f"- **{challenge['name']}** (Category: {challenge['category']}, Difficulty: {challenge['difficulty']})\n"
                f"  Avatar: {avatar_url}\n"
            )
        if challenge_list:
            for i, chunk in enumerate(split_content(challenge_list)):
                embed.add_field(
                    name=f"Created Challenges (Part {i + 1})" if i > 0 else "Created Challenges",
                    value=chunk,
                    inline=False
                )

    if not embed.fields:
        embed.description = "No content created by this user."

    await ctx.send(embed=embed)


@bot.event
async def on_ready():
    print(f"Bot connected as {bot.user}")


bot.run(DISCORD_TOKEN)
