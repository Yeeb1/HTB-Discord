"""Main service manager for HTB Discord integration."""

import asyncio
import signal
import logging
import sys
from typing import Dict, List, Optional
from pathlib import Path

import discord
from discord.ext import commands

from .config import Config, ConfigError
from .utils.database import DatabaseManager
from .modules.machines import MachineMonitor
from .modules.challenges import ChallengeMonitor
from .modules.notices import NoticeMonitor
from .modules.osint import OSINTCommands
from .modules.linkwarden import LinkwardenForwarder

logger = logging.getLogger(__name__)

class HTBDiscordService:
    """Main service class that manages all HTB Discord integrations."""

    def __init__(self, config_path: str = "config.yaml"):
        self.config_path = config_path
        self.config: Optional[Config] = None
        self.db_manager: Optional[DatabaseManager] = None
        self.client: Optional[discord.Client] = None
        self.bot: Optional[commands.Bot] = None
        self.monitors: Dict[str, object] = {}
        self.tasks: List[asyncio.Task] = []
        self.shutdown_event = asyncio.Event()
        self.restart_count = 0
        self.max_restarts = 5

    async def start(self) -> None:
        """Start the service."""
        try:
            logger.info("Starting HTB Discord Service...")

            # Load configuration
            await self._load_config()

            # Setup logging
            await self._setup_logging()

            # Initialize database
            await self._initialize_database()

            # Setup Discord clients
            await self._setup_discord()

            # Initialize modules
            await self._initialize_modules()

            # Setup signal handlers
            self._setup_signal_handlers()

            logger.info("Service started successfully")

            # Run Discord clients
            await self._run_discord_clients()

        except Exception as e:
            logger.critical(f"Failed to start service: {e}")
            await self.stop()
            sys.exit(1)

    async def stop(self) -> None:
        """Stop the service gracefully."""
        logger.info("Stopping HTB Discord Service...")

        # Cancel all background tasks
        for task in self.tasks:
            if not task.cancelled():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        # Close Discord connections
        if self.client and not self.client.is_closed():
            await self.client.close()

        if self.bot and not self.bot.is_closed():
            await self.bot.close()

        # Set shutdown event
        self.shutdown_event.set()

        logger.info("Service stopped")

    async def restart(self) -> None:
        """Restart the service."""
        if self.restart_count >= self.max_restarts:
            logger.critical(f"Maximum restart attempts ({self.max_restarts}) reached")
            await self.stop()
            return

        self.restart_count += 1
        logger.info(f"Restarting service (attempt {self.restart_count})")

        await self.stop()
        await asyncio.sleep(self.config.get('service.restart_delay', 30))
        await self.start()

    async def _load_config(self) -> None:
        """Load and validate configuration."""
        try:
            self.config = Config(self.config_path)
            self.max_restarts = self.config.get('service.max_restarts', 5)
            logger.info("Configuration loaded successfully")
        except ConfigError as e:
            logger.critical(f"Configuration error: {e}")
            raise

    async def _setup_logging(self) -> None:
        """Setup logging configuration."""
        log_config = self.config.get('logging', {})

        # Configure root logger
        logging.basicConfig(
            level=getattr(logging, log_config.get('level', 'INFO')),
            format=log_config.get('format', '%(asctime)s - %(name)s - %(levelname)s - %(message)s'),
            handlers=[
                logging.StreamHandler(sys.stdout),
                logging.FileHandler(log_config.get('file', 'logs/htb_discord.log'))
            ]
        )

        # Set Discord library log level
        discord_logger = logging.getLogger('discord')
        discord_logger.setLevel(logging.WARNING)

        logger.info("Logging configured")

    async def _initialize_database(self) -> None:
        """Initialize database manager."""
        self.db_manager = DatabaseManager(self.config)
        logger.info("Database initialized")

    async def _setup_discord(self) -> None:
        """Setup Discord clients."""
        discord_config = self.config.get('discord', {})
        intents_config = discord_config.get('intents', {})

        # Setup intents
        intents = discord.Intents.default()
        intents.message_content = intents_config.get('message_content', True)
        intents.guilds = intents_config.get('guilds', True)
        intents.messages = intents_config.get('messages', True)

        # Create main client for monitors
        self.client = discord.Client(intents=intents)

        # Create bot for commands (if OSINT is enabled)
        if self.config.is_feature_enabled('osint'):
            prefix = self.config.get('features.osint.command_prefix', '!')
            self.bot = commands.Bot(command_prefix=prefix, intents=intents)

        # Setup activity
        activity_config = discord_config.get('activity', {})
        if activity_config:
            activity_type = getattr(discord.ActivityType, activity_config.get('type', 'watching'), discord.ActivityType.watching)
            activity_name = activity_config.get('name', 'HackTheBox')
            activity = discord.Activity(type=activity_type, name=activity_name)

            @self.client.event
            async def on_ready():
                await self.client.change_presence(activity=activity)
                logger.info(f"Discord client ready: {self.client.user}")

            if self.bot:
                @self.bot.event
                async def on_ready():
                    await self.bot.change_presence(activity=activity)
                    logger.info(f"Discord bot ready: {self.bot.user}")

        logger.info("Discord clients configured")

    async def _initialize_modules(self) -> None:
        """Initialize monitoring modules based on configuration."""
        token = self.config.get('api.discord_token')

        # Initialize machine monitor
        if self.config.is_feature_enabled('machines'):
            self.monitors['machines'] = MachineMonitor(self.config, self.db_manager, self.client)
            logger.info("Machine monitor initialized")

        # Initialize challenge monitor
        if self.config.is_feature_enabled('challenges'):
            self.monitors['challenges'] = ChallengeMonitor(self.config, self.db_manager, self.client)
            logger.info("Challenge monitor initialized")

        # Initialize notice monitor
        if self.config.is_feature_enabled('notices'):
            self.monitors['notices'] = NoticeMonitor(self.config, self.db_manager, self.client)
            logger.info("Notice monitor initialized")

        # Initialize OSINT commands
        if self.config.is_feature_enabled('osint') and self.bot:
            osint_cog = OSINTCommands(self.config)
            await self.bot.add_cog(osint_cog)
            logger.info("OSINT commands initialized")

        # Initialize Linkwarden forwarder
        if self.config.is_feature_enabled('linkwarden'):
            self.monitors['linkwarden'] = LinkwardenForwarder(self.config, self.db_manager, self.client)
            logger.info("Linkwarden forwarder initialized")

    def _setup_signal_handlers(self) -> None:
        """Setup signal handlers for graceful shutdown."""
        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}, initiating shutdown...")
            asyncio.create_task(self.stop())

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

    async def _run_discord_clients(self) -> None:
        """Run Discord clients and monitoring tasks."""
        tasks = []

        # Start main client
        if self.client:
            tasks.append(asyncio.create_task(
                self.client.start(self.config.get('api.discord_token'))
            ))

        # Start bot (if different from client)
        if self.bot and self.bot != self.client:
            tasks.append(asyncio.create_task(
                self.bot.start(self.config.get('api.discord_token'))
            ))

        # Start monitoring tasks
        for name, monitor in self.monitors.items():
            if hasattr(monitor, 'start'):
                task = asyncio.create_task(monitor.start())
                task.set_name(f"monitor_{name}")
                tasks.append(task)
                self.tasks.append(task)

        try:
            # Wait for shutdown signal or client failure
            done, pending = await asyncio.wait(
                tasks + [asyncio.create_task(self.shutdown_event.wait())],
                return_when=asyncio.FIRST_COMPLETED
            )

            # Cancel remaining tasks
            for task in pending:
                task.cancel()

            # Check if any tasks failed
            for task in done:
                if task.get_name() != 'shutdown_event' and not task.cancelled():
                    try:
                        await task
                    except Exception as e:
                        logger.error(f"Task {task.get_name()} failed: {e}")
                        if self.config.get('service.restart_on_failure', True):
                            await self.restart()
                            return

        except Exception as e:
            logger.critical(f"Critical error in main loop: {e}")
            if self.config.get('service.restart_on_failure', True):
                await self.restart()
            else:
                await self.stop()

async def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description='HTB Discord Service')
    parser.add_argument('--config', '-c', default='config.yaml',
                       help='Configuration file path (default: config.yaml)')
    parser.add_argument('--log-level', '-l', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                       help='Override log level')

    args = parser.parse_args()

    # Override log level if specified
    if args.log_level:
        logging.basicConfig(level=getattr(logging, args.log_level))

    # Create and start service
    service = HTBDiscordService(args.config)
    await service.start()

if __name__ == "__main__":
    asyncio.run(main())