from datetime import datetime, timezone, timedelta
import discord
from discord.ext import commands
import requests
import os
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
HTB_BEARER_TOKEN = os.getenv("HTB_BEARER_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)


@bot.command()
async def osint(ctx, machine_name: str):
    """Fetch machine and maker details from HTB API and send as a message."""
    HTB_MACHINE_PROFILE_URL = f"https://labs.hackthebox.com/api/v4/machine/profile/{machine_name}"
    headers = {
        "Authorization": f"Bearer {HTB_BEARER_TOKEN}",
        "Accept": "application/json"
    }

    try:
        machine_response = requests.get(HTB_MACHINE_PROFILE_URL, headers=headers)
        if machine_response.status_code != 200:
            await ctx.send(f"Failed to fetch machine '{machine_name}'. Error: {machine_response.status_code}")
            return

        machine_data = machine_response.json().get('info', {})
        if not machine_data:
            await ctx.send(f"Machine '{machine_name}' not found or no data returned.")
            return

        difficulty = machine_data.get('difficultyText', 'Unknown')
        os = machine_data.get('os', 'Unknown')
        creator1 = machine_data.get('maker', {})
        creator2 = machine_data.get('maker2', {})
        avatar_url = f"https://labs.hackthebox.com{machine_data.get('avatar', '')}"

        embed = discord.Embed(
            title=f"Machine: {machine_data.get('name', 'Unknown')}",
            description=f"**Difficulty:** {difficulty}\n**OS:** {os}",
            color=discord.Color.blue()
        )
        embed.set_thumbnail(url=avatar_url)

        if creator1:
            embed.add_field(name="Maker 1", value=f"[{creator1.get('name', 'Unknown')}]({creator1.get('profile_url', '')})", inline=False)
            embed.add_field(name="Maker 1 ID", value=creator1.get('id', 'Unknown'), inline=True)

        if creator2:
            embed.add_field(name="Maker 2", value=f"[{creator2.get('name', 'Unknown')}]({creator2.get('profile_url', '')})", inline=False)
            embed.add_field(name="Maker 2 ID", value=creator2.get('id', 'Unknown'), inline=True)

        await ctx.send(embed=embed)

        for maker in [creator1, creator2]:
            if maker:
                await fetch_and_display_maker(ctx, maker.get('id'))

    except Exception as e:
        await ctx.send(f"An error occurred: {e}")


async def fetch_and_display_maker(ctx, maker_id: int):
    """Fetch and display details about a maker."""
    HTB_USER_PROFILE_URL = f"https://labs.hackthebox.com/api/v4/user/profile/basic/{maker_id}"
    HTB_USER_CONTENT_URL = f"https://labs.hackthebox.com/api/v4/user/profile/content/{maker_id}"
    headers = {
        "Authorization": f"Bearer {HTB_BEARER_TOKEN}",
        "Accept": "application/json"
    }

    try:
        profile_response = requests.get(HTB_USER_PROFILE_URL, headers=headers)
        if profile_response.status_code != 200:
            await ctx.send(f"Failed to fetch profile for Maker ID {maker_id}. Error: {profile_response.status_code}")
            return

        profile_data = profile_response.json().get('profile', {})

        content_response = requests.get(HTB_USER_CONTENT_URL, headers=headers)
        content_data = content_response.json().get('profile', {}).get('content', {})

        embed = discord.Embed(
            title=f"Maker: {profile_data.get('name', 'Unknown')}",
            color=discord.Color.gold()
        )
        embed.set_thumbnail(url=f"https://labs.hackthebox.com{profile_data.get('avatar', '')}")

        embed.add_field(name="System Owns", value=profile_data.get('system_owns', 'N/A'), inline=True)
        embed.add_field(name="User Owns", value=profile_data.get('user_owns', 'N/A'), inline=True)
        embed.add_field(name="Respects", value=profile_data.get('respects', 'N/A'), inline=True)
        embed.add_field(name="Rank", value=profile_data.get('rank', 'N/A'), inline=True)
        embed.add_field(name="Ranking", value=profile_data.get('ranking', 'N/A'), inline=True)
        embed.add_field(name="Country", value=profile_data.get('country_name', 'N/A'), inline=True)
        embed.add_field(name="Time Zone", value=profile_data.get('timezone', 'N/A'), inline=True)

        team = profile_data.get('team', {})
        if team:
            embed.add_field(name="Team", value=f"[{team.get('name')}]({team.get('profile_url', '')})", inline=True)
            embed.add_field(name="Team Ranking", value=team.get('ranking', 'N/A'), inline=True)

        if profile_data.get('github'):
            embed.add_field(name="GitHub", value=f"[GitHub]({profile_data.get('github')})", inline=False)
        if profile_data.get('linkedin'):
            embed.add_field(name="LinkedIn", value=f"[LinkedIn]({profile_data.get('linkedin')})", inline=False)
        if profile_data.get('twitter'):
            embed.add_field(name="Twitter", value=f"[Twitter]({profile_data.get('twitter')})", inline=False)

        await ctx.send(embed=embed)

        await display_content(ctx, content_data, username=profile_data.get('name', 'Unknown'))

    except Exception as e:
        await ctx.send(f"An error occurred while fetching maker details: {e}")


async def display_content(ctx, content_data, username):
    """Display created content details, handling Discord's character limits."""
    embed = discord.Embed(
        title=f"Content Created by {username}",
        color=discord.Color.blue()
    )

    def split_content(content, max_length=1024):
        """Split content into chunks of at most max_length characters."""
        lines = content.split('\n')
        chunks = []
        current_chunk = ""
        for line in lines:
            if len(current_chunk) + len(line) + 1 > max_length:
                chunks.append(current_chunk)
                current_chunk = line + '\n'
            else:
                current_chunk += line + '\n'
        if current_chunk:
            chunks.append(current_chunk)
        return chunks

    if content_data.get("machines"):
        machine_list = ""
        for machine in content_data["machines"]:
            machine_list += (
                f"- **[{machine['name']}]"
                f"(https://app.hackthebox.com/machines/{machine['id']})** "
                f"(OS: {machine['os']}, Difficulty: {machine['difficulty']}, Rating: {machine['rating']})\n"
            )
        machine_chunks = split_content(machine_list)
        for i, chunk in enumerate(machine_chunks):
            embed.add_field(
                name=f"Created Machines (Part {i + 1})" if len(machine_chunks) > 1 else "Created Machines",
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
        writeup_chunks = split_content(writeup_list)
        for i, chunk in enumerate(writeup_chunks):
            embed.add_field(
                name=f"Created Writeups (Part {i + 1})" if len(writeup_chunks) > 1 else "Created Writeups",
                value=chunk,
                inline=False
            )

    if content_data.get("challenges"):
        challenge_list = ""
        for challenge in content_data["challenges"]:
            challenge_list += (
                f"- **{challenge['name']}** (Category: {challenge['category']}, Difficulty: {challenge['difficulty']})\n"
                f"  URL: https://labs.hackthebox.com{challenge['challenge_avatar']}\n"
            )
        challenge_chunks = split_content(challenge_list)
        for i, chunk in enumerate(challenge_chunks):
            embed.add_field(
                name=f"Created Challenges (Part {i + 1})" if len(challenge_chunks) > 1 else "Created Challenges",
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
