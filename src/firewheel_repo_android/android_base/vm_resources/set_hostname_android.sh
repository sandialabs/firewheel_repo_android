#!/system/bin/sh

set -u

HOSTNAME_VALUE="$1"
DONE_FILE="done"

if [ -f "$DONE_FILE" ]; then
    exit 0
fi

if [ -z "$HOSTNAME_VALUE" ]; then
    echo "No hostname provided." >&2
    exit 1
fi

success=0

log_info() {
    echo "INFO: $*"
}

log_warn() {
    echo "WARN: $*" >&2
}

try_cmd() {
    description="$1"
    shift

    if "$@" >/dev/null 2>&1; then
        log_info "$description succeeded."
        success=1
        return 0
    fi

    log_warn "$description failed."
    return 1
}

# 1. Android property commonly used by older Android networking paths.
try_cmd "setprop net.hostname" setprop net.hostname "$HOSTNAME_VALUE"

# 2. Try Android/system hostname command if present.
if command -v hostname >/dev/null 2>&1; then
    try_cmd "hostname command" hostname "$HOSTNAME_VALUE"
elif [ -x /system/bin/hostname ]; then
    try_cmd "/system/bin/hostname command" /system/bin/hostname "$HOSTNAME_VALUE"
elif command -v toybox >/dev/null 2>&1; then
    try_cmd "toybox hostname command" toybox hostname "$HOSTNAME_VALUE"
else
    log_warn "No hostname command found."
fi

# 3. Linux kernel hostname interface. This may or may not be writable on Android.
if [ -w /proc/sys/kernel/hostname ]; then
    if printf '%s\n' "$HOSTNAME_VALUE" > /proc/sys/kernel/hostname 2>/dev/null; then
        log_info "Writing /proc/sys/kernel/hostname succeeded."
        success=1
    else
        log_warn "Writing /proc/sys/kernel/hostname failed."
    fi
else
    log_warn "/proc/sys/kernel/hostname is not writable."
fi

# 4. sysctl, if available.
if command -v sysctl >/dev/null 2>&1; then
    try_cmd "sysctl kernel.hostname" sysctl -w "kernel.hostname=$HOSTNAME_VALUE"
elif command -v toybox >/dev/null 2>&1; then
    try_cmd "toybox sysctl kernel.hostname" toybox sysctl -w "kernel.hostname=$HOSTNAME_VALUE"
else
    log_warn "No sysctl command found."
fi

# 5. Best-effort /etc/hosts update. This is not counted as setting the hostname,
# but it can help local name resolution when writable.
update_hosts() {
    hosts_path="$1"

    if [ ! -e "$hosts_path" ]; then
        log_warn "$hosts_path does not exist."
        return 1
    fi

    tmp="/data/local/tmp/firewheel-hosts.$$"

    # Avoid sed -i because Android sed may be unable to create temp files near
    # /etc or /system/etc.
    grep -v '^127\.0\.0\.1' "$hosts_path" 2>/dev/null \
        | grep -v '^127\.0\.1\.1' > "$tmp" 2>/dev/null || true

    printf '127.0.0.1\tlocalhost %s\n' "$HOSTNAME_VALUE" >> "$tmp"

    if cp "$tmp" "$hosts_path" 2>/dev/null; then
        log_info "Updated $hosts_path."
        rm -f "$tmp"
        return 0
    fi

    log_warn "Unable to update $hosts_path."
    rm -f "$tmp"
    return 1
}

update_hosts /etc/hosts || true

# On many Android images /etc/hosts may resolve to /system/etc/hosts, but try
# explicitly as a fallback if it is distinct/present.
if [ -e /system/etc/hosts ]; then
    update_hosts /system/etc/hosts || true
fi

# Verification/best-effort reporting.
reported_hostname=""
if command -v hostname >/dev/null 2>&1; then
    reported_hostname="$(hostname 2>/dev/null || true)"
elif [ -r /proc/sys/kernel/hostname ]; then
    reported_hostname="$(cat /proc/sys/kernel/hostname 2>/dev/null || true)"
fi

reported_property="$(getprop net.hostname 2>/dev/null || true)"

log_info "Requested hostname: $HOSTNAME_VALUE"
log_info "Reported hostname command/proc value: $reported_hostname"
log_info "Reported net.hostname property: $reported_property"

if [ "$success" -eq 1 ]; then
    touch "$DONE_FILE" 2>/dev/null || true
    exit 0
fi

log_warn "Unable to set Android hostname using any available method."
exit 1
