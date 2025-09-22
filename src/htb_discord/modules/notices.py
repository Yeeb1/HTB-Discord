"""Notice monitoring module."""

import asyncio
import logging
import requests
from typing import Dict, Any, List

import discord

from ..utils.discord_helpers import DiscordHelpers

logger = logging.getLogger(__name__)

class NoticeMonitor:
    """Monitors HTB notices and posts them to Discord."""

    def __init__(self, config, db_manager, client):
        self.config = config
        self.db_manager = db_manager
        self.client = client
        self.running = False

        # HTB API configuration
        self.api_url = "https://labs.hackthebox.com/api/v4/notices"
        self.headers = {
            "Authorization": f"Bearer {config.get('api.htb_bearer_token')}",
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36 Edg/117.0.2045.55"
        }

        # Configuration
        self.poll_interval = config.get_poll_interval('notices')
        self.error_channel_id = config.get_channel_id('error_channel_id')

    async def start(self) -> None:
        """Start the notice monitoring loop."""
        self.running = True
        logger.info("Starting notice monitor")

        await self.client.wait_until_ready()

        while self.running:
            try:
                await self.check_new_notices()
                await asyncio.sleep(self.poll_interval)
            except Exception as e:
                logger.error(f"Error in notice monitoring loop: {e}")
                await asyncio.sleep(60)  # Wait a minute before retrying

    async def stop(self) -> None:
        """Stop the notice monitoring loop."""
        self.running = False
        logger.info("Stopping notice monitor")

    async def fetch_notices(self) -> List[Dict[str, Any]]:
        """Fetch notices from HTB API."""
        try:
            response = requests.get(self.api_url, headers=self.headers)
            if response.status_code == 200:
                return response.json().get("data", [])
            else:
                logger.error(f"Failed to fetch notices. Status code: {response.status_code}")
        except Exception as e:
            logger.error(f"Error fetching notices: {e}")

        return []

    async def check_new_notices(self) -> None:
        """Check for new notices and process them."""
        notices = await self.fetch_notices()

        for notice in notices:
            notice_id = notice.get("id")
            if notice_id and not self.db_manager.notice_exists(notice_id):
                logger.info(f"Found new notice: {notice_id}")
                await self.process_new_notice(notice)
                self.db_manager.add_notice(notice_id)

    async def process_new_notice(self, notice: Dict[str, Any]) -> None:
        """Process a new notice by sending it to Discord."""
        await self.send_notice_to_channel(notice)

    async def send_notice_to_channel(self, notice: Dict[str, Any]) -> None:
        """Send notice to the configured error channel."""
        if not self.error_channel_id:
            logger.warning("Error channel ID not configured")
            return

        channel = await DiscordHelpers.resolve_channel(self.client, self.error_channel_id)
        if not channel:
            logger.error(f"Could not resolve error channel: {self.error_channel_id}")
            return

        # Check permissions
        me = channel.guild.me or await channel.guild.fetch_member(self.client.user.id)
        if not await DiscordHelpers.check_permissions(channel, me, ['send_messages', 'embed_links']):
            logger.error(f"Missing permissions for error channel: {channel.name}")
            return

        # Create and send embed
        embed = DiscordHelpers.create_notice_embed(notice)
        await channel.send(embed=embed)

        logger.info(f"Sent notice to channel: {notice.get('id')}")