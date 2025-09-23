#!/bin/bash
set -e

# HTB Discord Service Installation Script

INSTALL_DIR="/opt/htb-discord"
SERVICE_USER="htb-discord"
SERVICE_NAME="htb-discord"

echo "Installing HTB Discord Service..."

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   echo "This script must be run as root (use sudo)"
   exit 1
fi

# Install uv if not present
echo "Checking for uv..."
if ! command -v uv &> /dev/null; then
    echo "Installing uv system-wide..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.cargo/bin:$PATH"
fi

# Install Python dependencies using uv
echo "Installing Python dependencies with uv..."
uv sync

# Create installation directory first
echo "Creating installation directory..."
mkdir -p "$INSTALL_DIR"
mkdir -p "$INSTALL_DIR/data"
mkdir -p "$INSTALL_DIR/logs"
mkdir -p "$INSTALL_DIR/.cache"
mkdir -p "$INSTALL_DIR/.local/bin"

# Create service user with proper home directory
echo "Creating service user..."
if id "$SERVICE_USER" &>/dev/null; then
    echo "Removing existing user $SERVICE_USER to recreate with correct home directory..."
    userdel -r "$SERVICE_USER" 2>/dev/null || true
fi
useradd --system --home-dir "/home/$SERVICE_USER" --create-home --shell /bin/false "$SERVICE_USER"
echo "Created user: $SERVICE_USER"

# Recreate installation directories after user deletion
echo "Recreating installation directories..."
mkdir -p "$INSTALL_DIR"
mkdir -p "$INSTALL_DIR/data"
mkdir -p "$INSTALL_DIR/logs"
mkdir -p "$INSTALL_DIR/.cache"
mkdir -p "$INSTALL_DIR/.local/bin"

# Set initial permissions
chown -R "$SERVICE_USER:$SERVICE_USER" "$INSTALL_DIR"

# Copy files
echo "Copying service files..."
cp -r src/ "$INSTALL_DIR/"
cp pyproject.toml "$INSTALL_DIR/"
cp uv.lock "$INSTALL_DIR/"
cp README.md "$INSTALL_DIR/"
if [ -f config.yaml ]; then
    cp config.yaml "$INSTALL_DIR/"
fi

# Install uv for the service user in the working directory
echo "Installing uv for service user..."
sudo -u "$SERVICE_USER" bash -c "export HOME=$INSTALL_DIR && curl -LsSf https://astral.sh/uv/install.sh | sh"

# Install project dependencies using system uv
echo "Installing project dependencies..."
ORIGINAL_DIR=$(pwd)
cd "$INSTALL_DIR"
uv sync --frozen
cd "$ORIGINAL_DIR"

# Set permissions
echo "Setting permissions..."
chown -R "$SERVICE_USER:$SERVICE_USER" "$INSTALL_DIR"

# Ensure .cache directory exists and has correct permissions
mkdir -p "$INSTALL_DIR/.cache"
chown -R "$SERVICE_USER:$SERVICE_USER" "$INSTALL_DIR/.cache"

# Install systemd service
echo "Installing systemd service..."
cp htb-discord.service /etc/systemd/system/

# Stop the service if it's running
echo "Stopping any running service..."
systemctl stop "$SERVICE_NAME" 2>/dev/null || true

# Clean up any existing override files with syntax errors
if [ -d "/etc/systemd/system/htb-discord.service.d" ]; then
    echo "Cleaning up existing override configuration..."
    rm -rf /etc/systemd/system/htb-discord.service.d
fi

# Reload systemd and reset failed state
systemctl daemon-reload
systemctl reset-failed "$SERVICE_NAME" 2>/dev/null || true

# Enable service (but don't start it yet)
systemctl enable "$SERVICE_NAME"

echo ""
echo "Installation complete!"
echo ""
echo "Next steps:"
echo "1. Edit the configuration file: $INSTALL_DIR/config.yaml"
echo "2. Set up your environment variables or update the config file"
echo "3. Start the service: sudo systemctl start $SERVICE_NAME"
echo "4. Check service status: sudo systemctl status $SERVICE_NAME"
echo "5. View logs: sudo journalctl -u $SERVICE_NAME -f"
echo ""
echo "Service files installed to: $INSTALL_DIR"
echo "Service user created: $SERVICE_USER"
echo "Systemd service: $SERVICE_NAME"
