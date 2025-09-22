"""Linkwarden integration module."""

import asyncio
import logging
import re
import json
import http.client
from typing import Dict, Any, List, Optional

import discord

logger = logging.getLogger(__name__)

class LinkwardenForwarder:
    """Monitors Discord channels and forwards links to Linkwarden."""

    def __init__(self, config, db_manager, client):
        self.config = config
        self.db_manager = db_manager
        self.client = client
        self.running = False

        # Linkwarden configuration
        self.api_url = config.get('api.linkwarden_api_url', '').replace('https://', '').replace('http://', '')
        self.token = config.get('api.linkwarden_token')
        self.categories_to_monitor = config.get('features.linkwarden.categories_to_monitor', [])

        # Rate limiting configuration
        rate_limit_config = config.get('features.linkwarden.rate_limit', {})
        self.links_per_batch = rate_limit_config.get('links_per_batch', 10)
        self.batch_interval = rate_limit_config.get('batch_interval', 6)

        # Collections cache
        self.collections_cache: Dict[str, Dict[str, Any]] = {}

        # Validate configuration
        if not self.api_url or not self.token:
            logger.error("Linkwarden API URL and token are required")
            self.running = False

        if not self.categories_to_monitor:
            logger.warning("No categories configured for monitoring")

    async def start(self) -> None:
        """Start the Linkwarden forwarder."""
        if not self.api_url or not self.token:
            logger.error("Cannot start Linkwarden forwarder: missing configuration")
            return

        self.running = True
        logger.info("Starting Linkwarden forwarder")

        await self.client.wait_until_ready()

        # Process existing messages when starting
        await self.process_existing_messages()

        # Set up message listener
        self.client.add_listener(self.on_message, 'on_message')

        # Start link processing loop
        asyncio.create_task(self.process_links_loop())

    async def stop(self) -> None:
        """Stop the Linkwarden forwarder."""
        self.running = False
        self.client.remove_listener(self.on_message, 'on_message')
        logger.info("Stopping Linkwarden forwarder")

    async def process_existing_messages(self) -> None:
        """Process existing messages in monitored channels."""
        logger.info("Processing existing messages for links...")

        for guild in self.client.guilds:
            for category in guild.categories:
                if str(category.id) in self.categories_to_monitor:
                    for channel in category.channels:
                        if isinstance(channel, discord.TextChannel):
                            logger.debug(f"Processing history for channel: {channel.name}")
                            await self.process_channel_history(channel)

        logger.info("Finished processing existing messages")

    async def process_channel_history(self, channel: discord.TextChannel) -> None:
        """Process message history of a channel."""
        try:
            async for message in channel.history(limit=None):
                self.extract_links_from_message(message)
        except Exception as e:
            logger.error(f"Error processing channel history {channel.name}: {e}")

    async def on_message(self, message: discord.Message) -> None:
        """Handle new messages."""
        if message.author == self.client.user:
            return

        # Check if message is in a monitored category
        if (hasattr(message.channel, 'category') and
            message.channel.category and
            str(message.channel.category.id) in self.categories_to_monitor):

            self.extract_links_from_message(message)

    def extract_links_from_message(self, message: discord.Message) -> None:
        """Extract links from a message and save them."""
        links = re.findall(r'(https?://\S+)', message.content)
        for link in links:
            self.db_manager.save_link(message.channel.name, link)

    async def process_links_loop(self) -> None:
        """Main loop for processing saved links."""
        while self.running:
            try:
                await self.process_pending_links()
                await asyncio.sleep(self.batch_interval)
            except Exception as e:
                logger.error(f"Error in link processing loop: {e}")
                await asyncio.sleep(60)

    async def process_pending_links(self) -> None:
        """Process pending links from database."""
        links = self.db_manager.get_unprocessed_links(self.links_per_batch)

        if not links:
            return

        logger.debug(f"Processing {len(links)} pending links")

        for link_id, channel_name, link in links:
            success = await self.send_link_to_linkwarden(channel_name, link)
            if success:
                self.db_manager.mark_link_processed(link_id)
                logger.debug(f"Successfully processed link: {link}")
            else:
                logger.warning(f"Failed to process link: {link}")

    async def send_link_to_linkwarden(self, channel_name: str, link: str) -> bool:
        """Send a link to Linkwarden."""
        try:
            # Ensure collection exists
            collection = await self.get_or_create_collection(channel_name)
            if not collection:
                logger.error(f"Failed to get/create collection for channel: {channel_name}")
                return False

            # Prepare payload
            payload = {
                "url": link,
                "type": "url",
                "tags": [{"name": channel_name}],
                "collection": {
                    "id": collection["id"],
                    "name": collection["name"]
                }
            }

            # Send to Linkwarden
            response_data = await self.make_linkwarden_request("POST", "/api/v1/links", payload)

            if response_data and "response" in response_data:
                logger.debug(f"Successfully sent link to Linkwarden: {link}")
                return True
            else:
                logger.error(f"Unexpected response from Linkwarden: {response_data}")
                return False

        except Exception as e:
            logger.error(f"Error sending link to Linkwarden: {e}")
            return False

    async def get_or_create_collection(self, collection_name: str) -> Optional[Dict[str, Any]]:
        """Get existing collection or create new one."""
        # Check cache first
        if collection_name in self.collections_cache:
            return self.collections_cache[collection_name]

        # Fetch collections from API
        collections = await self.fetch_collections()
        if collection_name in collections:
            self.collections_cache[collection_name] = collections[collection_name]
            return collections[collection_name]

        # Create new collection
        collection = await self.create_collection(collection_name)
        if collection:
            self.collections_cache[collection_name] = collection

        return collection

    async def fetch_collections(self) -> Dict[str, Dict[str, Any]]:
        """Fetch existing collections from Linkwarden."""
        try:
            response_data = await self.make_linkwarden_request("GET", "/api/v1/collections")

            if response_data and "response" in response_data and isinstance(response_data["response"], list):
                return {
                    collection["name"]: {
                        "id": collection["id"],
                        "name": collection["name"]
                    }
                    for collection in response_data["response"]
                }
            else:
                logger.error(f"Unexpected collections response: {response_data}")
                return {}

        except Exception as e:
            logger.error(f"Error fetching collections: {e}")
            return {}

    async def create_collection(self, collection_name: str) -> Optional[Dict[str, Any]]:
        """Create a new collection in Linkwarden."""
        try:
            payload = {
                "name": collection_name,
                "description": f"Links from {collection_name}",
                "color": "#000000"
            }

            response_data = await self.make_linkwarden_request("POST", "/api/v1/collections", payload)

            if response_data and "response" in response_data:
                new_collection = response_data["response"]
                logger.info(f"Created collection: {new_collection['name']}")
                return {
                    "id": new_collection["id"],
                    "name": new_collection["name"]
                }
            else:
                logger.error(f"Failed to create collection: {response_data}")
                return None

        except Exception as e:
            logger.error(f"Error creating collection: {e}")
            return None

    async def make_linkwarden_request(self, method: str, endpoint: str, payload: Optional[Dict] = None) -> Optional[Dict]:
        """Make HTTP request to Linkwarden API."""
        try:
            conn = http.client.HTTPSConnection(self.api_url)

            headers = {
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json"
            }

            body = json.dumps(payload) if payload else None

            conn.request(method, endpoint, body, headers)
            response = conn.getresponse()
            response_data = response.read().decode("utf-8")

            if response.status in {200, 201}:
                return json.loads(response_data)
            else:
                logger.error(f"Linkwarden API error {response.status}: {response_data}")
                return None

        except Exception as e:
            logger.error(f"Error making Linkwarden request: {e}")
            return None