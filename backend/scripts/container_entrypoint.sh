#!/bin/sh
# Initialize the managed volume, then drop privileges before migration/API/worker execution.
set -eu
mkdir -p /var/lib/trust/history
chown 10001:10001 /var/lib/trust /var/lib/trust/history
chmod 700 /var/lib/trust/history
exec setpriv --reuid=10001 --regid=10001 --init-groups --bounding-set=-all --no-new-privs "$@"
