#!/system/bin/sh

status=0

for host in "$@"; do
    echo "Pinging $host"

    if ping -c 2 "$host"; then
        echo "OK: $host"
    else
        echo "FAIL: $host" >&2
        status=1
    fi
done

exit "$status"
