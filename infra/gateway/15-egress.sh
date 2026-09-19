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
  address=$(getent ahostsv4 "$service" | head -n 1 | awk '{print $1}')
  test -n "$address"
  iptables -A OUTPUT -d "$address" -j ACCEPT
done
iptables -P OUTPUT DROP
if [ -e /proc/net/if_inet6 ]; then
  ip6tables -P OUTPUT DROP 2>/dev/null || true
fi

# Pin the host upstream to the same IPv4 address admitted by the firewall.
# Docker Desktop can resolve host-gateway to IPv6 first; iptables is IPv4-only.
if [ -f /etc/nginx/host-ollama.conf ]; then
  host_address=$(getent ahostsv4 host.docker.internal | head -n 1 | awk '{print $1}')
  test -n "$host_address"
  sed "s/host.docker.internal/$host_address/g" /etc/nginx/host-ollama.conf > /etc/nginx/conf.d/default.conf
fi
