"""OSINT module for automatic machine information gathering."""

import asyncio
import logging
import requests
from urllib.parse import urlparse
from typing import Dict, Any, Optional

import discord
from discord.ext import commands

logger = logging.getLogger(__name__)

class OSINTHelper:
    """Helper class for automatic OSINT information gathering."""

    def __init__(self, config):
        self.config = config
        self.headers = {
            "Authorization": f"Bearer {config.get('api.htb_bearer_token')}",
            "Accept": "application/json",
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/117.0.0.0 Safari/537.36 Edg/117.0.2045.55"
            ),
        }

    @staticmethod
    def is_valid_url(url: str) -> bool:
        """Check if URL is valid."""
        if not url:
            return False
        url = url.strip()
        parsed = urlparse(url)
        return parsed.scheme in ("http", "https") and bool(parsed.netloc)

    async def gather_machine_info(self, machine_name: str) -> Optional[Dict[str, Any]]:
        """Gather comprehensive OSINT information for a machine."""
        api_url = f"https://labs.hackthebox.com/api/v4/machine/profile/{machine_name}"

        try:
            machine_response = requests.get(api_url, headers=self.headers)
            if machine_response.status_code != 200:
                logger.error(f"Failed to fetch machine '{machine_name}'. Error: {machine_response.status_code}")
                return None

            machine_data = machine_response.json().get("info", {})
            if not machine_data:
                logger.warning(f"Machine '{machine_name}' not found or no data returned.")
                return None

            # Gather maker information
            makers_info = []
            for maker_key in ['maker', 'maker2']:
                maker = machine_data.get(maker_key)
                if maker:
                    maker_info = await self.gather_maker_info(maker.get("id"), machine_data.get("id"))
                    if maker_info:
                        makers_info.append(maker_info)

            return {
                'machine': machine_data,
                'makers': makers_info
            }

        except Exception as e:
            logger.error(f"Error gathering machine info for {machine_name}: {e}")
            return None

    async def gather_maker_info(self, maker_id: int, skip_machine_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """Gather maker profile and content information."""
        profile_url = f"https://labs.hackthebox.com/api/v4/user/profile/basic/{maker_id}"
        content_url = f"https://labs.hackthebox.com/api/v4/user/profile/content/{maker_id}"

        try:
            # Fetch profile data
            profile_response = requests.get(profile_url, headers=self.headers)
            if profile_response.status_code != 200:
                logger.error(f"Failed to fetch profile for Maker ID {maker_id}. Error: {profile_response.status_code}")
                return None

            profile_data = profile_response.json().get("profile", {})

            # Fetch content data
            content_response = requests.get(content_url, headers=self.headers)
            content_data = {}
            if content_response.status_code == 200:
                content_data = content_response.json().get("profile", {}).get("content", {})

            return {
                'profile': profile_data,
                'content': content_data,
                'skip_machine_id': skip_machine_id
            }

        except Exception as e:
            logger.error(f"Error gathering maker info for ID {maker_id}: {e}")
            return None

    async def get_machine_details(self, machine_name: str) -> Optional[Dict[str, Any]]:
        """Get detailed machine information including first bloods."""
        api_url = f"https://labs.hackthebox.com/api/v4/machine/profile/{machine_name}"

        try:
            response = requests.get(api_url, headers=self.headers)
            if response.status_code != 200:
                logger.warning(f"Failed to fetch machine details for '{machine_name}'. Status: {response.status_code}")
                return None

            machine_data = response.json().get("info", {})
            if not machine_data:
                return None

            # Extract relevant details
            return {
                'userBlood': machine_data.get('userBlood'),
                'rootBlood': machine_data.get('rootBlood'),
                'stars': machine_data.get('stars'),
                'points': machine_data.get('points'),
                'user_owns_count': machine_data.get('user_owns_count'),
                'root_owns_count': machine_data.get('root_owns_count')
            }

        except Exception as e:
            logger.warning(f"Error fetching machine details for {machine_name}: {e}")
            return None

    async def get_challenge_details(self, challenge_id: int) -> Optional[Dict[str, Any]]:
        """Get detailed challenge information including difficulty and bloods."""
        try:
            detail_url = f"https://labs.hackthebox.com/api/v4/challenge/info/{challenge_id}"
            response = requests.get(detail_url, headers=self.headers)

            if response.status_code == 200:
                detail_data = response.json()
                challenge_data = detail_data.get('challenge', {})


                return {
                    'difficulty': challenge_data.get('difficulty', 'Unknown'),
                    'solves': challenge_data.get('solves', 0),
                    'first_blood_user': challenge_data.get('first_blood_user')
                }
            else:
                logger.warning(f"Failed to fetch challenge details for ID {challenge_id}: {response.status_code}")
                return None

        except Exception as e:
            logger.warning(f"Error fetching challenge details for ID {challenge_id}: {e}")
            return None

    async def post_osint_to_thread(self, thread: discord.Thread, machine_name: str) -> bool:
        """Post OSINT information to a forum thread."""
        try:
            osint_data = await self.gather_machine_info(machine_name)
            if not osint_data:
                logger.warning(f"No OSINT data found for machine: {machine_name}")
                return False

            # Post machine information
            await self.post_machine_info(thread, osint_data['machine'])

            # Post maker information
            for maker_info in osint_data['makers']:
                await self.post_maker_info(thread, maker_info)

            logger.info(f"Posted OSINT information for {machine_name} to thread {thread.name}")
            return True

        except Exception as e:
            logger.error(f"Failed to post OSINT info for {machine_name}: {e}")
            return False

    async def post_machine_info(self, thread: discord.Thread, machine_data: Dict[str, Any]) -> None:
        """Post machine information to thread."""
        difficulty = machine_data.get("difficultyText", "Unknown")
        os_type = machine_data.get("os", "Unknown")
        creator1 = machine_data.get("maker", {})
        creator2 = machine_data.get("maker2", {})

        # Handle avatar
        avatar_path = machine_data.get("avatar", "")
        machine_thumbnail = None
        if avatar_path:
            avatar_path = avatar_path.strip()
            avatar_url = (avatar_path if avatar_path.startswith("http")
                         else f"https://htb-mp-prod-public-storage.s3.eu-central-1.amazonaws.com{avatar_path}")
            if self.is_valid_url(avatar_url):
                machine_thumbnail = avatar_url

        # Create embed
        embed = discord.Embed(
            title=f"🔍 Machine Details: {machine_data.get('name', 'Unknown')}",
            description=f"**Difficulty:** {difficulty}\n**OS:** {os_type}",
            color=discord.Color.blue()
        )

        if machine_thumbnail:
            embed.set_thumbnail(url=machine_thumbnail)

        # Add creator information
        if creator1:
            profile_url = f"https://app.hackthebox.com/profile/{creator1.get('id')}"
            embed.add_field(
                name="Maker 1",
                value=f"[{creator1.get('name', 'Unknown')}]({profile_url})",
                inline=False
            )
            embed.add_field(name="Maker 1 ID", value=creator1.get("id", "Unknown"), inline=True)

        if creator2:
            profile_url = f"https://app.hackthebox.com/profile/{creator2.get('id')}"
            embed.add_field(
                name="Maker 2",
                value=f"[{creator2.get('name', 'Unknown')}]({profile_url})",
                inline=False
            )
            embed.add_field(name="Maker 2 ID", value=creator2.get("id", "Unknown"), inline=True)

        await thread.send(embed=embed)

    async def post_maker_info(self, thread: discord.Thread, maker_info: Dict[str, Any]) -> None:
        """Post maker profile and content information to thread."""
        profile_data = maker_info['profile']
        content_data = maker_info['content']
        skip_machine_id = maker_info.get('skip_machine_id')

        # Post profile information
        await self.post_maker_profile(thread, profile_data)

        # Post content information
        await self.post_maker_content(thread, content_data, profile_data.get("name", "Unknown"), skip_machine_id)

    async def post_maker_profile(self, thread: discord.Thread, profile_data: Dict[str, Any]) -> None:
        """Post maker profile embed to thread."""
        # Handle avatar
        avatar_path = profile_data.get("avatar", "")
        user_thumbnail = None
        if avatar_path:
            avatar_path = avatar_path.strip()
            if avatar_path.startswith("/"):
                avatar_url = f"https://account.hackthebox.com{avatar_path}"
            elif avatar_path.startswith("http"):
                avatar_url = avatar_path
            else:
                avatar_url = None

            if avatar_url and self.is_valid_url(avatar_url):
                user_thumbnail = avatar_url

        # Create embed
        embed = discord.Embed(
            title=f"👤 Maker Profile: {profile_data.get('name', 'Unknown')}",
            color=discord.Color.gold()
        )

        if user_thumbnail:
            embed.set_thumbnail(url=user_thumbnail)

        # Add profile fields
        embed.add_field(name="System Owns", value=profile_data.get("system_owns", "N/A"), inline=True)
        embed.add_field(name="User Owns", value=profile_data.get("user_owns", "N/A"), inline=True)
        embed.add_field(name="Respects", value=profile_data.get("respects", "N/A"), inline=True)
        embed.add_field(name="Rank", value=profile_data.get("rank", "N/A"), inline=True)
        embed.add_field(name="Ranking", value=profile_data.get("ranking", "N/A"), inline=True)
        embed.add_field(name="Country", value=profile_data.get("country_name", "N/A"), inline=True)
        embed.add_field(name="Time Zone", value=profile_data.get("timezone", "N/A"), inline=True)

        # Add team info
        team = profile_data.get("team", {})
        if team:
            team_profile_url = f"https://app.hackthebox.com/team/{team.get('id')}"
            embed.add_field(
                name="Team",
                value=f"[{team.get('name')}]({team_profile_url})",
                inline=True
            )
            embed.add_field(name="Team Ranking", value=team.get("ranking", "N/A"), inline=True)

        # Add social links
        for social in ['github', 'linkedin', 'twitter']:
            if profile_data.get(social):
                embed.add_field(
                    name=social.capitalize(),
                    value=f"[{social.capitalize()}]({profile_data.get(social)})",
                    inline=False
                )

        await thread.send(embed=embed)

    async def post_maker_content(self, thread: discord.Thread, content_data: Dict[str, Any],
                                username: str, skip_machine_id: Optional[int] = None) -> None:
        """Post maker content information to thread."""
        embed = discord.Embed(
            title=f"📊 Content Created by {username}",
            color=discord.Color.blue()
        )

        def split_content(content: str, max_length: int = 1024) -> list:
            """Split content into chunks that fit in embed fields."""
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

        # Add machines (show all machines, no limits)
        if content_data.get("machines"):
            # Sort machines by rating first, then by ID (most recent)
            machines = sorted(content_data["machines"], key=lambda x: (x.get('rating', 0), x.get('id', 0)), reverse=True)

            machine_list = ""
            machine_count = 0

            for machine in machines:
                if skip_machine_id and machine.get("id") == skip_machine_id:
                    continue

                machine_count += 1
                # Get first blood info for all machines (with rate limit handling)
                first_blood_info = ""
                machine_details = await self.get_machine_details(machine['name'])
                if machine_details:
                    user_blood = machine_details.get('userBlood')
                    root_blood = machine_details.get('rootBlood')

                    if user_blood and root_blood:
                        first_blood_info = f" | 🩸 {user_blood['user']['name']}/{root_blood['user']['name']}"
                    elif user_blood:
                        first_blood_info = f" | 🩸 {user_blood['user']['name']}"

                # Add small delay to avoid rate limiting
                await asyncio.sleep(0.2)

                machine_list += (
                    f"- **[{machine['name']}]"
                    f"(https://app.hackthebox.com/machines/{machine['id']})** "
                    f"({machine['os']} | {machine['difficulty']} | ⭐{machine['rating']}/5 | "
                    f"👤{machine['user_owns']} | 🔐{machine['system_owns']}{first_blood_info})\n"
                )

            if machine_list:
                for i, chunk in enumerate(split_content(machine_list)):
                    embed.add_field(
                        name=f"Created Machines (Part {i + 1})" if i > 0 else "Created Machines",
                        value=chunk,
                        inline=False
                    )

        # Add writeups
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

        # Add challenges
        if content_data.get("challenges"):
            challenge_list = ""
            for challenge in content_data["challenges"]:
                # Safely get challenge fields with fallbacks
                challenge_name = challenge.get('name', 'Unknown')
                challenge_category = challenge.get('category', challenge.get('category_name', 'Unknown'))
                challenge_rating = challenge.get('rating', 'N/A')
                challenge_id = challenge.get('id', '')

                # Get detailed challenge info for difficulty and bloods
                detailed_info = await self.get_challenge_details(challenge_id)
                difficulty_text = "Unknown"
                bloods_info = ""
                solve_count = ""

                if detailed_info:
                    difficulty_text = detailed_info.get('difficulty', 'Unknown')
                    solves = detailed_info.get('solves', 0)
                    if solves > 0:
                        solve_count = f" | 👤{solves}"

                    # Get first blood info
                    first_blood_user = detailed_info.get('first_blood_user')
                    if first_blood_user:
                        bloods_info = f" | 🩸 {first_blood_user}"


                # Add small delay to avoid rate limiting
                await asyncio.sleep(0.1)

                # Create enhanced challenge entry with difficulty, rating, and bloods
                challenge_list += (
                    f"- **[{challenge_name}](https://app.hackthebox.com/challenges/{challenge_id})** "
                    f"({challenge_category} | {difficulty_text} | ⭐{challenge_rating}{solve_count}{bloods_info})\n"
                )

            if challenge_list:
                for i, chunk in enumerate(split_content(challenge_list)):
                    embed.add_field(
                        name=f"Created Challenges (Part {i + 1})" if i > 0 else "Created Challenges",
                        value=chunk,
                        inline=False
                    )

        # Handle empty content
        if not embed.fields:
            embed.description = "No content created by this user."

        await thread.send(embed=embed)

class OSINTCommands(commands.Cog):
    """OSINT command handlers for machine and user lookups."""

    def __init__(self, config):
        self.config = config
        self.headers = {
            "Authorization": f"Bearer {config.get('api.htb_bearer_token')}",
            "Accept": "application/json",
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/117.0.0.0 Safari/537.36 Edg/117.0.2045.55"
            ),
        }

    @staticmethod
    def is_valid_url(url: str) -> bool:
        """Check if URL is valid."""
        if not url:
            return False
        url = url.strip()
        parsed = urlparse(url)
        return parsed.scheme in ("http", "https") and bool(parsed.netloc)

    @commands.command()
    async def osint(self, ctx, machine_name: str):
        """Fetch machine profile and creator details."""
        api_url = f"https://labs.hackthebox.com/api/v4/machine/profile/{machine_name}"

        try:
            # Fetch machine data
            machine_response = requests.get(api_url, headers=self.headers)
            if machine_response.status_code != 200:
                await ctx.send(f"Failed to fetch machine '{machine_name}'. Error: {machine_response.status_code}")
                return

            machine_data = machine_response.json().get("info", {})
            if not machine_data:
                await ctx.send(f"Machine '{machine_name}' not found or no data returned.")
                return

            # Process machine data
            await self.send_machine_info(ctx, machine_data)

            # Process makers
            for maker_key in ['maker', 'maker2']:
                maker = machine_data.get(maker_key)
                if maker:
                    await self.fetch_and_display_maker(ctx, maker.get("id"), skip_machine_id=machine_data.get("id"))

        except Exception as e:
            logger.error(f"Error in OSINT command: {e}")
            await ctx.send(f"An error occurred: {e}")

    async def send_machine_info(self, ctx, machine_data: Dict[str, Any]) -> None:
        """Send machine information embed."""
        difficulty = machine_data.get("difficultyText", "Unknown")
        os_type = machine_data.get("os", "Unknown")
        creator1 = machine_data.get("maker", {})
        creator2 = machine_data.get("maker2", {})

        # Handle avatar
        avatar_path = machine_data.get("avatar", "")
        machine_thumbnail = None
        if avatar_path:
            avatar_path = avatar_path.strip()
            avatar_url = (avatar_path if avatar_path.startswith("http")
                         else f"https://htb-mp-prod-public-storage.s3.eu-central-1.amazonaws.com{avatar_path}")
            if self.is_valid_url(avatar_url):
                machine_thumbnail = avatar_url

        # Create embed
        embed = discord.Embed(
            title=f"Machine: {machine_data.get('name', 'Unknown')}",
            description=f"**Difficulty:** {difficulty}\n**OS:** {os_type}",
            color=discord.Color.blue()
        )

        if machine_thumbnail:
            embed.set_thumbnail(url=machine_thumbnail)

        # Add creator information
        if creator1:
            profile_url = f"https://app.hackthebox.com/profile/{creator1.get('id')}"
            embed.add_field(
                name="Maker 1",
                value=f"[{creator1.get('name', 'Unknown')}]({profile_url})",
                inline=False
            )
            embed.add_field(name="Maker 1 ID", value=creator1.get("id", "Unknown"), inline=True)

        if creator2:
            profile_url = f"https://app.hackthebox.com/profile/{creator2.get('id')}"
            embed.add_field(
                name="Maker 2",
                value=f"[{creator2.get('name', 'Unknown')}]({profile_url})",
                inline=False
            )
            embed.add_field(name="Maker 2 ID", value=creator2.get("id", "Unknown"), inline=True)

        await ctx.send(embed=embed)

    async def fetch_and_display_maker(self, ctx, maker_id: int, skip_machine_id: Optional[int] = None) -> None:
        """Fetch and display maker profile and content."""
        profile_url = f"https://labs.hackthebox.com/api/v4/user/profile/basic/{maker_id}"
        content_url = f"https://labs.hackthebox.com/api/v4/user/profile/content/{maker_id}"

        try:
            # Fetch profile data
            profile_response = requests.get(profile_url, headers=self.headers)
            if profile_response.status_code != 200:
                await ctx.send(f"Failed to fetch profile for Maker ID {maker_id}. Error: {profile_response.status_code}")
                return

            profile_data = profile_response.json().get("profile", {})

            # Fetch content data
            content_response = requests.get(content_url, headers=self.headers)
            content_data = content_response.json().get("profile", {}).get("content", {})

            # Send profile info
            await self.send_maker_profile(ctx, profile_data)

            # Send content info
            await self.send_maker_content(ctx, content_data, profile_data.get("name", "Unknown"), skip_machine_id)

        except Exception as e:
            logger.error(f"Error fetching maker details: {e}")
            await ctx.send(f"An error occurred while fetching maker details: {e}")

    async def send_maker_profile(self, ctx, profile_data: Dict[str, Any]) -> None:
        """Send maker profile embed."""
        # Handle avatar
        avatar_path = profile_data.get("avatar", "")
        user_thumbnail = None
        if avatar_path:
            avatar_path = avatar_path.strip()
            if avatar_path.startswith("/"):
                avatar_url = f"https://account.hackthebox.com{avatar_path}"
            elif avatar_path.startswith("http"):
                avatar_url = avatar_path
            else:
                avatar_url = None

            if avatar_url and self.is_valid_url(avatar_url):
                user_thumbnail = avatar_url

        # Create embed
        embed = discord.Embed(
            title=f"Maker: {profile_data.get('name', 'Unknown')}",
            color=discord.Color.gold()
        )

        if user_thumbnail:
            embed.set_thumbnail(url=user_thumbnail)

        # Add profile fields
        embed.add_field(name="System Owns", value=profile_data.get("system_owns", "N/A"), inline=True)
        embed.add_field(name="User Owns", value=profile_data.get("user_owns", "N/A"), inline=True)
        embed.add_field(name="Respects", value=profile_data.get("respects", "N/A"), inline=True)
        embed.add_field(name="Rank", value=profile_data.get("rank", "N/A"), inline=True)
        embed.add_field(name="Ranking", value=profile_data.get("ranking", "N/A"), inline=True)
        embed.add_field(name="Country", value=profile_data.get("country_name", "N/A"), inline=True)
        embed.add_field(name="Time Zone", value=profile_data.get("timezone", "N/A"), inline=True)

        # Add team info
        team = profile_data.get("team", {})
        if team:
            team_profile_url = f"https://app.hackthebox.com/team/{team.get('id')}"
            embed.add_field(
                name="Team",
                value=f"[{team.get('name')}]({team_profile_url})",
                inline=True
            )
            embed.add_field(name="Team Ranking", value=team.get("ranking", "N/A"), inline=True)

        # Add social links
        for social in ['github', 'linkedin', 'twitter']:
            if profile_data.get(social):
                embed.add_field(
                    name=social.capitalize(),
                    value=f"[{social.capitalize()}]({profile_data.get(social)})",
                    inline=False
                )

        await ctx.send(embed=embed)

    async def send_maker_content(self, ctx, content_data: Dict[str, Any], username: str, skip_machine_id: Optional[int] = None) -> None:
        """Send maker content embed."""
        embed = discord.Embed(
            title=f"Content Created by {username}",
            color=discord.Color.blue()
        )

        def split_content(content: str, max_length: int = 1024) -> list:
            """Split content into chunks that fit in embed fields."""
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

        # Add machines
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

        # Add writeups
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

        # Add challenges
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

        # Handle empty content
        if not embed.fields:
            embed.description = "No content created by this user."

        await ctx.send(embed=embed)