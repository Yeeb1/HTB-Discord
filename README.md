# HackTheBot

<p align="center">
    <img src="https://github.com/user-attachments/assets/17106da1-f82d-4d01-b263-5dc094abb130" width="400">
</p>

HackTheBot is a Discord bot that sends Hack The Box updates and information towards your Discord server.
It can automatically post newly released machines and challenges, forward platform notices, collect basic OSINT details, and optionally archive links.
All features are configured in a single YAML file and can be turned on or off as needed

> Heads Up: These scripts make heavy use of Discord’s community server features (forum threads). If you don’t want Discord sniffing through your messages (like more than anyways), temporarily enable the community server mode, create a few forums, and then disable it afterward.



## Features

- **Machine Monitoring**: Automatically posts upcoming HTB machines with Discord events and forum threads
<p align="center">
<img width="379" height="502" alt="image" src="https://github.com/user-attachments/assets/fc6621ea-0e5d-4a2f-a2df-1c7e8644053a" />
</p>

- **Challenge Tracking**: Also monitors for new HTB challenges
<p align="center">
<img width="379" height="159" alt="image" src="https://github.com/user-attachments/assets/d34b6a8b-a157-4613-a2c6-95072163e2ac" />
</p>

- **Platform Notices**: Forwards HTB platform warnings and notices to Discord
<p align="center">
<img width="568" height="144" alt="image" src="https://github.com/user-attachments/assets/e96af6a2-7331-427b-a53e-9ed5615b5624" />
</p>

- **OSINT**: Automatic intelligence gathering for machines and challenges including creator profiles, historical content, and statistics
<p align="center">
<img width="508" height="709" alt="image" src="https://github.com/user-attachments/assets/3e908300-097c-4004-ac19-630dfdca1b4d" />
</p>

- **Link Archival**: Optional Linkwarden integration for automatic link collection
- **Unified Configuration**: Single YAML config file with feature toggles

## Requirements

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) package manager
- Discord bot with appropriate permissions
- HTB API token
- Discord server with community features enabled

## Quick Start

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

### 3. Generate and customize config
```bash
uv run htb-discord generate-config
cp config.sample.yaml config.yaml
# Edit config.yaml to match your setup
```

### 4. Run the service
```bash
uv run htb-discord
```

## Documentation

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
    enabled: false  # Legcay and Disabled - OSINT now runs automatically with new machine and challenge posts
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
- **Community features enabled** (for forum channels, can be disabled after forum creation)
- **Forum channels** with appropriate tags:
  - Machine forum: OS tags (linux, windows, etc) + difficulty tags
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

## Architecture

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

## Development

### Setup Development Environment
```bash
uv sync --group dev          # Install dev dependencies
make lint                    # Check code quality
make format                  # Format code
make typecheck              # Run type checking
```

