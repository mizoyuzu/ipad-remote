#!/bin/bash
# Unified Bluetooth backend control for iPad Remote
# Covers setup, service switching, pairing/unpairing from RPi side, and status.
# Usage examples:
#   sudo bash bt_backend_ctl.sh setup
#   sudo bash bt_backend_ctl.sh service bt
#   sudo bash bt_backend_ctl.sh pair AA:BB:CC:DD:EE:FF
#   sudo bash bt_backend_ctl.sh unpair AA:BB:CC:DD:EE:FF
#   sudo bash bt_backend_ctl.sh status
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SERVICE_BT="ipad-remote-bt.service"
SERVICE_DEFAULT="ipad-remote.service"

need_root() {
    if [ "$(id -u)" -ne 0 ]; then
        echo "Error: must run as root (sudo bash bt_backend_ctl.sh ...)"
        exit 1
    fi
}

mac_re='^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$'

require_mac() {
    local mac="${1:-}"
    if [[ -z "$mac" || ! "$mac" =~ $mac_re ]]; then
        echo "Error: invalid MAC address: $mac"
        echo "Expected format: AA:BB:CC:DD:EE:FF"
        exit 1
    fi
}

ensure_bt_tools() {
    command -v bluetoothctl >/dev/null 2>&1 || {
        echo "Error: bluetoothctl not found. Run: sudo bash bt_backend_ctl.sh setup"
        exit 1
    }
}

cmd_setup() {
    need_root
    bash "$SCRIPT_DIR/bt_setup.sh"
}

cmd_service() {
    need_root
    local mode="${1:-}"
    case "$mode" in
        bt)
            systemctl disable --now "$SERVICE_DEFAULT" >/dev/null 2>&1 || true
            systemctl enable --now "$SERVICE_BT"
            echo "Active service: $SERVICE_BT"
            ;;
        default|usb|both)
            systemctl disable --now "$SERVICE_BT" >/dev/null 2>&1 || true
            systemctl enable --now "$SERVICE_DEFAULT"
            echo "Active service: $SERVICE_DEFAULT"
            ;;
        stop)
            systemctl disable --now "$SERVICE_BT" >/dev/null 2>&1 || true
            systemctl disable --now "$SERVICE_DEFAULT" >/dev/null 2>&1 || true
            echo "Stopped both iPad Remote services"
            ;;
        *)
            echo "Usage: $0 service {bt|default|usb|both|stop}"
            exit 1
            ;;
    esac
}

cmd_status() {
    ensure_bt_tools
    echo "=== bluetoothctl show ==="
    bluetoothctl show || true
    echo ""
    echo "=== paired devices ==="
    bluetoothctl paired-devices || true
    echo ""
    echo "=== service status ($SERVICE_BT) ==="
    systemctl --no-pager --full status "$SERVICE_BT" || true
    echo ""
    echo "=== service status ($SERVICE_DEFAULT) ==="
    systemctl --no-pager --full status "$SERVICE_DEFAULT" || true
}

cmd_logs() {
    local which="${1:-bt}"
    case "$which" in
        bt)
            journalctl -u "$SERVICE_BT" -f
            ;;
        default|usb|both)
            journalctl -u "$SERVICE_DEFAULT" -f
            ;;
        *)
            echo "Usage: $0 logs {bt|default}"
            exit 1
            ;;
    esac
}

cmd_scan() {
    ensure_bt_tools
    local seconds="${1:-10}"
    echo "Scanning for $seconds seconds..."
    bluetoothctl --timeout "$seconds" scan on || true
    echo ""
    echo "Discovered devices:"
    bluetoothctl devices || true
}

cmd_prepare_host() {
    ensure_bt_tools
    echo "Preparing Raspberry Pi as pairable/discoverable HID device..."
    bluetoothctl power on
    bluetoothctl pairable on
    bluetoothctl discoverable on
    bluetoothctl agent NoInputNoOutput
    bluetoothctl default-agent
    echo "RPi is ready for host pairing (Mac/PC)."
}

cmd_pair() {
    ensure_bt_tools
    local mac="${1:-}"
    require_mac "$mac"
    echo "Pairing with $mac ..."
    bluetoothctl pair "$mac"
    bluetoothctl trust "$mac"
    bluetoothctl connect "$mac" || true
    echo "Pairing flow completed for $mac"
}

