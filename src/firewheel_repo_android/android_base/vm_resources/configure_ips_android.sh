#!/system/bin/sh

# Android-compatible FIREWHEEL IP configuration script.
#
# Expected input file format:
#
#   <dns1> [dns2]
#   <network> <mac> <addr> <netmask> <prefix> [gateway]
#
# Example:
#
#   8.8.8.8 1.1.1.1
#   network-10 00:00:00:00:00:01 10.0.0.2 255.255.255.0 24 10.0.0.1
#
# This script intentionally avoids Linux distribution persistence mechanisms
# such as /etc/network/interfaces, /etc/sysconfig, NetworkManager, and systemd.
# Android network configuration here is runtime-only.

CONFIG_FILE="$1"

# Accepted for compatibility with the Linux configure_ips.sh invocation:
#   configure_ips_android.sh dynamic None reboot
# but currently unused on Android.
_NAMESERVER_MODE="${2:-}"
_REBOOT_MODE="${3:-}"

MAX_ATTEMPTS="${MAX_ATTEMPTS:-120}"
SLEEP_SECONDS="${SLEEP_SECONDS:-2}"

if [ -z "$CONFIG_FILE" ]; then
    echo "ERROR: No dynamic network config file provided." >&2
    exit 1
fi

if [ ! -f "$CONFIG_FILE" ]; then
    echo "ERROR: Dynamic network config file not found: $CONFIG_FILE" >&2
    exit 1
fi

log_info() {
    echo "INFO: $*"
}

log_warn() {
    echo "WARN: $*" >&2
}

log_error() {
    echo "ERROR: $*" >&2
}

lower_mac() {
    echo "$1" | tr 'A-F' 'a-f'
}

print_interface_info() {
    log_info "Available Android interfaces and MAC addresses:"
    for iface_path in /sys/class/net/*; do
        [ -e "$iface_path" ] || continue

        dev="${iface_path##*/}"
        mac="$(cat "$iface_path/address" 2>/dev/null | tr 'A-F' 'a-f')"

        if [ -n "$mac" ]; then
            echo "$dev -> $mac"
        fi
    done
}

find_device_by_mac() {
    target_mac="$(lower_mac "$1")"

    for iface_path in /sys/class/net/*; do
        [ -e "$iface_path" ] || continue

        dev="${iface_path##*/}"
        mac="$(cat "$iface_path/address" 2>/dev/null | tr 'A-F' 'a-f')"

        if [ "$mac" = "$target_mac" ]; then
            echo "$dev"
            return 0
        fi
    done

    return 1
}

set_dns_nameservers() {
    nameservers="$1"

    if [ -z "$nameservers" ]; then
        log_info "No DNS nameservers specified."
        return 0
    fi

    set -- $nameservers
    dns1="${1:-}"
    dns2="${2:-}"

    if [ -n "$dns1" ]; then
        log_info "Setting Android DNS property net.dns1=$dns1"
        setprop net.dns1 "$dns1" 2>/dev/null || log_warn "Unable to set net.dns1"
    fi

    if [ -n "$dns2" ]; then
        log_info "Setting Android DNS property net.dns2=$dns2"
        setprop net.dns2 "$dns2" 2>/dev/null || log_warn "Unable to set net.dns2"
    fi

    # Best-effort resolv.conf update for images that provide a writable file.
    # Android usually does not rely on /etc/resolv.conf, so this is not fatal.
    if [ -w /etc/resolv.conf ]; then
        log_info "Updating /etc/resolv.conf"
        : > /etc/resolv.conf 2>/dev/null || true

        if [ -n "$dns1" ]; then
            echo "nameserver $dns1" >> /etc/resolv.conf 2>/dev/null || true
        fi

        if [ -n "$dns2" ]; then
            echo "nameserver $dns2" >> /etc/resolv.conf 2>/dev/null || true
        fi
    else
        log_warn "/etc/resolv.conf is not writable; skipping resolv.conf update."
    fi

    return 0
}

set_gateway() {
    dev="$1"
    gateway="$2"

    if [ -z "$gateway" ]; then
        return 0
    fi

    log_info "Setting default gateway via $gateway dev $dev"

    ip route replace default via "$gateway" dev "$dev" 2>/dev/null && return 0
    ip route add default via "$gateway" dev "$dev" 2>/dev/null && return 0

    log_warn "Unable to set default gateway via $gateway dev $dev"
    return 1
}

set_ip() {
    dev="$1"
    cidr="$2"

    log_info "Setting $dev to IP: $cidr"

    ip link set dev "$dev" up 2>/dev/null || {
        log_error "Unable to bring interface $dev up."
        return 1
    }

    ip addr flush dev "$dev" 2>/dev/null || true

    ip addr add "$cidr" dev "$dev" 2>/dev/null || {
        log_error "Unable to add address $cidr to $dev."
        return 1
    }

    ip link set dev "$dev" up 2>/dev/null || true

    attempts=0
    while true; do
        if ip addr show dev "$dev" 2>/dev/null | grep -q "$cidr"; then
            log_info "Confirmed $dev has address $cidr"
            return 0
        fi

        attempts=$((attempts + 1))
        if [ "$attempts" -ge 10 ]; then
            log_error "Address $cidr did not appear on $dev after $attempts attempts."
            return 1
        fi

        log_warn "IP did not take on $dev, sleeping and trying again."
        sleep 1
        ip addr add "$cidr" dev "$dev" 2>/dev/null || true
    done
}

configure_line() {
    line="$1"

    # Skip blank lines and comments.
    case "$line" in
        ""|\#*)
            return 0
            ;;
    esac

    set -- $line

    if [ "$#" -le 2 ]; then
        return 0
    fi

    network="$1"
    mac="$2"
    addr="$3"
    netmask="${4:-}"
    prefix="${5:-}"
    gateway="${6:-}"

    if [ -z "$mac" ] || [ -z "$addr" ] || [ -z "$prefix" ]; then
        log_error "Invalid network config line: $line"
        return 1
    fi

    log_info "Configuring network=$network mac=$mac addr=$addr netmask=$netmask prefix=$prefix gateway=$gateway"

    attempts=0
    while true; do
        dev="$(find_device_by_mac "$mac")"

        if [ -n "$dev" ]; then
            log_info "Found device $dev for MAC $mac"

            set_ip "$dev" "$addr/$prefix" || return 1
            set_gateway "$dev" "$gateway" || true

            return 0
        fi

        attempts=$((attempts + 1))

        if [ "$MAX_ATTEMPTS" != "0" ] && [ "$attempts" -ge "$MAX_ATTEMPTS" ]; then
            log_error "Unable to find device for MAC $mac after $attempts attempts."
            print_interface_info
            return 1
        fi

        log_warn "Unable to find device for MAC $mac, sleeping."
        print_interface_info
        sleep "$SLEEP_SECONDS"
    done
}

print_interface_info

NAMESERVERS="$(head -n 1 "$CONFIG_FILE" 2>/dev/null || true)"
set_dns_nameservers "$NAMESERVERS"

BODY_FILE="/data/local/tmp/firewheel-configure-ips.$$"
tail -n +2 "$CONFIG_FILE" > "$BODY_FILE" 2>/dev/null || {
    log_error "Unable to read network config body from $CONFIG_FILE"
    rm -f "$BODY_FILE"
    exit 1
}

overall_status=0

while IFS= read -r line; do
    if ! configure_line "$line"; then
        overall_status=1
    fi
done < "$BODY_FILE"

rm -f "$BODY_FILE"

exit "$overall_status"