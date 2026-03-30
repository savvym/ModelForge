#!/bin/sh
set -eu

until tctl cluster health >/dev/null 2>&1; do
  echo "waiting for temporal..."
  sleep 2
done

if tctl --ns "$TEMPORAL_NAMESPACE" namespace describe >/dev/null 2>&1; then
  echo "temporal namespace already exists: $TEMPORAL_NAMESPACE"
  exit 0
fi

tctl --ns "$TEMPORAL_NAMESPACE" namespace register
echo "temporal namespace created: $TEMPORAL_NAMESPACE"

