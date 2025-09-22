"""Discord helper utilities."""

import discord
import aiohttp
import asyncio
import logging
from typing import Optional, Dict, Any
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)

class DiscordHelpers:
    """Helper class for Discord operations."""

    @staticmethod
    def get_embed_color(difficulty: str) -> discord.Color:
        """Get embed color based on difficulty."""
        difficulty_colors = {
            "easy": discord.Color.green(),
            "medium": discord.Color.orange(),
            "hard": discord.Color.red(),
            "insane": discord.Color.from_rgb(0, 0, 0),
        }
        return difficulty_colors.get(difficulty.lower(), discord.Color.blue())

    @staticmethod
    async def download_image(url: str, for_event: bool = False) -> Optional[bytes]:
        """Download image from URL with proper error handling."""
        if not url:
            logger.warning("Empty URL provided for image download")
            return None

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as response:
                    if response.status == 200:
                        data = await response.read()

                        if not data:
                            logger.warning(f"Empty image data from {url}")
                            return None

                        # Basic size validation
                        if len(data) < 100:
                            logger.warning(f"Image data too small from {url} ({len(data)} bytes)")
                            return None

                        logger.debug(f"Downloaded image from {url}: {len(data)} bytes")
                        return data
                    else:
                        logger.warning(f"Failed to download image: {url} (status: {response.status})")
                        return None
        except asyncio.TimeoutError:
            logger.error(f"Timeout downloading image from {url}")
            return None
        except Exception as e:
            logger.error(f"Error downloading image {url}: {e}")
            return None

    @staticmethod
    async def resolve_channel(client: discord.Client, channel_id: int) -> Optional[discord.abc.GuildChannel]:
        """Resolve channel by ID with fallback to API."""
        try:
            # Try cache first
            channel = client.get_channel(channel_id)
            if channel is not None:
                return channel

            # Fallback to API
            try:
                channel = await client.fetch_channel(channel_id)
                return channel
            except discord.NotFound:
                logger.error(f"Channel {channel_id} not found")
                return None
            except discord.Forbidden:
                logger.error(f"Bot lacks permission to view channel {channel_id}")
                return None

        except Exception as e:
            logger.error(f"Error resolving channel {channel_id}: {e}")
            return None

    @staticmethod
    def format_discord_timestamp(iso_date: str, offset_hours: int = 0) -> str:
        """Format ISO date string to Discord timestamp."""
        try:
            release_date = datetime.fromisoformat(iso_date.replace("Z", "+00:00")).astimezone(timezone.utc)
            if offset_hours:
                release_date = release_date + timedelta(hours=offset_hours)
            return f"<t:{int(release_date.timestamp())}:F>"
        except Exception as e:
            logger.error(f"Error formatting timestamp {iso_date}: {e}")
            return iso_date

    @staticmethod
    async def check_permissions(channel: discord.abc.GuildChannel, member: discord.Member,
                              required_perms: list) -> bool:
        """Check if member has required permissions in channel."""
        try:
            if hasattr(channel, 'permissions_for'):
                perms = channel.permissions_for(member)
            else:
                perms = member.guild_permissions

            for perm in required_perms:
                if not getattr(perms, perm, False):
                    logger.warning(f"Missing permission '{perm}' in channel {channel.name}")
                    return False
            return True

        except Exception as e:
            logger.error(f"Error checking permissions: {e}")
            return False

    @staticmethod
    def create_machine_embed(machine: Dict[str, Any]) -> discord.Embed:
        """Create Discord embed for machine."""
        creator = machine['firstCreator'][0]['name'] if machine.get('firstCreator') else 'Unknown'

        embed_color = DiscordHelpers.get_embed_color(machine['difficulty_text'])
        embed = discord.Embed(
            title=f"Machine: **{machine['name']}**",
            description=f"Release Date: {DiscordHelpers.format_discord_timestamp(machine['release'])}",
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

        if machine.get('avatar'):
            embed.set_thumbnail(url=f"https://labs.hackthebox.com{machine['avatar']}")

        return embed

    @staticmethod
    def create_challenge_embed(challenge: Dict[str, Any]) -> discord.Embed:
        """Create Discord embed for challenge."""
        embed_color = DiscordHelpers.get_embed_color(challenge['difficulty'])
        embed = discord.Embed(
            title=f"Challenge: **{challenge['name']}**",
            description=f"Release Date: {DiscordHelpers.format_discord_timestamp(challenge['release_date'])}",
            color=embed_color
        )
        embed.add_field(name="Difficulty", value=challenge['difficulty'], inline=True)
        embed.add_field(name="Category", value=challenge['category_name'], inline=True)

        return embed

    @staticmethod
    def create_notice_embed(notice: Dict[str, Any]) -> discord.Embed:
        """Create Discord embed for HTB notice."""
        machine_url = notice.get("url")
        machine_name = machine_url.split("/")[-1] if machine_url else "N/A"
        message = notice.get("message", "No message provided")
        notice_type = notice.get("type", "info")

        # Get appropriate color and emoji
        type_config = {
            "error": (discord.Color.red(), "❌"),
            "warning": (discord.Color.orange(), "⚠️"),
            "success": (discord.Color.green(), "✅"),
        }
        color, emoji = type_config.get(notice_type, (discord.Color.blue(), "ℹ️"))

        embed = discord.Embed(
            title=f"{emoji} {notice_type.capitalize()} Notice for {machine_name}",
            description=message,
            color=color
        )

        return embed

    @staticmethod
    async def create_forum_thread(forum_channel: discord.ForumChannel, name: str, content: str,
                                 tags: list, file: Optional[discord.File] = None) -> Optional[discord.Thread]:
        """Create a forum thread with tags."""
        try:
            # Map tag names to tag objects
            available_tags = {tag.name.lower(): tag for tag in forum_channel.available_tags}
            applied_tags = []

            for tag_name in tags:
                if tag_name:  # Check for non-empty tag names
                    tag = available_tags.get(tag_name.lower())
                    if tag:
                        applied_tags.append(tag)
                    else:
                        logger.warning(f"Tag '{tag_name}' not found in forum {forum_channel.name}")

            if not applied_tags:
                logger.error(f"No valid tags found for forum thread in {forum_channel.name}")
                return None

            # Create thread - only include file if we have valid data
            thread_kwargs = {
                "name": name,
                "content": content,
                "applied_tags": applied_tags,
                "auto_archive_duration": 1440
            }

            if file:
                thread_kwargs["file"] = file

            thread_with_message = await forum_channel.create_thread(**thread_kwargs)

            logger.info(f"Created forum thread: {name} in {forum_channel.name}")
            return thread_with_message.thread

        except Exception as e:
            logger.error(f"Failed to create forum thread '{name}': {e}")
            return None

    @staticmethod
    async def create_scheduled_event(guild: discord.Guild, name: str, description: str,
                                   start_time: datetime, end_time: datetime,
                                   voice_channel: discord.VoiceChannel,
                                   image_data: Optional[bytes] = None) -> bool:
        """Create a Discord scheduled event."""
        try:
            # Check if guild and voice_channel are valid
            if not guild or not voice_channel:
                logger.error("Invalid guild or voice channel for event creation")
                return False

            # Check permissions - get bot member from guild
            me = guild.me
            if not me:
                logger.error(f"Bot is not a member of guild {guild.name}")
                return False

            if not me.guild_permissions.manage_events:
                logger.error(f"Bot lacks 'Manage Events' permission in {guild.name}")
                return False

            channel_perms = voice_channel.permissions_for(me)
            if not (channel_perms.view_channel and channel_perms.connect):
                logger.error(f"Bot lacks voice channel permissions in {voice_channel.name}")
                return False

            # Ensure description is not too long (Discord limit is 1000 characters)
            if description and len(description) > 1000:
                description = description[:997] + "..."

            # Create event - only include image if we have valid data
            event_kwargs = {
                "name": name,
                "description": description,
                "start_time": start_time,
                "end_time": end_time,
                "channel": voice_channel,
                "entity_type": discord.EntityType.voice,
                "privacy_level": discord.PrivacyLevel.guild_only,
            }

            if image_data:
                event_kwargs["image"] = image_data

            await guild.create_scheduled_event(**event_kwargs)

            logger.info(f"Created Discord event: {name}")
            return True

        except Exception as e:
            import traceback
            logger.error(f"Failed to create Discord event '{name}': {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return False