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

ensure_unit_installed() {
    local unit_name="$1"
    local src="$SCRIPT_DIR/$unit_name"
    local dst="/etc/systemd/system/$unit_name"

    if [ ! -f "$src" ]; then
        echo "Error: unit file not found in setup directory: $src"
        exit 1
    fi

    if [ ! -f "$dst" ]; then
        echo "Installing missing unit file: $unit_name"
        cp "$src" "$dst"
        systemctl daemon-reload
    fi
}

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

bt_try() {
    local label="$1"
    shift
    if "$@" >/dev/null 2>&1; then
        echo "[ok] $label"
        return 0
    fi
    echo "[warn] $label failed"
    return 1
}

bt_show() {
    bluetoothctl show 2>/dev/null || true
}

bt_is_powered() {
    bt_show | grep -q "Powered: yes"
}

bt_device_connected() {
    local mac="$1"
    bluetoothctl info "$mac" 2>/dev/null | grep -q "Connected: yes"
}

bt_device_paired() {
    local mac="$1"
    bluetoothctl info "$mac" 2>/dev/null | grep -q "Paired: yes"
}

bt_list_all_devices() {
    bluetoothctl devices 2>/dev/null | awk '/^Device /{print $2}'
}

bt_list_paired_devices() {
    local mac
    while read -r mac; do
        [ -z "$mac" ] && continue
        if bt_device_paired "$mac"; then
            local line
            line="$(bluetoothctl devices 2>/dev/null | grep "^Device $mac " || true)"
            if [ -n "$line" ]; then
                echo "$line"
            else
                echo "Device $mac"
            fi
        fi
    done < <(bt_list_all_devices)
}

hid_channel_connected_since() {
    local since_ts="$1"
    journalctl -u "$SERVICE_BT" --since "$since_ts" --no-pager 2>/dev/null \
        | grep -q "BT HID interrupt channel connected"
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
            ensure_unit_installed "$SERVICE_BT"
            systemctl disable --now "$SERVICE_DEFAULT" >/dev/null 2>&1 || true
            systemctl enable --now "$SERVICE_BT"
            echo "Active service: $SERVICE_BT"
            ;;
        default|usb|both)
            ensure_unit_installed "$SERVICE_DEFAULT"
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
    bt_list_paired_devices || true
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
    need_root
    ensure_bt_tools
    echo "Preparing Raspberry Pi as pairable/discoverable HID device..."

    # Try to recover adapter state before bluetoothctl operations.
    bt_try "restart bluetooth service" systemctl restart bluetooth || true
    if command -v rfkill >/dev/null 2>&1; then
        bt_try "rfkill unblock bluetooth" rfkill unblock bluetooth || true
    fi
    if command -v hciconfig >/dev/null 2>&1; then
        bt_try "hciconfig hci0 up" hciconfig hci0 up || true
    fi
    if command -v btmgmt >/dev/null 2>&1; then
        bt_try "btmgmt power on" btmgmt power on || true
    fi

    bt_try "bluetoothctl power on" bluetoothctl power on || true
    bt_try "bluetoothctl pairable on" bluetoothctl pairable on || true
    bt_try "bluetoothctl discoverable on" bluetoothctl discoverable on || true
    bt_try "bluetoothctl agent NoInputNoOutput" bluetoothctl agent NoInputNoOutput || true
    bt_try "bluetoothctl default-agent" bluetoothctl default-agent || true

    if ! bt_is_powered; then
        echo "Error: Bluetooth adapter is still not powered on."
        echo "Run diagnostics: bluetoothctl list ; rfkill list ; hciconfig -a"
        echo "Then retry: sudo bash $0 prepare-host"
        return 1
    fi

    echo "Current controller state:"
    bt_show | sed -n '1,20p'
    echo "RPi is ready for host pairing (Mac/PC)."
}

cmd_wait_pairing() {
    need_root
    ensure_bt_tools
    local timeout_sec="${1:-120}"
    local host_mac="${2:-}"

    if [[ -n "$host_mac" ]]; then
        require_mac "$host_mac"
    fi

    if ! [[ "$timeout_sec" =~ ^[0-9]+$ ]]; then
        echo "Error: timeout must be an integer number of seconds"
        exit 1
    fi

    # Pairing approval is handled by the Python BT agent (src.bt_agent),
    # so ensure bt backend service is running before waiting.
    if ! systemctl is-active --quiet "$SERVICE_BT"; then
        echo "Starting $SERVICE_BT so auto-accept agent can handle pairing..."
        cmd_service bt
        sleep 1
    fi

    if ! systemctl is-active --quiet "$SERVICE_BT"; then
        echo "Error: $SERVICE_BT is not active; cannot accept pairing requests."
        echo "Check logs: sudo journalctl -u $SERVICE_BT -n 80 --no-pager"
        return 1
    fi

    cmd_prepare_host
    if [[ -n "$host_mac" ]]; then
        echo "Waiting for HID pairing/connection to host ${host_mac} for up to ${timeout_sec}s..."
    else
        echo "Waiting for HID pairing/connection for up to ${timeout_sec}s..."
    fi
    local end=$((SECONDS + timeout_sec))
    local seen_connected=0
    local wait_since
    wait_since="$(date -Iseconds)"

    echo "Auto-accept agent source: $SERVICE_BT (src.bt_agent)"

    while [ "$SECONDS" -lt "$end" ]; do
        local paired
        paired="$(bt_list_paired_devices || true)"
        local connected
        connected="$(bluetoothctl devices Connected 2>/dev/null || true)"

        if [ -n "$paired" ]; then
            echo "--- paired devices ---"
            echo "$paired"
        fi
        if [ -n "$connected" ]; then
            echo "--- connected devices ---"
            echo "$connected"
        fi

        # Success criteria:
        # 1) if host MAC is specified, that exact host must be Connected: yes
        # 2) otherwise, BT HID interrupt channel must be connected in service logs
        if [[ -n "$host_mac" ]]; then
            if bt_device_connected "$host_mac"; then
                seen_connected=1
                break
            fi
        else
            if hid_channel_connected_since "$wait_since"; then
                seen_connected=1
                break
            fi
        fi

        sleep 3
    done

    if [ "$seen_connected" -eq 1 ]; then
        echo "Pairing wait completed: at least one host is connected."
        return 0
    fi

    echo "Timeout reached. Pairing may still succeed later from Mac Bluetooth settings."
    echo "Tip: keep service running and use: sudo bash $0 status"
    if [[ -n "$host_mac" ]]; then
        echo "Tip: verify target host state: sudo bash $0 info $host_mac"
    fi
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
    sudo bash $0 wait-pairing [timeout_sec] [host_mac]

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
        wait-pairing) cmd_wait_pairing "$@" ;;
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
