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
    echo "Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.cargo/bin:$PATH"
fi

# Install Python dependencies using uv
echo "Installing Python dependencies with uv..."
uv sync

# Create service user
echo "Creating service user..."
if ! id "$SERVICE_USER" &>/dev/null; then
    useradd --system --home-dir "$INSTALL_DIR" --shell /bin/false "$SERVICE_USER"
    echo "Created user: $SERVICE_USER"
else
    echo "User $SERVICE_USER already exists"
fi

# Create installation directory
echo "Creating installation directory..."
mkdir -p "$INSTALL_DIR"
mkdir -p "$INSTALL_DIR/data"
mkdir -p "$INSTALL_DIR/logs"

# Copy files
echo "Copying service files..."
cp -r src/ "$INSTALL_DIR/"
cp htb-discord "$INSTALL_DIR/"
cp config.yaml "$INSTALL_DIR/"

# Set permissions
echo "Setting permissions..."
chown -R "$SERVICE_USER:$SERVICE_USER" "$INSTALL_DIR"
chmod +x "$INSTALL_DIR/htb-discord"

# Install systemd service
echo "Installing systemd service..."
cp htb-discord.service /etc/systemd/system/
systemctl daemon-reload

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