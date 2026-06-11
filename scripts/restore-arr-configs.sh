#!/bin/bash
set -euo pipefail

BACKUP_DIR="$(cd "$(dirname "$0")" && pwd)/config-backups"
APPS="sonarr radarr lidarr readarr bazarr prowlarr"

for app in $APPS; do
  backup="$BACKUP_DIR/${app}-config.tar.gz"
  if [ ! -f "$backup" ]; then
    echo "No backup found for $app at $backup, skipping"
    continue
  fi

  pod=$(kubectl get pods -n "$app" -l app.kubernetes.io/instance="$app" -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true)
  if [ -z "$pod" ]; then
    echo "No pod found for $app, skipping"
    continue
  fi

  echo "Restoring $app config to $pod..."
  cat "$backup" | kubectl exec -n "$app" "$pod" -c main -i -- tar xzf - -C /

  # Restart the pod so the app picks up the restored config
  kubectl delete pod -n "$app" "$pod"
  echo "  -> $pod deleted, will restart with restored config"
done

echo ""
echo "All done."