#!/bin/bash
set -euo pipefail

BACKUP_DIR="$(cd "$(dirname "$0")" && pwd)/config-backups"
mkdir -p "$BACKUP_DIR"

APPS="sonarr radarr lidarr readarr bazarr prowlarr"

for app in $APPS; do
  pod=$(kubectl get pods -n "$app" -l app.kubernetes.io/instance="$app" -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true)
  if [ -z "$pod" ]; then
    echo "No pod found for $app, skipping"
    continue
  fi
  echo "Backing up $app config from $pod..."
  kubectl exec -n "$app" "$pod" -c main -- tar czf - -C / config > "$BACKUP_DIR/${app}-config.tar.gz"
  echo "  -> $BACKUP_DIR/${app}-config.tar.gz"
done

echo ""
echo "All done. Backups in $BACKUP_DIR"