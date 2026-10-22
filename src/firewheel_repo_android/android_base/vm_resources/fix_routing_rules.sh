#!/system/bin/sh

for rule in $(ip rule | tail -n +2 | awk '{print $1}' | tr -d ':');
do
    ip rule del pref $rule;
done

ip rule add pref 1000 from all lookup main
ip rule add pref 2000 from all lookup default
