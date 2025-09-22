# HTB-Discord

<p align="center">
    <img src="https://github.com/user-attachments/assets/17106da1-f82d-4d01-b263-5dc094abb130" width="400">
</p>

A sophisticated Discord service that integrates HackTheBox platform data into Discord servers. This unified service replaces the original collection of separate bot scripts with a modern, configurable, and maintainable architecture.

## 🚀 Features

- **Machine Monitoring**: Automatically posts unreleased HTB machines with Discord events and forum threads
- **Challenge Tracking**: Monitors new HTB challenges with comprehensive intelligence including ratings, difficulty, solve counts, and first blood information
- **Platform Notices**: Forwards HTB platform warnings and notices to Discord
- **Enhanced OSINT**: Automatic intelligence gathering for machines and challenges including creator profiles, historical content, and detailed statistics
- **Link Archival**: Optional Linkwarden integration for automatic link collection
- **Unified Configuration**: Single YAML config file with feature toggles
- **Service Management**: Production-ready with systemd integration
- **Modern Tooling**: Built with uv, type hints, and comprehensive error handling

## 📋 Requirements

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) package manager
- Discord bot with appropriate permissions
- HTB API token
- Discord server with community features enabled

## 🛠️ Quick Start

### 1. Install uv (if not already installed)
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 2. Clone and setup
```bash
git clone https://github.com/Yeeb1/HTB-Discord.git
cd HTB-Discord
uv sync
```

### 3. Configure environment variables
```bash
export DISCORD_TOKEN="your_discord_bot_token"
export HTB_BEARER_TOKEN="your_htb_api_token"
export GENERAL_CHANNEL_ID="123456789"
export MACHINES_CHANNEL_ID="123456789"
# ... add other required channel IDs
```

### 4. Generate and customize config
```bash
uv run htb-discord generate-config
cp config.sample.yaml config.yaml
# Edit config.yaml to match your setup
```

### 5. Run the service
```bash
uv run htb-discord
```

## 📖 Documentation

### Configuration

The service uses a single `config.yaml` file for all settings:

```yaml
features:
  machines:
    enabled: true
    create_events: true        # Discord scheduled events
    create_forum_threads: true # Forum posts
    send_announcements: true   # Channel messages
    poll_interval: 600        # Check every 10 minutes

  challenges:
    enabled: true
    # Similar options...

  notices:
    enabled: true
    poll_interval: 60         # Check every minute

  osint:
    enabled: false  # Disabled - OSINT now runs automatically with machine and challenge posts
    command_prefix: "!"

  linkwarden:
    enabled: false            # Optional feature
```

### Available Commands

```bash
# Service management
uv run htb-discord                    # Start service
uv run htb-discord validate           # Validate configuration
uv run htb-discord generate-config    # Generate sample config

# Development
make run                              # Start in development mode
make lint                             # Run code linting
make format                           # Format code
make test                             # Run tests
```

### Discord Setup

Your Discord server needs:
- **Community features enabled** (for forum channels)
- **Forum channels** with appropriate tags:
  - Machine forum: OS tags (linux, windows, freebsd) + difficulty tags
  - Challenge forum: Category tags (web, crypto, pwn, etc.) + difficulty tags
- **Voice channels** for scheduled events
- **Bot permissions**: Send Messages, Manage Threads, Manage Events, View Channels, Embed Links

### Production Deployment

```bash
# Install as system service
sudo ./install.sh

# Service management
sudo systemctl start htb-discord
sudo systemctl status htb-discord
sudo journalctl -u htb-discord -f
```

## 🏗️ Architecture

The service follows a modular architecture:

```
src/htb_discord/
├── service.py              # Main service manager
├── config.py               # Configuration management
├── cli.py                  # Command line interface
├── modules/                # Feature modules
│   ├── machines.py         # Machine monitoring
│   ├── challenges.py       # Challenge tracking
│   ├── notices.py          # Notice forwarding
│   ├── osint.py           # OSINT commands
│   └── linkwarden.py      # Link archival
└── utils/                  # Shared utilities
    ├── database.py         # SQLite management
    └── discord_helpers.py  # Discord utilities
```

Each module can be independently enabled/disabled and configured through the main config file.

## 🔧 Development

### Setup Development Environment
```bash
uv sync --group dev          # Install dev dependencies
make lint                    # Check code quality
make format                  # Format code
make typecheck              # Run type checking
```

### Adding New Features
1. Create a new module in `src/htb_discord/modules/`
2. Add configuration options to `config.yaml`
3. Register the module in `service.py`
4. Add appropriate tests

## 📝 Migration from Original Scripts

If you're migrating from the original individual bot scripts:

1. **Database Migration**: The new service uses the same SQLite database files, so existing state is preserved
2. **Configuration**: Convert your `.env` variables to the new `config.yaml` format
3. **Systemd Services**: Replace individual service files with the unified `htb-discord.service`

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes with proper type hints and documentation
4. Run tests and linting: `make test lint`
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🐛 Issues

Report bugs and feature requests on the [GitHub Issues](https://github.com/Yeeb1/HTB-Discord/issues) page.

---

**Note**: These scripts make heavy use of Discord's community server features (forum threads). If you don't want Discord analyzing your messages, temporarily enable community server mode, create the required forums, and then disable it afterward.