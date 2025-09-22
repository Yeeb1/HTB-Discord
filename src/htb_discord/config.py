"""Configuration management for HTB Discord service."""

import os
import yaml
import logging
from typing import Dict, Any, Optional
from pathlib import Path
import re

logger = logging.getLogger(__name__)

class ConfigError(Exception):
    """Configuration validation error."""
    pass

class Config:
    """Configuration manager with validation and environment variable substitution."""

    def __init__(self, config_path: str = "config.yaml"):
        self.config_path = Path(config_path)
        self._config: Dict[str, Any] = {}
        self.load()
        self.validate()

    def load(self) -> None:
        """Load configuration from YAML file with environment variable substitution."""
        if not self.config_path.exists():
            raise ConfigError(f"Configuration file not found: {self.config_path}")

        try:
            with open(self.config_path, 'r') as f:
                raw_config = f.read()

            # Substitute environment variables
            substituted_config = self._substitute_env_vars(raw_config)
            self._config = yaml.safe_load(substituted_config)

            logger.info(f"Configuration loaded from {self.config_path}")

        except yaml.YAMLError as e:
            raise ConfigError(f"Invalid YAML in configuration file: {e}")
        except Exception as e:
            raise ConfigError(f"Failed to load configuration: {e}")

    def _substitute_env_vars(self, text: str) -> str:
        """Substitute environment variables in format ${VAR} or ${VAR:-default}."""
        def replace_var(match):
            var_expr = match.group(1)

            if ':-' in var_expr:
                var_name, default_value = var_expr.split(':-', 1)
                return os.getenv(var_name, default_value)
            else:
                value = os.getenv(var_expr)
                if value is None:
                    raise ConfigError(f"Required environment variable not set: {var_expr}")
                return value

        # Pattern matches ${VAR} or ${VAR:-default}
        pattern = r'\$\{([^}]+)\}'
        return re.sub(pattern, replace_var, text)

    def validate(self) -> None:
        """Validate configuration structure and required fields."""
        required_sections = ['api', 'channels', 'features', 'database', 'logging', 'service', 'discord']

        for section in required_sections:
            if section not in self._config:
                raise ConfigError(f"Missing required configuration section: {section}")

        # Validate API tokens
        api = self._config['api']
        if not api.get('discord_token'):
            raise ConfigError("Discord token is required")
        if not api.get('htb_bearer_token'):
            raise ConfigError("HTB bearer token is required")

        # Validate enabled features have required channels
        features = self._config['features']
        channels = self._config['channels']

        if features.get('machines', {}).get('enabled'):
            required_channels = ['machines_channel_id', 'machines_voice_channel_id', 'machines_forum_channel_id']
            for channel in required_channels:
                if not channels.get(channel):
                    raise ConfigError(f"Machine feature enabled but missing channel: {channel}")

        if features.get('challenges', {}).get('enabled'):
            required_channels = ['general_channel_id', 'challenges_voice_channel_id', 'challenges_forum_channel_id']
            for channel in required_channels:
                if not channels.get(channel):
                    raise ConfigError(f"Challenge feature enabled but missing channel: {channel}")

        if features.get('notices', {}).get('enabled'):
            if not channels.get('error_channel_id'):
                raise ConfigError("Notice feature enabled but missing error_channel_id")

        if features.get('linkwarden', {}).get('enabled'):
            linkwarden_api = api.get('linkwarden_api_url')
            linkwarden_token = api.get('linkwarden_token')
            if not linkwarden_api or not linkwarden_token:
                raise ConfigError("Linkwarden feature enabled but missing API URL or token")

        # Validate database paths
        self._ensure_database_dirs()

        # Validate logging
        self._ensure_log_dir()

        logger.info("Configuration validation passed")

    def _ensure_database_dirs(self) -> None:
        """Ensure database directories exist."""
        db_config = self._config['database']
        for db_name, db_path in db_config.items():
            if db_name.endswith('_db'):
                db_dir = Path(db_path).parent
                db_dir.mkdir(parents=True, exist_ok=True)

    def _ensure_log_dir(self) -> None:
        """Ensure log directory exists."""
        log_file = self._config['logging']['file']
        log_dir = Path(log_file).parent
        log_dir.mkdir(parents=True, exist_ok=True)

    def get(self, key_path: str, default: Any = None) -> Any:
        """Get configuration value using dot notation (e.g., 'api.discord_token')."""
        keys = key_path.split('.')
        value = self._config

        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default

        return value

    def is_feature_enabled(self, feature: str) -> bool:
        """Check if a feature is enabled."""
        return self.get(f'features.{feature}.enabled', False)

    def get_poll_interval(self, feature: str) -> int:
        """Get poll interval for a feature."""
        return self.get(f'features.{feature}.poll_interval', 600)

    def get_channel_id(self, channel_name: str) -> Optional[int]:
        """Get channel ID as integer."""
        channel_id = self.get(f'channels.{channel_name}')
        if channel_id:
            try:
                return int(channel_id)
            except (ValueError, TypeError):
                logger.error(f"Invalid channel ID for {channel_name}: {channel_id}")
                return None
        return None

    @property
    def config(self) -> Dict[str, Any]:
        """Get full configuration dictionary."""
        return self._config.copy()

    def reload(self) -> None:
        """Reload configuration from file."""
        logger.info("Reloading configuration...")
        self.load()
        self.validate()
        logger.info("Configuration reloaded successfully")