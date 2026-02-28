#!/bin/bash
# Master installer for iPad Remote on Raspberry Pi Zero 2W
# Must be run as root: sudo bash install.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
INSTALL_DIR="/opt/ipad-remote"

echo "=== iPad Remote Installer ==="

# Check root
if [ "$(id -u)" -ne 0 ]; then
    echo "Error: must run as root (sudo bash install.sh)"
    exit 1
fi

NEEDS_REBOOT=""

# 1. Ensure dwc2 overlay is enabled
BOOT_CONFIG="/boot/config.txt"
[ -f "/boot/firmware/config.txt" ] && BOOT_CONFIG="/boot/firmware/config.txt"

if ! grep -q "^dtoverlay=dwc2" "$BOOT_CONFIG" 2>/dev/null; then
    echo "dtoverlay=dwc2" >> "$BOOT_CONFIG"
    echo "Added dwc2 overlay to $BOOT_CONFIG"
    NEEDS_REBOOT=1
fi

# 2. Ensure dwc2 + libcomposite modules are loaded at boot
grep -qxF 'dwc2' /etc/modules || echo 'dwc2' >> /etc/modules
grep -qxF 'libcomposite' /etc/modules || echo 'libcomposite' >> /etc/modules

# 3. Install avahi if not present
if ! command -v avahi-daemon &>/dev/null; then
    apt-get update -qq
    apt-get install -y -qq avahi-daemon
fi

# 4. Copy project files
echo "Installing to $INSTALL_DIR ..."
mkdir -p "$INSTALL_DIR"
cp -r "$SCRIPT_DIR/../" "$INSTALL_DIR/rpi/"
chmod +x "$INSTALL_DIR/rpi/setup/"*.sh

# 5. Install avahi service
cp "$SCRIPT_DIR/avahi/ipad-remote.service" /etc/avahi/services/
systemctl restart avahi-daemon

# 6. Install systemd service
cp "$SCRIPT_DIR/ipad-remote.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable ipad-remote.service

# 7. Start service (if gadget can be set up)
if [ -z "$NEEDS_REBOOT" ]; then
    systemctl start ipad-remote.service
    echo ""
    echo "Service started. Check status:"
    echo "  sudo systemctl status ipad-remote"
    echo "  sudo journalctl -u ipad-remote -f"
else
    echo ""
    echo "*** REBOOT REQUIRED ***"
    echo "dwc2 overlay was added to $BOOT_CONFIG."
    echo "Run: sudo reboot"
    echo "After reboot, the service will start automatically."
fi

echo ""
echo "=== Installation complete ==="
