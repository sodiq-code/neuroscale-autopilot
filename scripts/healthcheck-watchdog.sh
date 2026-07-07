#!/bin/bash
# Watchdog: restarts the autopilot container if it stops responding.
# Defense-in-depth on top of the actual code fix for the blocking-event-loop
# bug — this exists so the live deployment self-heals within ~2 minutes even
# if any other, still-unknown issue causes it to hang, since this is a
# hackathon submission that judges may check unannounced at any time.
#
# Install as a cron job (runs every minute):
#   * * * * * /root/neuroscale-autopilot/scripts/healthcheck-watchdog.sh >> /var/log/autopilot-watchdog.log 2>&1

CONTAINER_NAME="neuroscale-autopilot"
HEALTH_URL="http://localhost:8000/health"
TIMEOUT_SECONDS=5

STATUS=$(curl -s -m "$TIMEOUT_SECONDS" -o /dev/null -w "%{http_code}" "$HEALTH_URL")

if [ "$STATUS" != "200" ]; then
  echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) UNHEALTHY (status=$STATUS) - restarting $CONTAINER_NAME"
  docker restart "$CONTAINER_NAME"
else
  echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) OK"
fi
