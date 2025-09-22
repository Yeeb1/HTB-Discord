"""Command line interface for HTB Discord service."""

import asyncio
import argparse
import logging
import sys
from pathlib import Path

from .service import HTBDiscordService


def setup_logging(level: str = "INFO") -> None:
    """Setup basic logging configuration."""
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)]
    )


def main() -> None:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="HTB Discord Integration Service",
        prog="htb-discord"
    )

    parser.add_argument(
        "--config", "-c",
        default="config.yaml",
        help="Configuration file path (default: config.yaml)"
    )

    parser.add_argument(
        "--log-level", "-l",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default="INFO",
        help="Set logging level (default: INFO)"
    )

    parser.add_argument(
        "--version", "-v",
        action="version",
        version="%(prog)s 2.0.0"
    )

    # Subcommands
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Start command (default)
    start_parser = subparsers.add_parser("start", help="Start the service")
    start_parser.add_argument(
        "--daemon", "-d",
        action="store_true",
        help="Run as daemon (detach from terminal)"
    )

    # Validate config command
    validate_parser = subparsers.add_parser("validate", help="Validate configuration")

    # Generate config command
    generate_parser = subparsers.add_parser("generate-config", help="Generate sample configuration")
    generate_parser.add_argument(
        "--output", "-o",
        default="config.sample.yaml",
        help="Output file for sample config (default: config.sample.yaml)"
    )

    args = parser.parse_args()

    # Setup logging
    setup_logging(args.log_level)

    # Handle commands
    if args.command == "validate":
        return validate_config(args.config)
    elif args.command == "generate-config":
        return generate_sample_config(args.output)
    else:
        # Default to start command
        return start_service(args.config, args.log_level)


def validate_config(config_path: str) -> None:
    """Validate configuration file."""
    try:
        from .config import Config

        config = Config(config_path)
        print(f"✅ Configuration file '{config_path}' is valid")

        # Print enabled features
        print("\nEnabled features:")
        for feature in ["machines", "challenges", "notices", "osint", "linkwarden"]:
            if config.is_feature_enabled(feature):
                print(f"  ✅ {feature}")
            else:
                print(f"  ❌ {feature}")

    except Exception as e:
        print(f"❌ Configuration validation failed: {e}")
        sys.exit(1)


def generate_sample_config(output_path: str) -> None:
    """Generate sample configuration file."""
    sample_config = '''# HTB Discord Bot Service Configuration
# All settings for the unified HTB Discord integration service

# Core API Configuration
api:
  discord_token: "${DISCORD_TOKEN}"
  htb_bearer_token: "${HTB_BEARER_TOKEN}"
  linkwarden_api_url: "${LINKWARDEN_API_URL:-}"
  linkwarden_token: "${LINKWARDEN_TOKEN:-}"

# Discord Channel Configuration
channels:
  # General announcement channel for challenges
  general_channel_id: "${GENERAL_CHANNEL_ID}"

  # Machine-specific channels
  machines_channel_id: "${MACHINES_CHANNEL_ID}"
  machines_voice_channel_id: "${MACHINES_VOICE_CHANNEL_ID}"
  machines_forum_channel_id: "${FORUM_CHANNEL_ID}"

  # Challenge-specific channels
  challenges_voice_channel_id: "${CHALL_VOICE_CHANNEL_ID}"
  challenges_forum_channel_id: "${CHALL_FORUM_CHANNEL_ID}"

  # Error/notice channel
  error_channel_id: "${ERROR_CHANNEL_ID}"

# Feature Configuration - Enable/Disable specific features
features:
  machines:
    enabled: true
    create_events: true
    create_forum_threads: true
    send_announcements: true
    poll_interval: 600  # seconds

  challenges:
    enabled: true
    create_events: true
    create_forum_threads: true
    send_announcements: true
    poll_interval: 600  # seconds

  notices:
    enabled: true
    poll_interval: 60  # seconds

  osint:
    enabled: true
    command_prefix: "!"

  linkwarden:
    enabled: false  # Disabled by default
    categories_to_monitor: []  # List of Discord category IDs
    rate_limit:
      links_per_batch: 10
      batch_interval: 6  # seconds

# Database Configuration
database:
  # SQLite database files
  machines_db: "data/machines.db"
  challenges_db: "data/challenges.db"
  notices_db: "data/notices.db"
  links_db: "data/links.db"

# Logging Configuration
logging:
  level: "INFO"  # DEBUG, INFO, WARNING, ERROR, CRITICAL
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
  file: "logs/htb_discord.log"
  max_file_size: "10MB"
  backup_count: 5

# Service Configuration
service:
  name: "htb-discord-service"
  description: "HackTheBox Discord Integration Service"
  restart_on_failure: true
  max_restarts: 5
  restart_delay: 30  # seconds

# Discord Bot Configuration
discord:
  intents:
    message_content: true
    guilds: true
    messages: true
  activity:
    type: "watching"  # playing, streaming, listening, watching
    name: "HackTheBox"
'''

    try:
        with open(output_path, 'w') as f:
            f.write(sample_config)
        print(f"✅ Sample configuration generated: {output_path}")
    except Exception as e:
        print(f"❌ Failed to generate sample config: {e}")
        sys.exit(1)


def start_service(config_path: str, log_level: str) -> None:
    """Start the HTB Discord service."""
    try:
        service = HTBDiscordService(config_path)
        asyncio.run(service.start())
    except KeyboardInterrupt:
        print("\n🛑 Service interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"❌ Service error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()