"""Machine monitoring module."""

import asyncio
import logging
import requests
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List

import discord

from ..utils.discord_helpers import DiscordHelpers
from .osint import OSINTHelper

logger = logging.getLogger(__name__)

class MachineMonitor:
    """Monitors HTB unreleased machines and posts to Discord."""

    def __init__(self, config, db_manager, client):
        self.config = config
        self.db_manager = db_manager
        self.client = client
        self.running = False

        # Initialize OSINT helper for automatic information gathering
        self.osint_helper = OSINTHelper(config)

        # HTB API configuration
        self.api_url = "https://labs.hackthebox.com/api/v4/machine/unreleased"
        self.headers = {
            "Authorization": f"Bearer {config.get('api.htb_bearer_token')}",
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36 Edg/117.0.2045.55"
        }

        # Feature flags
        self.create_events = config.get('features.machines.create_events', True)
        self.create_forum_threads = config.get('features.machines.create_forum_threads', True)
        self.send_announcements = config.get('features.machines.send_announcements', True)
        self.poll_interval = config.get_poll_interval('machines')

        # Channel IDs
        self.machines_channel_id = config.get_channel_id('machines_channel_id')
        self.machines_voice_channel_id = config.get_channel_id('machines_voice_channel_id')
        self.machines_forum_channel_id = config.get_channel_id('machines_forum_channel_id')

    async def start(self) -> None:
        """Start the machine monitoring loop."""
        self.running = True
        logger.info("Starting machine monitor")

        await self.client.wait_until_ready()

        while self.running:
            try:
                await self.check_new_machines()
                await asyncio.sleep(self.poll_interval)
            except Exception as e:
                logger.error(f"Error in machine monitoring loop: {e}")
                await asyncio.sleep(60)  # Wait a minute before retrying

    async def stop(self) -> None:
        """Stop the machine monitoring loop."""
        self.running = False
        logger.info("Stopping machine monitor")

    async def fetch_machines(self) -> List[Dict[str, Any]]:
        """Fetch unreleased machines from HTB API."""
        try:
            response = requests.get(self.api_url, headers=self.headers)
            if response.status_code == 200:
                return response.json().get("data", [])
            else:
                logger.error(f"Failed to fetch machines. Status code: {response.status_code}")
        except Exception as e:
            logger.error(f"Error fetching machines: {e}")

        return []

    async def check_new_machines(self) -> None:
        """Check for new machines and process them."""
        machines = await self.fetch_machines()

        for machine in machines:
            machine_id = machine['id']

            if not self.db_manager.machine_exists(machine_id):
                logger.info(f"Found new machine: {machine['name']}")
                await self.process_new_machine(machine)
                self.db_manager.add_machine(machine)

    async def process_new_machine(self, machine: Dict[str, Any]) -> None:
        """Process a new machine by sending announcements, creating events, etc."""
        # Send announcement
        if self.send_announcements:
            await self.send_machine_announcement(machine)

        # Create Discord event
        if self.create_events:
            await self.create_machine_event(machine)

        # Create forum thread
        if self.create_forum_threads:
            await self.create_machine_forum_thread(machine)

    async def send_machine_announcement(self, machine: Dict[str, Any]) -> None:
        """Send machine announcement to the configured channel."""
        if not self.machines_channel_id:
            logger.warning("Machines channel ID not configured")
            return

        channel = await DiscordHelpers.resolve_channel(self.client, self.machines_channel_id)
        if not channel:
            logger.error(f"Could not resolve machines channel: {self.machines_channel_id}")
            return

        # Skip if it's a forum channel (announcements go to regular channels)
        if isinstance(channel, discord.ForumChannel):
            logger.debug("Machines channel is a forum channel, skipping announcement")
            return

        # Check permissions
        me = channel.guild.me or await channel.guild.fetch_member(self.client.user.id)
        if not await DiscordHelpers.check_permissions(channel, me, ['send_messages', 'embed_links']):
            logger.error(f"Missing permissions for machines channel: {channel.name}")
            return

        # Download and prepare avatar file for announcement
        avatar_file = None
        if machine.get('avatar'):
            avatar_url = f"https://htb-mp-prod-public-storage.s3.eu-central-1.amazonaws.com{machine['avatar']}"
            image_data = await DiscordHelpers.download_image(avatar_url, for_event=True)

            if image_data:
                try:
                    import io
                    avatar_file = discord.File(
                        fp=io.BytesIO(image_data),
                        filename=f"{machine['name']}_logo.png"
                    )
                    logger.info(f"Created avatar file for announcement: {machine['name']} ({len(image_data)} bytes)")
                except Exception as e:
                    logger.warning(f"Failed to create avatar file for announcement {machine['name']}: {e}")
                    avatar_file = None

        # Create and send embed with logo
        embed = DiscordHelpers.create_machine_embed(machine)

        # If we have an avatar file, set the embed image to use the attachment
        if avatar_file:
            embed.set_image(url=f"attachment://{avatar_file.filename}")

        await channel.send(embed=embed, file=avatar_file)

        logger.info(f"Sent machine announcement: {machine['name']}")

    async def create_machine_event(self, machine: Dict[str, Any]) -> None:
        """Create a Discord scheduled event for the machine release."""
        if not self.machines_voice_channel_id:
            logger.warning("Machines voice channel ID not configured")
            return

        voice_channel = await DiscordHelpers.resolve_channel(self.client, self.machines_voice_channel_id)
        if not voice_channel or not isinstance(voice_channel, discord.VoiceChannel):
            logger.error(f"Invalid voice channel for events: {self.machines_voice_channel_id}")
            return

        # Prepare event data
        creator = machine['firstCreator'][0]['name'] if machine.get('firstCreator') else 'Unknown'
        event_name = f"{machine['name']}"
        machine_link = f"https://app.hackthebox.com/machines/{machine['name']}"
        event_description = f"{machine['os']} - {machine['difficulty_text']} - by {creator}\n\n{machine_link}"

        # Parse release time
        start_time = datetime.fromisoformat(machine['release'].replace("Z", "+00:00")).astimezone(timezone.utc)
        end_time = start_time + timedelta(hours=2)

        # Download machine image for event (preserve original data)
        image_data = None
        if machine.get('avatar'):
            avatar_url = f"https://htb-mp-prod-public-storage.s3.eu-central-1.amazonaws.com{machine['avatar']}"
            image_data = await DiscordHelpers.download_image(avatar_url, for_event=True)

        # Create event
        success = await DiscordHelpers.create_scheduled_event(
            guild=voice_channel.guild,
            name=event_name,
            description=event_description,
            start_time=start_time,
            end_time=end_time,
            voice_channel=voice_channel,
            image_data=image_data
        )

        if success:
            logger.info(f"Created Discord event for machine: {machine['name']}")

    async def create_machine_forum_thread(self, machine: Dict[str, Any]) -> None:
        """Create a forum thread for the machine."""
        if not self.machines_forum_channel_id:
            logger.warning("Machines forum channel ID not configured")
            return

        forum_channel = await DiscordHelpers.resolve_channel(self.client, self.machines_forum_channel_id)
        if not forum_channel or not isinstance(forum_channel, discord.ForumChannel):
            logger.error(f"Invalid forum channel: {self.machines_forum_channel_id}")
            return

        # Prepare thread data
        creator = machine['firstCreator'][0]['name'] if machine.get('firstCreator') else 'Unknown'
        thread_name = machine['name']
        machine_link = f"https://app.hackthebox.com/machines/{machine['name']}"

        thread_content = (
            f"**Machine Name:** {machine['name']}\n"
            f"**Operating System:** {machine['os']}\n"
            f"**Difficulty:** {machine['difficulty_text']}\n"
            f"**Creator:** {creator}\n\n"
            f"[View Machine on Hack The Box]({machine_link})"
        )

        # Prepare tags - ensure they are valid strings
        tags = []
        if machine.get('os'):
            tags.append(str(machine['os']).strip())
        if machine.get('difficulty_text'):
            tags.append(str(machine['difficulty_text']).strip())

        # Download and prepare avatar file for forum
        avatar_file = None
        if machine.get('avatar'):
            avatar_url = f"https://htb-mp-prod-public-storage.s3.eu-central-1.amazonaws.com{machine['avatar']}"
            # Use the same image data as events (unfiltered)
            image_data = await DiscordHelpers.download_image(avatar_url, for_event=True)

            if image_data:
                try:
                    import io
                    # Create the Discord file object
                    avatar_file = discord.File(
                        fp=io.BytesIO(image_data),
                        filename=f"{machine['name']}_avatar.png"
                    )
                    logger.info(f"Created avatar file for {machine['name']} ({len(image_data)} bytes)")
                except Exception as e:
                    logger.warning(f"Failed to create avatar file for {machine['name']}: {e}")
                    avatar_file = None

        # Create thread
        thread = await DiscordHelpers.create_forum_thread(
            forum_channel=forum_channel,
            name=thread_name,
            content=thread_content,
            tags=tags,
            file=avatar_file
        )

        if thread:
            logger.info(f"Created forum thread for machine: {machine['name']}")

            # Automatically post OSINT information to the thread
            await self.post_automatic_osint(thread, machine['name'])

    async def post_automatic_osint(self, thread: discord.Thread, machine_name: str) -> None:
        """Automatically post OSINT information to the forum thread."""
        try:
            logger.info(f"Gathering OSINT information for machine: {machine_name}")

            # Use the OSINT helper to post comprehensive machine information
            success = await self.osint_helper.post_osint_to_thread(thread, machine_name)

            if success:
                logger.info(f"Successfully posted automatic OSINT for {machine_name}")
            else:
                logger.warning(f"Failed to post automatic OSINT for {machine_name}")

        except Exception as e:
            logger.error(f"Error posting automatic OSINT for {machine_name}: {e}")