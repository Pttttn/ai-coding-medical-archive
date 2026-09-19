#!/bin/sh
set -eu
# Published ports require a non-internal bridge on recent Docker Desktop.
# This ingress-only proxy can originate connections only to named local services.
iptables -F OUTPUT
iptables -A OUTPUT -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT
iptables -A OUTPUT -o lo -j ACCEPT
iptables -A OUTPUT -d 127.0.0.11 -p udp --dport 53 -j ACCEPT
iptables -A OUTPUT -d 127.0.0.11 -p tcp --dport 53 -j ACCEPT
for service in ${EGRESS_TARGETS:-frontend backend ai}; do
  address=$(getent hosts "$service" | head -n 1 | awk '{print $1}')
  test -n "$address"
  iptables -A OUTPUT -d "$address" -j ACCEPT
done
iptables -P OUTPUT DROP
if [ -e /proc/net/if_inet6 ]; then
  ip6tables -P OUTPUT DROP 2>/dev/null || true
fi
