"""Challenge monitoring module."""

import asyncio
import logging
import requests
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional

import discord

from ..utils.discord_helpers import DiscordHelpers
from .osint import OSINTHelper

logger = logging.getLogger(__name__)

class ChallengeMonitor:
    """Monitors HTB unreleased challenges and posts to Discord."""

    def __init__(self, config, db_manager, client):
        self.config = config
        self.db_manager = db_manager
        self.client = client
        self.running = False

        # Initialize OSINT helper for automatic information gathering
        self.osint_helper = OSINTHelper(config)

        # HTB API configuration
        self.api_url = "https://labs.hackthebox.com/api/v4/challenges?state=unreleased"
        self.headers = {
            "Authorization": f"Bearer {config.get('api.htb_bearer_token')}",
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36 Edg/117.0.2045.55"
        }

        # Feature flags
        self.create_events = config.get('features.challenges.create_events', True)
        self.create_forum_threads = config.get('features.challenges.create_forum_threads', True)
        self.send_announcements = config.get('features.challenges.send_announcements', True)
        self.poll_interval = config.get_poll_interval('challenges')

        # Channel IDs
        self.general_channel_id = config.get_channel_id('general_channel_id')
        self.challenges_voice_channel_id = config.get_channel_id('challenges_voice_channel_id')
        self.challenges_forum_channel_id = config.get_channel_id('challenges_forum_channel_id')

    async def start(self) -> None:
        """Start the challenge monitoring loop."""
        self.running = True
        logger.info("Starting challenge monitor")

        await self.client.wait_until_ready()

        while self.running:
            try:
                await self.check_new_challenges()
                await asyncio.sleep(self.poll_interval)
            except Exception as e:
                logger.error(f"Error in challenge monitoring loop: {e}")
                await asyncio.sleep(60)  # Wait a minute before retrying

    async def stop(self) -> None:
        """Stop the challenge monitoring loop."""
        self.running = False
        logger.info("Stopping challenge monitor")

    async def fetch_challenges(self) -> List[Dict[str, Any]]:
        """Fetch unreleased challenges from HTB API."""
        try:
            response = requests.get(self.api_url, headers=self.headers)
            if response.status_code == 200:
                return response.json().get("data", [])
            else:
                logger.error(f"Failed to fetch challenges. Status code: {response.status_code}")
        except Exception as e:
            logger.error(f"Error fetching challenges: {e}")

        return []

    async def check_new_challenges(self) -> None:
        """Check for new challenges and process them."""
        challenges = await self.fetch_challenges()

        for challenge in challenges:
            challenge_id = challenge['id']

            if not self.db_manager.challenge_exists(challenge_id):
                logger.info(f"Found new challenge: {challenge['name']}")
                await self.process_new_challenge(challenge)
                self.db_manager.add_challenge(challenge)

    async def process_new_challenge(self, challenge: Dict[str, Any]) -> None:
        """Process a new challenge by sending announcements, creating events, etc."""
        # Validate challenge data
        required_fields = ['name', 'category_name', 'difficulty', 'release_date', 'id']
        for field in required_fields:
            if not challenge.get(field):
                logger.error(f"Challenge missing required field '{field}': {challenge}")
                return

        # Send announcement
        if self.send_announcements:
            await self.send_challenge_announcement(challenge)

        # Create Discord event
        if self.create_events:
            await self.create_challenge_event(challenge)

        # Create forum thread
        if self.create_forum_threads:
            await self.create_challenge_forum_thread(challenge)

    async def send_challenge_announcement(self, challenge: Dict[str, Any]) -> None:
        """Send challenge announcement to the configured channel."""
        if not self.general_channel_id:
            logger.warning("General channel ID not configured")
            return

        channel = await DiscordHelpers.resolve_channel(self.client, self.general_channel_id)
        if not channel:
            logger.error(f"Could not resolve general channel: {self.general_channel_id}")
            return

        # Check permissions
        me = channel.guild.me or await channel.guild.fetch_member(self.client.user.id)
        if not await DiscordHelpers.check_permissions(channel, me, ['send_messages', 'embed_links']):
            logger.error(f"Missing permissions for general channel: {channel.name}")
            return

        # Create and send embed
        embed = DiscordHelpers.create_challenge_embed(challenge)
        await channel.send(embed=embed)

        logger.info(f"Sent challenge announcement: {challenge['name']}")

    async def create_challenge_event(self, challenge: Dict[str, Any]) -> None:
        """Create a Discord scheduled event for the challenge release."""
        if not self.challenges_voice_channel_id:
            logger.warning("Challenges voice channel ID not configured")
            return

        voice_channel = await DiscordHelpers.resolve_channel(self.client, self.challenges_voice_channel_id)
        if not voice_channel or not isinstance(voice_channel, discord.VoiceChannel):
            logger.error(f"Invalid voice channel for events: {self.challenges_voice_channel_id}")
            return

        # Get detailed challenge information including creator
        challenge_details = await self.get_challenge_details(challenge['id'])

        # Prepare event data
        event_name = f"[{challenge['category_name']}] {challenge['name']}"

        # Build event description with creator information
        creator_info = "Unknown"
        if challenge_details and challenge_details.get('creator_name'):
            creator_info = challenge_details['creator_name']
            if challenge_details.get('creator2_name'):
                creator_info += f" & {challenge_details['creator2_name']}"

        challenge_link = f"https://app.hackthebox.com/challenges/{challenge['id']}"
        event_description = f"{challenge['category_name']} - {challenge['difficulty']} - by {creator_info}\n\n{challenge_link}"

        # Parse release time (use exact time from API)
        release_date = datetime.fromisoformat(challenge['release_date'].replace("Z", "+00:00")).astimezone(timezone.utc)
        start_time = release_date
        end_time = start_time + timedelta(hours=2)

        # Create event
        success = await DiscordHelpers.create_scheduled_event(
            guild=voice_channel.guild,
            name=event_name,
            description=event_description,
            start_time=start_time,
            end_time=end_time,
            voice_channel=voice_channel,
            image_data=None
        )

        if success:
            logger.info(f"Created Discord event for challenge: {challenge['name']}")

    async def create_challenge_forum_thread(self, challenge: Dict[str, Any]) -> None:
        """Create a forum thread for the challenge."""
        if not self.challenges_forum_channel_id:
            logger.warning("Challenges forum channel ID not configured")
            return

        forum_channel = await DiscordHelpers.resolve_channel(self.client, self.challenges_forum_channel_id)
        if not forum_channel or not isinstance(forum_channel, discord.ForumChannel):
            logger.error(f"Invalid forum channel: {self.challenges_forum_channel_id}")
            return

        # Prepare thread data
        thread_name = challenge['name']
        release_timestamp = int(datetime.fromisoformat(challenge['release_date'].replace('Z', '+00:00')).timestamp())

        thread_content = (
            f"**Challenge Name:** {challenge['name']}\n"
            f"**Category:** {challenge['category_name']}\n"
            f"**Difficulty:** {challenge['difficulty']}\n"
            f"Release Date: <t:{release_timestamp}:F>"
        )

        # Prepare tags - ensure they are valid strings
        tags = []
        if challenge.get('difficulty'):
            tags.append(str(challenge['difficulty']).strip())
        if challenge.get('category_name'):
            tags.append(str(challenge['category_name']).strip())

        # Create thread
        thread = await DiscordHelpers.create_forum_thread(
            forum_channel=forum_channel,
            name=thread_name,
            content=thread_content,
            tags=tags,
            file=None
        )

        if thread:
            logger.info(f"Created forum thread for challenge: {challenge['name']}")

            # Automatically post OSINT information to the thread
            await self.post_automatic_osint(thread, challenge['name'])

    async def post_automatic_osint(self, thread: discord.Thread, challenge_name: str) -> None:
        """Automatically post OSINT information to the forum thread."""
        try:
            logger.info(f"Gathering OSINT information for challenge: {challenge_name}")

            # Get challenge data from the unreleased challenges API
            challenges = await self.fetch_challenges()
            challenge_data = None

            for challenge in challenges:
                if challenge['name'] == challenge_name:
                    challenge_data = challenge
                    break

            if not challenge_data:
                logger.warning(f"Could not find challenge data for {challenge_name}")
                return

            # Create challenge OSINT embed
            await self.post_challenge_osint_embed(thread, challenge_data)

            logger.info(f"Successfully posted automatic OSINT for {challenge_name}")

        except Exception as e:
            logger.error(f"Error posting automatic OSINT for {challenge_name}: {e}")

    async def get_challenge_details(self, challenge_id: int) -> Optional[Dict[str, Any]]:
        """Get detailed challenge information including creator data."""
        try:
            detail_url = f"https://labs.hackthebox.com/api/v4/challenge/info/{challenge_id}"
            response = requests.get(detail_url, headers=self.headers)

            if response.status_code == 200:
                detail_data = response.json()
                return detail_data.get('challenge', {})
            else:
                logger.warning(f"Failed to fetch challenge details for ID {challenge_id}: {response.status_code}")
                return None

        except Exception as e:
            logger.error(f"Error fetching challenge details for ID {challenge_id}: {e}")
            return None

    async def post_challenge_osint_embed(self, thread: discord.Thread, challenge: Dict[str, Any]) -> None:
        """Post challenge-specific OSINT embed to thread."""
        try:
            # Get detailed challenge information including creator
            challenge_details = await self.get_challenge_details(challenge['id'])

            embed = discord.Embed(
                title=f"🔍 Challenge Intelligence: {challenge['name']}",
                color=DiscordHelpers.get_embed_color(challenge['difficulty'])
            )

            # Basic challenge info
            embed.add_field(name="📁 Category", value=challenge['category_name'], inline=True)
            embed.add_field(name="📊 Difficulty", value=challenge['difficulty'], inline=True)
            embed.add_field(name="🎯 Solves", value=str(challenge.get('solves', 0)), inline=True)

            # Creator information (from detailed data if available)
            if challenge_details and challenge_details.get('creator_name'):
                creator_name = challenge_details['creator_name']
                creator_info = creator_name

                # Add co-creator if exists
                if challenge_details.get('creator2_name'):
                    creator_info += f" & {challenge_details['creator2_name']}"

                embed.add_field(name="👤 Creator", value=creator_info, inline=True)

            # Release information
            if challenge.get('release_date'):
                release_timestamp = int(datetime.fromisoformat(challenge['release_date'].replace('Z', '+00:00')).timestamp())
                embed.add_field(name="📅 Release Date", value=f"<t:{release_timestamp}:F>", inline=False)

            # Play methods
            if challenge.get('play_methods'):
                methods = ", ".join(challenge['play_methods'])
                embed.add_field(name="🎮 Play Methods", value=methods, inline=True)

            # Challenge link
            challenge_link = f"https://app.hackthebox.com/challenges/{challenge['id']}"
            embed.add_field(name="🔗 Challenge Link", value=f"[View Challenge]({challenge_link})", inline=False)

            # Additional info if available
            if challenge.get('rating') is not None:
                embed.add_field(name="⭐ Rating", value=f"{challenge['rating']}/5", inline=True)

            if challenge.get('rating_count'):
                embed.add_field(name="📝 Reviews", value=str(challenge['rating_count']), inline=True)

            await thread.send(embed=embed)

            # Post creator OSINT information if we have creator details
            if challenge_details and challenge_details.get('creator_name'):
                await self.post_creator_osint_embed(thread, challenge_details)

        except Exception as e:
            logger.error(f"Failed to post challenge OSINT embed: {e}")

    async def post_creator_osint_embed(self, thread: discord.Thread, challenge_details: Dict[str, Any]) -> None:
        """Post creator OSINT information to thread."""
        try:
            creator_name = challenge_details['creator_name']
            creator_id = challenge_details['creator_id']
            logger.info(f"Gathering creator OSINT for: {creator_name} (ID: {creator_id})")

            # Use the OSINT helper to get creator's other content by ID
            creator_info = await self.osint_helper.gather_maker_info(creator_id)

            if creator_info:
                # Use the same format as machine OSINT - post maker profile and content
                await self.osint_helper.post_maker_info(thread, creator_info)
                logger.info(f"Successfully posted creator OSINT for {creator_name}")
            else:
                logger.warning(f"No creator information found for {creator_name}")

        except Exception as e:
            import traceback
            logger.error(f"Error posting creator OSINT: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")