cmd_pair_host() {
    ensure_bt_tools
    local mac="${1:-}"
    require_mac "$mac"
    cmd_prepare_host
    echo "Pairing host device from Raspberry Pi side: $mac"
    bluetoothctl pair "$mac"
    bluetoothctl trust "$mac"
    bluetoothctl connect "$mac" || true
    bluetoothctl info "$mac" || true
    echo "Host pairing flow completed for $mac"
}

cmd_unpair() {
    ensure_bt_tools
    local mac="${1:-}"
    require_mac "$mac"
    echo "Removing $mac ..."
    bluetoothctl remove "$mac"
    echo "Removed $mac"
}

cmd_trust() {
    ensure_bt_tools
    local mac="${1:-}"
    require_mac "$mac"
    bluetoothctl trust "$mac"
}

cmd_untrust() {
    ensure_bt_tools
    local mac="${1:-}"
    require_mac "$mac"
    bluetoothctl untrust "$mac"
}

cmd_connect() {
    ensure_bt_tools
    local mac="${1:-}"
    require_mac "$mac"
    bluetoothctl connect "$mac"
}

cmd_disconnect() {
    ensure_bt_tools
    local mac="${1:-}"
    require_mac "$mac"
    bluetoothctl disconnect "$mac"
}

cmd_info() {
    ensure_bt_tools
    local mac="${1:-}"
    require_mac "$mac"
    bluetoothctl info "$mac"
}

cmd_discoverable() {
    ensure_bt_tools
    local onoff="${1:-}"
    case "$onoff" in
        on|off)
            bluetoothctl discoverable "$onoff"
            ;;
        *)
            echo "Usage: $0 discoverable {on|off}"
            exit 1
            ;;
    esac
}

cmd_pairable() {
    ensure_bt_tools
    local onoff="${1:-}"
    case "$onoff" in
        on|off)
            bluetoothctl pairable "$onoff"
            ;;
        *)
            echo "Usage: $0 pairable {on|off}"
            exit 1
            ;;
    esac
}

cmd_power() {
    ensure_bt_tools
    local onoff="${1:-}"
    case "$onoff" in
        on|off)
            bluetoothctl power "$onoff"
            ;;
        *)
            echo "Usage: $0 power {on|off}"
            exit 1
            ;;
    esac
}

usage() {
    cat <<EOF
Unified BT backend controller for iPad Remote

Usage:
  sudo bash $0 setup
  sudo bash $0 service {bt|default|usb|both|stop}
  sudo bash $0 status
  sudo bash $0 logs {bt|default}
  sudo bash $0 scan [seconds]
    sudo bash $0 prepare-host

    sudo bash $0 pair-host AA:BB:CC:DD:EE:FF
    sudo bash $0 pair AA:BB:CC:DD:EE:FF   (alias)
  sudo bash $0 unpair AA:BB:CC:DD:EE:FF
  sudo bash $0 trust AA:BB:CC:DD:EE:FF
  sudo bash $0 untrust AA:BB:CC:DD:EE:FF
  sudo bash $0 connect AA:BB:CC:DD:EE:FF
  sudo bash $0 disconnect AA:BB:CC:DD:EE:FF
  sudo bash $0 info AA:BB:CC:DD:EE:FF

  sudo bash $0 discoverable {on|off}
  sudo bash $0 pairable {on|off}
  sudo bash $0 power {on|off}
EOF
}

main() {
    local cmd="${1:-help}"
    shift || true
    case "$cmd" in
        setup) cmd_setup "$@" ;;
        service) cmd_service "$@" ;;
        status) cmd_status "$@" ;;
        logs) cmd_logs "$@" ;;
        scan) cmd_scan "$@" ;;
        prepare-host) cmd_prepare_host "$@" ;;
        pair-host) cmd_pair_host "$@" ;;
        pair) cmd_pair_host "$@" ;;
        unpair|remove) cmd_unpair "$@" ;;
        trust) cmd_trust "$@" ;;
        untrust) cmd_untrust "$@" ;;
        connect) cmd_connect "$@" ;;
        disconnect) cmd_disconnect "$@" ;;
        info) cmd_info "$@" ;;
        discoverable) cmd_discoverable "$@" ;;
        pairable) cmd_pairable "$@" ;;
        power) cmd_power "$@" ;;
        help|-h|--help) usage ;;
        *)
            echo "Unknown command: $cmd"
            usage
            exit 1
            ;;
    esac
}

main "$@"
