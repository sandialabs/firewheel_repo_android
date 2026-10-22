#!/system/bin/sh

# Android APK installer for FIREWHEEL.
#
# Usage:
#   install_apk_android.sh --independent <apk1> [apk2 ...]
#   install_apk_android.sh --split <base.apk> <split1.apk> [split2.apk ...]
#
# Modes:
#   --independent:
#       Install each APK separately using pm install -r.
#
#   --split:
#       Install all APKs as one split package.

TIMEOUT_SECONDS="${TIMEOUT_SECONDS:-180}"
SLEEP_SECONDS="${SLEEP_SECONDS:-2}"
MAX_ATTEMPTS="${MAX_ATTEMPTS:-10}"

MODE="$1"
shift

if [ "$MODE" != "--independent" ] && [ "$MODE" != "--split" ]; then
    echo "ERROR: First argument must be --independent or --split." >&2
    exit 1
fi

if [ "$#" -lt 1 ]; then
    echo "ERROR: No APK path(s) provided." >&2
    exit 1
fi

for apk in "$@"; do
    if [ ! -f "$apk" ]; then
        echo "ERROR: APK does not exist: $apk" >&2
        exit 1
    fi
done

log_info() {
    echo "INFO: $*"
}

log_warn() {
    echo "WARN: $*" >&2
}

log_error() {
    echo "ERROR: $*" >&2
}

wait_for_boot_completed() {
    elapsed=0

    log_info "Waiting for Android boot completion."

    while [ "$elapsed" -lt "$TIMEOUT_SECONDS" ]; do
        sys_boot_completed="$(getprop sys.boot_completed 2>/dev/null || true)"
        dev_bootcomplete="$(getprop dev.bootcomplete 2>/dev/null || true)"
        init_svc_bootanim="$(getprop init.svc.bootanim 2>/dev/null || true)"

        if [ "$sys_boot_completed" = "1" ] || [ "$dev_bootcomplete" = "1" ]; then
            log_info "Android boot property indicates boot complete."
            log_info "sys.boot_completed=$sys_boot_completed dev.bootcomplete=$dev_bootcomplete init.svc.bootanim=$init_svc_bootanim"
            return 0
        fi

        log_info "Android still booting: sys.boot_completed=$sys_boot_completed dev_bootcomplete=$dev_bootcomplete init.svc.bootanim=$init_svc_bootanim"
        sleep "$SLEEP_SECONDS"
        elapsed=$((elapsed + SLEEP_SECONDS))
    done

    log_error "Timed out waiting for Android boot completion."
    return 1
}

wait_for_package_manager() {
    elapsed=0

    log_info "Waiting for Android Package Manager."

    while [ "$elapsed" -lt "$TIMEOUT_SECONDS" ]; do
        if pm path android >/dev/null 2>&1; then
            log_info "Package Manager appears ready via 'pm path android'."
            return 0
        fi

        if cmd package list packages >/dev/null 2>&1; then
            log_info "Package Manager appears ready via 'cmd package list packages'."
            return 0
        fi

        log_info "Package Manager not ready yet."
        sleep "$SLEEP_SECONDS"
        elapsed=$((elapsed + SLEEP_SECONDS))
    done

    log_error "Timed out waiting for Android Package Manager."
    return 1
}

run_with_retries() {
    description="$1"
    shift

    attempt=1

    while [ "$attempt" -le "$MAX_ATTEMPTS" ]; do
        log_info "$description attempt $attempt/$MAX_ATTEMPTS."
        log_info "Running: $*"

        output="$("$@" 2>&1)"
        rc="$?"

        echo "$output"

        if [ "$rc" -eq 0 ]; then
            log_info "$description succeeded."
            return 0
        fi

        echo "$output" | grep -qi "still booting"
        still_booting="$?"

        echo "$output" | grep -qi "package manager"
        package_manager_issue="$?"

        echo "$output" | grep -qi "Can't find service: package"
        package_service_issue="$?"

        if [ "$still_booting" -eq 0 ] || [ "$package_manager_issue" -eq 0 ] || [ "$package_service_issue" -eq 0 ]; then
            log_warn "$description failed because Android is not ready. Retrying."
            sleep "$SLEEP_SECONDS"
            attempt=$((attempt + 1))
            wait_for_boot_completed || return 1
            wait_for_package_manager || return 1
            continue
        fi

        log_error "$description failed with non-retryable error."
        return "$rc"
    done

    log_error "$description failed after $MAX_ATTEMPTS attempts."
    return 1
}

install_independent() {
    status=0

    for apk in "$@"; do
        if ! run_with_retries "APK install $apk" pm install -r "$apk"; then
            status=1
        fi
    done

    return "$status"
}

install_split_with_install_multiple() {
    if pm help 2>/dev/null | grep -q "install-multiple"; then
        run_with_retries "Split APK install" pm install-multiple -r "$@"
        return "$?"
    fi

    if cmd package help 2>/dev/null | grep -q "install-multiple"; then
        run_with_retries "Split APK install" cmd package install-multiple -r "$@"
        return "$?"
    fi

    return 127
}

install_split_with_session() {
    log_info "Using Package Manager install session for split APK install."

    session_output="$(pm install-create -r 2>&1)"
    rc="$?"

    echo "$session_output"

    if [ "$rc" -ne 0 ]; then
        log_error "pm install-create failed."
        return "$rc"
    fi

    session_id="$(echo "$session_output" | sed -n 's/.*\[\([0-9][0-9]*\)\].*/\1/p')"

    if [ -z "$session_id" ]; then
        log_error "Unable to parse install session ID from: $session_output"
        return 1
    fi

    for apk in "$@"; do
        size="$(wc -c < "$apk" 2>/dev/null | tr -d ' ')"
        name="$(basename "$apk")"

        if [ -z "$size" ]; then
            log_error "Unable to determine size for $apk"
            pm install-abandon "$session_id" >/dev/null 2>&1 || true
            return 1
        fi

        log_info "Writing split $name size=$size to session $session_id"

        output="$(pm install-write -S "$size" "$session_id" "$name" "$apk" 2>&1)"
        rc="$?"

        echo "$output"

        if [ "$rc" -ne 0 ]; then
            log_error "pm install-write failed for $apk"
            pm install-abandon "$session_id" >/dev/null 2>&1 || true
            return "$rc"
        fi
    done

    output="$(pm install-commit "$session_id" 2>&1)"
    rc="$?"

    echo "$output"

    if [ "$rc" -eq 0 ]; then
        log_info "Split APK install succeeded."
        return 0
    fi

    log_error "pm install-commit failed."
    return "$rc"
}

install_split() {
    install_split_with_install_multiple "$@"
    rc="$?"

    if [ "$rc" -eq 0 ]; then
        return 0
    fi

    if [ "$rc" -ne 127 ]; then
        return "$rc"
    fi

    log_warn "install-multiple is unavailable; falling back to install session API."
    install_split_with_session "$@"
}

wait_for_boot_completed || exit 1
wait_for_package_manager || exit 1

case "$MODE" in
    --independent)
        install_independent "$@"
        exit "$?"
        ;;
    --split)
        install_split "$@"
        exit "$?"
        ;;
esac

log_error "Unreachable installer mode: $MODE"
exit 1
